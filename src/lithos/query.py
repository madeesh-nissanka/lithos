# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Query building, translation, and search profiles for LITHOS.
"""
from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from lithos.models import SearchQuery, Record

logger = logging.getLogger(__name__)


@dataclass
class SynonymGroup:
    """A group of synonymous terms."""
    canonical: str
    synonyms: list[str]

    def expand(self, term: str) -> list[str]:
        """Return all terms if term matches canonical or any synonym."""
        term_lower = term.lower()
        if term_lower == self.canonical.lower() or term_lower in [s.lower() for s in self.synonyms]:
            return [self.canonical] + self.synonyms
        return [term]


class SynonymExpander:
    """Manages synonym groups and expands queries."""

    def __init__(self, synonym_groups: Optional[list[SynonymGroup]] = None):
        self.groups = synonym_groups or []
        self._term_to_group: dict[str, SynonymGroup] = {}
        for group in self.groups:
            self._term_to_group[group.canonical.lower()] = group
            for syn in group.synonyms:
                self._term_to_group[syn.lower()] = group

    def add_group(self, group: SynonymGroup):
        self.groups.append(group)
        self._term_to_group[group.canonical.lower()] = group
        for syn in group.synonyms:
            self._term_to_group[syn.lower()] = group

    def load_from_file(self, path: Path):
        """Load synonym groups from JSON file."""
        with path.open() as f:
            data = json.load(f)
        for item in data:
            self.add_group(SynonymGroup(canonical=item["canonical"], synonyms=item.get("synonyms", [])))

    def expand_term(self, term: str) -> list[str]:
        """Expand a single term using synonym groups."""
        group = self._term_to_group.get(term.lower())
        if group:
            return [group.canonical] + group.synonyms
        return [term]

    def expand_query(self, query: str) -> str:
        """Expand all terms in a query string."""
        # Simple approach: find quoted phrases and terms
        # This is a basic implementation; could be enhanced with proper parsing
        tokens = re.findall(r'"[^"]+"|\S+', query)
        expanded_tokens = []
        for token in tokens:
            if token.startswith('"') and token.endswith('"'):
                # Quoted phrase - don't expand inside
                expanded_tokens.append(token)
            elif token.upper() in ("AND", "OR", "NOT", "(", ")"):
                expanded_tokens.append(token)
            else:
                expanded = self.expand_term(token)
                if len(expanded) > 1:
                    expanded_tokens.append(f"({' OR '.join(expanded)})")
                else:
                    expanded_tokens.append(expanded[0])
        return " ".join(expanded_tokens)


class QueryBuilder:
    """Builds structured boolean queries with field-specific syntax."""

    def __init__(self):
        self.terms: list[dict] = []
        self.boolean_operator = "AND"

    def add_term(self, term: str, field: Optional[str] = None, operator: str = "AND", fuzzy: bool = False) -> QueryBuilder:
        """Add a search term."""
        self.terms.append({
            "term": term,
            "field": field,
            "operator": operator,
            "fuzzy": fuzzy,
        })
        return self

    def add_phrase(self, phrase: str, field: Optional[str] = None, operator: str = "AND") -> QueryBuilder:
        """Add a quoted phrase."""
        self.terms.append({
            "term": f'"{phrase}"',
            "field": field,
            "operator": operator,
            "fuzzy": False,
        })
        return self

    def add_year_range(self, from_year: Optional[int] = None, to_year: Optional[int] = None, operator: str = "AND") -> QueryBuilder:
        """Add year range filter."""
        if from_year and to_year:
            self.terms.append({"term": f"year:[{from_year} TO {to_year}]", "field": None, "operator": operator, "fuzzy": False})
        elif from_year:
            self.terms.append({"term": f"year:[{from_year} TO *]", "field": None, "operator": operator, "fuzzy": False})
        elif to_year:
            self.terms.append({"term": f"year:[* TO {to_year}]", "field": None, "operator": operator, "fuzzy": False})
        return self

    def add_type_filter(self, pub_type: str, operator: str = "AND") -> QueryBuilder:
        """Add publication type filter."""
        self.terms.append({"term": f"type:{pub_type}", "field": None, "operator": operator, "fuzzy": False})
        return self

    def build(self) -> str:
        """Build the final query string."""
        if not self.terms:
            return ""

        parts = []
        for i, t in enumerate(self.terms):
            term_str = t["term"]
            if t["field"]:
                term_str = f"{t['field']}:{term_str}"
            if i == 0:
                parts.append(term_str)
            else:
                parts.append(f"{t['operator']} {term_str}")
        return " ".join(parts)

    def to_search_query(self, original: str = "") -> SearchQuery:
        """Convert to SearchQuery object."""
        return SearchQuery(
            original=original or self.build(),
            boolean_query=self.build(),
        )


@dataclass
class SearchProfile:
    """Saved search profile with queries and settings."""
    name: str
    description: str = ""
    queries: list[SearchQuery] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # Empty = all enabled
    filters: dict[str, Any] = field(default_factory=dict)
    deduplicate: bool = True
    validate: bool = True
    screen: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "queries": [q.__dict__ for q in self.queries],
            "sources": self.sources,
            "filters": self.filters,
            "deduplicate": self.deduplicate,
            "validate": self.validate,
            "screen": self.screen,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SearchProfile:
        queries = [SearchQuery(**q) for q in data.get("queries", [])]
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            queries=queries,
            sources=data.get("sources", []),
            filters=data.get("filters", {}),
            deduplicate=data.get("deduplicate", True),
            validate=data.get("validate", True),
            screen=data.get("screen", False),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def save(self, path: Path):
        """Save profile to JSON file."""
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> SearchProfile:
        """Load profile from JSON file."""
        return cls.from_dict(json.loads(path.read_text()))


class SearchLogger:
    """PRISMA-S compliant search logging."""

    def __init__(self):
        self.entries: list[dict] = []

    def log_search(self, source: str, query: SearchQuery, result: Any, timestamp: Optional[str] = None):
        """Log a search operation."""
        entry = {
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "source": source,
            "query_original": query.original,
            "query_boolean": query.boolean_query,
            "query_synonyms": query.synonyms,
            "query_translated": query.source_translations.get(source, ""),
            "filters": query.filters,
            "total_hits": getattr(result, "total_hits", 0),
            "records_retrieved": len(getattr(result, "records", [])),
            "duration_seconds": getattr(result, "duration_seconds", 0),
            "errors": getattr(result, "errors", []),
        }
        self.entries.append(entry)

    def log_deduplication(self, before: int, after: int, method: str, clusters: int):
        """Log deduplication step."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": "deduplication",
            "method": method,
            "records_before": before,
            "records_after": after,
            "duplicates_removed": before - after,
            "clusters": clusters,
        }
        self.entries.append(entry)

    def log_validation(self, validated: int, warnings: int, errors: int, retractions: int):
        """Log validation step."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": "validation",
            "validated": validated,
            "with_warnings": warnings,
            "errors": errors,
            "retracted": retractions,
        }
        self.entries.append(entry)

    def log_screening(self, included: int, excluded: int, conflicts: int, unscreened: int):
        """Log screening step."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": "screening",
            "included": included,
            "excluded": excluded,
            "conflicts": conflicts,
            "unscreened": unscreened,
        }
        self.entries.append(entry)

    def export_prisma_s(self, path: Path):
        """Export search log in PRISMA-S format (markdown table)."""
        lines = ["# PRISMA-S Search Log\n"]
        lines.append("| Timestamp | Source | Query | Hits | Retrieved | Duration (s) | Errors |\n")
        lines.append("|---|---|---|---|---|---|---|\n")
        for e in self.entries:
            if e.get("step") in ("deduplication", "validation", "screening"):
                continue
            query = e.get("query_translated") or e.get("query_boolean") or e.get("query_original", "")
            query = query[:100].replace("|", "\\|")
            lines.append(f"| {e['timestamp']} | {e['source']} | {query} | {e['total_hits']} | {e['records_retrieved']} | {e['duration_seconds']:.1f} | {'; '.join(e['errors']) if e['errors'] else ''} |\n")

        lines.append("\n## Processing Steps\n")
        for e in self.entries:
            if e.get("step") == "deduplication":
                lines.append(f"- **Deduplication** ({e['method']}): {e['records_before']} → {e['records_after']} records ({e['duplicates_removed']} duplicates removed, {e['clusters']} clusters)\n")
            elif e.get("step") == "validation":
                lines.append(f"- **Validation**: {e['validated']} validated, {e['with_warnings']} with warnings, {e['errors']} errors, {e['retracted']} retracted\n")
            elif e.get("step") == "screening":
                lines.append(f"- **Screening**: {e['included']} included, {e['excluded']} excluded, {e['conflicts']} conflicts, {e['unscreened']} unscreened\n")

        path.write_text("\n".join(lines))

    def export_json(self, path: Path):
        """Export full search log as JSON."""
        path.write_text(json.dumps(self.entries, indent=2))