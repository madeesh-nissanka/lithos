# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Screening module for LITHOS - inclusion/exclusion rules, keyword scoring, TF-IDF/BM25 ranking, two-reviewer support.
"""
from __future__ import annotations
import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from lithos.models import Record, ScreenState, ScreenDecision

logger = logging.getLogger(__name__)


@dataclass
class ScreeningRule:
    """A single inclusion/exclusion rule."""
    id: str
    type: str  # "include" or "exclude"
    field: str  # "title", "abstract", "keywords", "venue", "year", "any"
    pattern: str
    is_regex: bool = False
    case_sensitive: bool = False
    description: str = ""

    def matches(self, record: Record) -> bool:
        """Check if rule matches a record."""
        text = self._get_field_text(record)
        if not text:
            return False

        if self.is_regex:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            return bool(re.search(self.pattern, text, flags))
        else:
            if not self.case_sensitive:
                text = text.lower()
                pattern = self.pattern.lower()
            else:
                pattern = self.pattern
            return pattern in text

    def _get_field_text(self, record: Record) -> str:
        """Get text content for the specified field."""
        if self.field == "title":
            return record.title
        elif self.field == "abstract":
            return record.abstract
        elif self.field == "keywords":
            return " ".join(record.keywords)
        elif self.field == "venue":
            return record.venue or ""
        elif self.field == "year":
            return str(record.year) if record.year else ""
        elif self.field == "any":
            parts = [record.title, record.abstract, " ".join(record.keywords), record.venue or ""]
            if record.year:
                parts.append(str(record.year))
            return " ".join(parts)
        return ""


@dataclass
class ScreeningRules:
    """Collection of screening rules."""
    rules: list[ScreeningRule] = field(default_factory=list)

    def add_rule(self, rule: ScreeningRule):
        self.rules.append(rule)

    def add_include(self, field: str, pattern: str, **kwargs) -> ScreeningRule:
        rule = ScreeningRule(id=f"inc_{len(self.rules)}", type="include", field=field, pattern=pattern, **kwargs)
        self.add_rule(rule)
        return rule

    def add_exclude(self, field: str, pattern: str, **kwargs) -> ScreeningRule:
        rule = ScreeningRule(id=f"exc_{len(self.rules)}", type="exclude", field=field, pattern=pattern, **kwargs)
        self.add_rule(rule)
        return rule

    def evaluate(self, record: Record) -> tuple[ScreenState, list[str]]:
        """Evaluate all rules against a record."""
        include_hits = []
        exclude_hits = []

        for rule in self.rules:
            if rule.matches(record):
                if rule.type == "include":
                    include_hits.append(rule.id)
                else:
                    exclude_hits.append(rule.id)

        # Exclude takes precedence
        if exclude_hits:
            return ScreenState.EXCLUDE, exclude_hits
        elif include_hits:
            return ScreenState.INCLUDE, include_hits
        else:
            return ScreenState.UNSCREENED, []

    def save(self, path: Path):
        """Save rules to JSON file."""
        data = {
            "rules": [
                {
                    "id": r.id,
                    "type": r.type,
                    "field": r.field,
                    "pattern": r.pattern,
                    "is_regex": r.is_regex,
                    "case_sensitive": r.case_sensitive,
                    "description": r.description,
                }
                for r in self.rules
            ]
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path) -> ScreeningRules:
        """Load rules from JSON file."""
        data = json.loads(path.read_text())
        rules = ScreeningRules()
        for r in data.get("rules", []):
            rules.add_rule(ScreeningRule(**r))
        return rules


@dataclass
class KeywordScorer:
    """Scores records based on keyword presence."""
    include_keywords: dict[str, float] = field(default_factory=dict)  # keyword -> weight
    exclude_keywords: dict[str, float] = field(default_factory=dict)

    def score(self, record: Record) -> float:
        """Calculate keyword score for a record."""
        text = f"{record.title} {record.abstract} {' '.join(record.keywords)}".lower()
        score = 0.0
        for kw, weight in self.include_keywords.items():
            if kw.lower() in text:
                score += weight
        for kw, weight in self.exclude_keywords.items():
            if kw.lower() in text:
                score -= weight
        return score


class TFIDFRanker:
    """TF-IDF/BM25 ranker for abstract relevance (offline, no network)."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs: Counter = Counter()
        self.doc_lengths: list[int] = []
        self.avgdl: float = 0
        self.corpus: list[Record] = []
        self._fitted = False

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer."""
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return [t for t in text.split() if len(t) > 2]

    def fit(self, records: list[Record]):
        """Fit the ranker on a corpus of records."""
        self.corpus = records
        self.doc_freqs = Counter()
        self.doc_lengths = []

        for record in records:
            text = f"{record.title} {record.abstract} {' '.join(record.keywords)}"
            tokens = self._tokenize(text)
            self.doc_lengths.append(len(tokens))
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] += 1

        self.avgdl = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0
        self._fitted = True

    def score(self, query: str, record: Record) -> float:
        """BM25 score for a query against a record."""
        if not self._fitted:
            return 0.0

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return 0.0

        text = f"{record.title} {record.abstract} {' '.join(record.keywords)}"
        doc_tokens = self._tokenize(text)
        doc_len = len(doc_tokens)
        if doc_len == 0:
            return 0.0

        term_freqs = Counter(doc_tokens)
        score = 0.0
        N = len(self.corpus)

        for token in query_tokens:
            df = self.doc_freqs.get(token, 0)
            if df == 0:
                continue
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1)
            tf = term_freqs.get(token, 0)
            score += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl))

        return score

    def rank(self, query: str, records: list[Record]) -> list[tuple[Record, float]]:
        """Rank records by relevance to query."""
        scored = [(r, self.score(query, r)) for r in records]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


@dataclass
class ScreeningSession:
    """Manages a screening session with multiple reviewers."""
    records: list[Record] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=list)
    rules: Optional[ScreeningRules] = None
    keyword_scorer: Optional[KeywordScorer] = None
    tfidf_ranker: Optional[TFIDFRanker] = None
    decisions: dict[str, dict[str, ScreenDecision]] = field(default_factory=dict)  # record_id -> {reviewer -> decision}

    def add_reviewer(self, name: str):
        if name not in self.reviewers:
            self.reviewers.append(name)

    def record_decision(self, record_id: str, reviewer: str, decision: ScreenState, notes: str = ""):
        """Record a screening decision."""
        if record_id not in self.decisions:
            self.decisions[record_id] = {}
        self.decisions[record_id][reviewer] = ScreenDecision(
            reviewer=reviewer,
            decision=decision,
            notes=notes,
        )

    def get_consensus(self, record_id: str) -> tuple[ScreenState, bool]:
        """Get consensus decision for a record (returns state, has_conflict)."""
        if record_id not in self.decisions:
            return ScreenState.UNSCREENED, False

        decisions = self.decisions[record_id]
        if not decisions:
            return ScreenState.UNSCREENED, False

        states = [d.decision for d in decisions.values()]
        if all(s == states[0] for s in states):
            return states[0], False
        else:
            return ScreenState.CONFLICT, True

    def apply_rules(self):
        """Apply screening rules to all records."""
        if not self.rules:
            return
        for record in self.records:
            state, hits = self.rules.evaluate(record)
            if state != ScreenState.UNSCREENED:
                record.screen_state = state
                record.screen_notes = f"Auto: {', '.join(hits)}"

    def apply_keyword_scoring(self, threshold: float = 0.0):
        """Apply keyword scoring."""
        if not self.keyword_scorer:
            return
        for record in self.records:
            score = self.keyword_scorer.score(record)
            if score > threshold:
                record.screen_state = ScreenState.INCLUDE
                record.screen_notes = f"Keyword score: {score:.2f}"
            elif score < -threshold:
                record.screen_state = ScreenState.EXCLUDE
                record.screen_notes = f"Keyword score: {score:.2f}"

    def apply_tfidf_ranking(self, query: str, top_k: int = 50):
        """Apply TF-IDF ranking and auto-include top K."""
        if not self.tfidf_ranker:
            return
        self.tfidf_ranker.fit(self.records)
        ranked = self.tfidf_ranker.rank(query, self.records)
        for i, (record, score) in enumerate(ranked):
            if i < top_k:
                record.screen_state = ScreenState.INCLUDE
                record.screen_notes = f"TF-IDF rank: {i+1}, score: {score:.3f}"

    def export_two_reviewer(self, path: Path):
        """Export screening results for two reviewers with disagreement columns."""
        if len(self.reviewers) != 2:
            logger.warning("Two-reviewer export requires exactly 2 reviewers")
        r1, r2 = self.reviewers[0] if self.reviewers else "Reviewer1", self.reviewers[1] if len(self.reviewers) > 1 else "Reviewer2"

        lines = []
        lines.append("| Include? (Y/N) | ID | DOI | Year | First Author | Title | Venue | Reviewer 1 | Reviewer 2 | Agreement | Notes |\n")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|\n")

        for record in self.records:
            d1 = self.decisions.get(record.id, {}).get(r1)
            d2 = self.decisions.get(record.id, {}).get(r2)
            s1 = d1.decision.value if d1 else ""
            s2 = d2.decision.value if d2 else ""
            agreement = "Y" if s1 == s2 and s1 else "N" if s1 and s2 else "?"
            notes = ""
            if d1:
                notes += f"R1: {d1.notes}; "
            if d2:
                notes += f"R2: {d2.notes}"

            title_disp = (record.title or "").replace("|", "\\|")[:100]
            venue_disp = (record.venue or "").replace("|", "\\|")
            first_author = first_author_surname(record.authors) or ""

            lines.append(f"| | {record.id} | {record.doi or ''} | {record.year or ''} | {first_author} | {title_disp} | {venue_disp} | {s1} | {s2} | {agreement} | {notes} |\n")

        path.write_text("\n".join(lines))

    def export_decisions(self, path: Path):
        """Export all decisions as JSON."""
        data = {
            "reviewers": self.reviewers,
            "decisions": {
                rid: {rev: {"decision": dec.decision.value, "notes": dec.notes} for rev, dec in revs.items()}
                for rid, revs in self.decisions.items()
            }
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load_decisions(cls, path: Path) -> dict:
        """Load decisions from JSON."""
        return json.loads(path.read_text())


def first_author_surname(authors: list[str]) -> Optional[str]:
    if not authors:
        return None
    name = authors[0].strip()
    if "," in name:
        return name.split(",")[0].strip()
    parts = name.split()
    return parts[-1] if parts else None