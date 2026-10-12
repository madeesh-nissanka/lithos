# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Screening module for LITHOS - inclusion/exclusion rules, keyword scoring, TF-IDF/BM25 ranking, two-reviewer support.
"""
from __future__ import annotations
import csv
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

    def matches(self, record: Record, extra_text: str = "") -> bool:
        """Check if rule matches a record."""
        text = self._get_field_text(record, extra_text)
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

    def _get_field_text(self, record: Record, extra_text: str = "") -> str:
        """Get text content for the specified field."""
        if self.field == "title":
            return record.title
        elif self.field == "abstract":
            return record.abstract
        elif self.field == "fulltext":
            return extra_text
        elif self.field == "keywords":
            return " ".join(record.keywords)
        elif self.field == "venue":
            return record.venue or ""
        elif self.field == "year":
            return str(record.year) if record.year else ""
        elif self.field == "any":
            parts = [record.title, record.abstract, " ".join(record.keywords), record.venue or "", extra_text]
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

    def evaluate(self, record: Record, extra_text: str = "") -> tuple[ScreenState, list[str]]:
        """Evaluate all rules against a record."""
        include_hits = []
        exclude_hits = []

        for rule in self.rules:
            if rule.matches(record, extra_text):
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

    def score(self, record: Record, full_text: str = "") -> float:
        """Calculate keyword score for a record."""
        text = f"{record.title} {record.abstract} {' '.join(record.keywords)} {full_text}".lower()
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
        self._full_texts: dict = {}
        self._fitted = False

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer."""
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return [t for t in text.split() if len(t) > 2]

    def fit(self, records: list[Record], full_texts: Optional[dict] = None):
        """Fit the ranker on a corpus of records."""
        self.corpus = records
        self._full_texts = full_texts or {}
        self.doc_freqs = Counter()
        self.doc_lengths = []

        for record in records:
            text = f"{record.title} {record.abstract} {' '.join(record.keywords)} {self._full_texts.get(record.id, '')}"
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

        text = f"{record.title} {record.abstract} {' '.join(record.keywords)} {self._full_texts.get(record.id, '')}"
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

    def apply_rules(self, full_texts: Optional[dict[str, str]] = None):
        """Apply screening rules to all records, optionally with full text."""
        if not self.rules:
            return
        for record in self.records:
            extra = (full_texts or {}).get(record.id, "")
            state, hits = self.rules.evaluate(record, extra_text=extra)
            if state != ScreenState.UNSCREENED:
                record.screen_state = state
                record.screen_notes = f"Auto: {', '.join(hits)}"

    def apply_keyword_scoring(self, threshold: float = 0.0, full_texts: Optional[dict] = None):
        """Apply keyword scoring."""
        if not self.keyword_scorer:
            return
        for record in self.records:
            score = self.keyword_scorer.score(record, (full_texts or {}).get(record.id, ""))
            if score > threshold:
                record.screen_state = ScreenState.INCLUDE
                record.screen_notes = f"Keyword score: {score:.2f}"
            elif score < -threshold:
                record.screen_state = ScreenState.EXCLUDE
                record.screen_notes = f"Keyword score: {score:.2f}"

    def apply_tfidf_ranking(self, query: str, top_k: int = 50, full_texts: Optional[dict] = None):
        """Apply TF-IDF ranking and auto-include top K."""
        if not self.tfidf_ranker:
            return
        self.tfidf_ranker.fit(self.records, full_texts)
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

    def export_reviewer_form(self, path: Path, reviewer: str):
        """Export a CSV screening form for one reviewer (decision column empty)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["record_id", "reviewer", "title", "year", "first_author", "venue", "doi", "decision", "reason"])
            for record in self.records:
                writer.writerow([
                    record.id,
                    reviewer,
                    record.title,
                    record.year or "",
                    first_author_surname(record.authors) or "",
                    record.venue or "",
                    record.doi or "",
                    "",
                    "",
                ])

    def import_reviewer_decisions(self, path: Path, reviewer: str) -> int:
        """Import decisions from a filled reviewer CSV. Returns count imported."""
        imported = 0
        valid = {ScreenState.INCLUDE.value: ScreenState.INCLUDE, ScreenState.EXCLUDE.value: ScreenState.EXCLUDE}
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                raw = (row.get("decision") or "").strip().upper()
                if raw not in valid:
                    continue
                self.record_decision(row.get("record_id", ""), reviewer, valid[raw], row.get("reason", ""))
                imported += 1
        return imported

    def agreement_report(self, reviewer_1: str, reviewer_2: str) -> AgreementReport:
        """Compute Cohen's kappa + confusion matrix + conflict list for two reviewers."""
        labels_1: list[str] = []
        labels_2: list[str] = []
        conflicts: list[dict] = []
        confusion: Counter = Counter()
        record_by_id = {r.id: r for r in self.records}

        for record_id, decs in sorted(self.decisions.items()):
            d1 = decs.get(reviewer_1)
            d2 = decs.get(reviewer_2)
            if not d1 or not d2:
                continue
            if d1.decision not in (ScreenState.INCLUDE, ScreenState.EXCLUDE):
                continue
            if d2.decision not in (ScreenState.INCLUDE, ScreenState.EXCLUDE):
                continue
            s1, s2 = d1.decision.value, d2.decision.value
            labels_1.append(s1)
            labels_2.append(s2)
            confusion[(s1, s2)] += 1
            if s1 != s2:
                record = record_by_id.get(record_id)
                conflicts.append({
                    "record_id": record_id,
                    "title": record.title if record else "",
                    f"{reviewer_1}": s1,
                    f"{reviewer_2}": s2,
                    f"{reviewer_1}_reason": d1.notes,
                    f"{reviewer_2}_reason": d2.notes,
                })

        report = AgreementReport(reviewer_1=reviewer_1, reviewer_2=reviewer_2)
        report.n_both_screened = len(labels_1)
        report.n_agree = sum(1 for a, b in zip(labels_1, labels_2) if a == b)
        report.confusion = dict(confusion)
        report.conflicts = conflicts
        if report.n_both_screened:
            report.percent_agreement = 100.0 * report.n_agree / report.n_both_screened
            report.kappa = cohens_kappa(labels_1, labels_2)
        return report

    def export_agreement(self, report: AgreementReport, out_dir: Path):
        """Write agreement_summary.md and conflicts.csv for a two-reviewer report."""
        out_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Inter-reviewer agreement",
            "",
            f"- Reviewers: {report.reviewer_1} vs {report.reviewer_2}",
            f"- Records screened by both: {report.n_both_screened}",
            f"- Absolute agreement: {report.n_agree} ({report.percent_agreement:.1f}%)",
            f"- Cohen's kappa: {report.kappa:.4f}",
            f"- Conflicts: {len(report.conflicts)}",
            "",
            "## Confusion matrix",
            "",
        ]
        states = sorted({s for pair in report.confusion for s in pair})
        lines.append("| R1 \\ R2 | " + " | ".join(states) + " |")
        lines.append("|---" * (len(states) + 1) + "|")
        for s1 in states:
            lines.append(f"| {s1} | " + " | ".join(str(report.confusion.get((s1, s2), 0)) for s2 in states) + " |")
        (out_dir / "agreement_summary.md").write_text("\n".join(lines) + "\n")

        if report.conflicts:
            keys = ["record_id", "title", report.reviewer_1, report.reviewer_2,
                    f"{report.reviewer_1}_reason", f"{report.reviewer_2}_reason"]
            with (out_dir / "conflicts.csv").open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=keys)
                writer.writeheader()
                writer.writerows(report.conflicts)
        else:
            (out_dir / "conflicts.csv").write_text("record_id,title,reviewer_1,reviewer_2\n")

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


