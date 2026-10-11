# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Core data models for LITHOS.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import hashlib
import json


class RecordStatus(str, Enum):
    """Validation status of a record."""
    VALIDATED = "VALIDATED"
    VALIDATED_WITH_WARNINGS = "VALIDATED_WITH_WARNINGS"
    NO_DOI = "NO_DOI"
    NOT_FOUND_IN_CROSSREF = "NOT_FOUND_IN_CROSSREF"
    CROSSREF_UNREACHABLE = "CROSSREF_UNREACHABLE"
    RETRACTED = "RETRACTED"
    PREDATORY_VENUE = "PREDATORY_VENUE"
    PREPRINT = "PREPRINT"
    PREPRINT_MATCHED = "PREPRINT_MATCHED"


class ScreenState(str, Enum):
    """Screening decision state."""
    UNSCREENED = "UNSCREENED"
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    CONFLICT = "CONFLICT"


@dataclass
class ScreenDecision:
    """A single reviewer's screening decision on one record."""
    reviewer: str = ""
    decision: ScreenState = ScreenState.UNSCREENED
    notes: str = ""
    decided_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Record:
    """A bibliographic record with metadata and tracking fields."""
    # Core identifiers
    id: str = ""  # Internal unique ID
    openalex_id: Optional[str] = None
    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    arxiv_id: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    core_id: Optional[str] = None

    # Bibliographic metadata
    title: str = ""
    year: Optional[int] = None
    authors: list[str] = field(default_factory=list)
    venue: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    publication_type: Optional[str] = None  # journal-article, preprint, conference, etc.

    # Metrics
    cited_by: Optional[int] = None
    referenced_works: list[str] = field(default_factory=list)  # DOIs of references
    citing_works: list[str] = field(default_factory=list)  # DOIs of citing works

    # Source tracking
    source: str = ""  # Which adapter found this record
    query_hits: list[str] = field(default_factory=list)  # Which queries matched

    # Validation
    status: RecordStatus = RecordStatus.NO_DOI
    flags: list[str] = field(default_factory=list)
    crossref_data: dict = field(default_factory=dict)
    completeness_score: float = 0.0

    # Screening
    screen_state: ScreenState = ScreenState.UNSCREENED
    screen_notes: str = ""
    reviewer_decisions: dict[str, ScreenState] = field(default_factory=dict)  # reviewer -> decision

    # Deduplication
    dedup_cluster_id: Optional[str] = None
    dedup_master: bool = False

    # Provenance
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    retrieved_by: str = ""  # adapter name
    content_hash: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
        if not self.content_hash:
            self.content_hash = self._compute_hash()

    def _generate_id(self) -> str:
        """Generate a unique ID based on available identifiers."""
        parts = []
        if self.doi:
            parts.append(f"doi:{self.doi.lower()}")
        elif self.pmid:
            parts.append(f"pmid:{self.pmid}")
        elif self.arxiv_id:
            parts.append(f"arxiv:{self.arxiv_id}")
        elif self.openalex_id:
            parts.append(f"oa:{self.openalex_id}")
        elif self.semantic_scholar_id:
            parts.append(f"s2:{self.semantic_scholar_id}")
        elif self.core_id:
            parts.append(f"core:{self.core_id}")
        elif self.pmcid:
            parts.append(f"pmcid:{self.pmcid}")
        else:
            parts.append(f"title:{hashlib.md5(self.title.encode()).hexdigest()[:12]}")
        return "|".join(parts)

    def _compute_hash(self) -> str:
        """Compute content hash for change detection."""
        content = f"{self.title}|{self.year}|{'|'.join(self.authors)}|{self.venue}|{self.abstract}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "openalex_id": self.openalex_id,
            "doi": self.doi,
            "pmid": self.pmid,
            "pmcid": self.pmcid,
            "arxiv_id": self.arxiv_id,
            "semantic_scholar_id": self.semantic_scholar_id,
            "core_id": self.core_id,
            "title": self.title,
            "year": self.year,
            "authors": self.authors,
            "venue": self.venue,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "publication_type": self.publication_type,
            "cited_by": self.cited_by,
            "referenced_works": self.referenced_works,
            "citing_works": self.citing_works,
            "source": self.source,
            "query_hits": self.query_hits,
            "status": self.status.value,
            "flags": self.flags,
            "crossref_data": self.crossref_data,
            "completeness_score": self.completeness_score,
            "screen_state": self.screen_state.value,
            "screen_notes": self.screen_notes,
            "reviewer_decisions": {k: v.value for k, v in self.reviewer_decisions.items()},
            "dedup_cluster_id": self.dedup_cluster_id,
            "dedup_master": self.dedup_master,
            "retrieved_at": self.retrieved_at,
            "retrieved_by": self.retrieved_by,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Record:
        """Create Record from dictionary."""
        record = cls(
            id=data.get("id", ""),
            openalex_id=data.get("openalex_id"),
            doi=data.get("doi"),
            pmid=data.get("pmid"),
            pmcid=data.get("pmcid"),
            arxiv_id=data.get("arxiv_id"),
            semantic_scholar_id=data.get("semantic_scholar_id"),
            core_id=data.get("core_id"),
            title=data.get("title", ""),
            year=data.get("year"),
            authors=data.get("authors", []),
            venue=data.get("venue"),
            volume=data.get("volume"),
            issue=data.get("issue"),
            pages=data.get("pages"),
            abstract=data.get("abstract", ""),
            keywords=data.get("keywords", []),
            publication_type=data.get("publication_type"),
            cited_by=data.get("cited_by"),
            referenced_works=data.get("referenced_works", []),
            citing_works=data.get("citing_works", []),
            source=data.get("source", ""),
            query_hits=data.get("query_hits", []),
            status=RecordStatus(data.get("status", "NO_DOI")),
            flags=data.get("flags", []),
            crossref_data=data.get("crossref_data", {}),
            completeness_score=data.get("completeness_score", 0.0),
            screen_state=ScreenState(data.get("screen_state", "UNSCREENED")),
            screen_notes=data.get("screen_notes", ""),
            reviewer_decisions={k: ScreenState(v) for k, v in data.get("reviewer_decisions", {}).items()},
            dedup_cluster_id=data.get("dedup_cluster_id"),
            dedup_master=data.get("dedup_master", False),
            retrieved_at=data.get("retrieved_at", ""),
            retrieved_by=data.get("retrieved_by", ""),
            content_hash=data.get("content_hash", ""),
        )
        if not record.id:
            record.id = record._generate_id()
        if not record.content_hash:
            record.content_hash = record._compute_hash()
        return record


@dataclass
class SearchQuery:
    """A structured search query with boolean logic and source-specific translations."""
    original: str = ""
    boolean_query: str = ""
    synonyms: dict[str, list[str]] = field(default_factory=dict)
    source_translations: dict[str, str] = field(default_factory=dict)
    filters: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class SearchResult:
    """Result of a search operation."""
    query: SearchQuery
    records: list[Record] = field(default_factory=list)
    total_hits: int = 0
    source: str = ""
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of validating a record."""
    record_id: str
    status: RecordStatus
    flags: list[str]
    crossref_data: dict = field(default_factory=dict)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DedupCluster:
    """A cluster of duplicate records."""
    cluster_id: str
    master_record: Record
    duplicates: list[Record] = field(default_factory=list)
    match_reasons: list[str] = field(default_factory=list)  # doi, title, fuzzy, etc.


@dataclass
class AnalyticsResult:
    """Container for computed analytics tables."""
    trends: list = field(default_factory=list)
    top_venues: list = field(default_factory=list)
    top_authors: list = field(default_factory=list)
    top_keywords: list = field(default_factory=list)
    keyword_cooccurrence: Any = None
    topic_clusters: list = field(default_factory=list)
    publication_types: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    open_access_status: dict = field(default_factory=dict)


@dataclass
class RunManifest:
    """Manifest of a complete run for reproducibility."""
    run_id: str
    lithos_version: str = "0.2.0"
    python_version: str = ""
    started_at: str = ""
    completed_at: Optional[str] = None
    config_hash: str = ""
    parameters: dict = field(default_factory=dict)
    queries: list[SearchQuery] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    total_records_found: int = 0
    total_records_after_dedup: int = 0
    validation_summary: dict[str, int] = field(default_factory=dict)
    output_hashes: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, default=str)


@dataclass
class RunLedger:
    """Ledger of record changes between runs."""
    run_id: str
    previous_run_id: Optional[str] = None
    unchanged: list[str] = field(default_factory=list)  # record IDs
    new: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)