@dataclass
class AgreementReport:
    """Inter-rater agreement statistics for two reviewers."""
    reviewer_1: str = ""
    reviewer_2: str = ""
    n_both_screened: int = 0
    n_agree: int = 0
    kappa: float = 0.0
    percent_agreement: float = 0.0
    confusion: dict = field(default_factory=dict)  # (state1, state2) -> count
    conflicts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "reviewer_1": self.reviewer_1,
            "reviewer_2": self.reviewer_2,
            "n_both_screened": self.n_both_screened,
            "n_agree": self.n_agree,
            "kappa": round(self.kappa, 4),
            "percent_agreement": round(self.percent_agreement, 2),
            "confusion": {f"{a}|{b}": n for (a, b), n in self.confusion.items()},
            "n_conflicts": len(self.conflicts),
            "conflicts": self.conflicts,
        }


def cohens_kappa(labels_1: list[str], labels_2: list[str]) -> float:
    """Cohen's kappa for two equal-length lists of categorical labels."""
    if len(labels_1) != len(labels_2) or not labels_1:
        raise ValueError("label lists must be equal length and non-empty")
    n = len(labels_1)
    po = sum(1 for a, b in zip(labels_1, labels_2) if a == b) / n
    categories = sorted(set(labels_1) | set(labels_2))
    pe = 0.0
    for cat in categories:
        p1 = sum(1 for a in labels_1 if a == cat) / n
        p2 = sum(1 for b in labels_2 if b == cat) / n
        pe += p1 * p2
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


def first_author_surname(authors: list[str]) -> Optional[str]:
    if not authors:
        return None
    name = authors[0].strip()
    if "," in name:
        return name.split(",")[0].strip()
    parts = name.split()
    return parts[-1] if parts else None