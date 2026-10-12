# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Validation module for LITHOS - DOI validation, retraction checking, predatory venue detection, completeness scoring.
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lithos.adapters import get_adapter
from lithos.adapters_crossref import CrossrefAdapter
from lithos.models import Record, RecordStatus, ValidationResult

logger = logging.getLogger(__name__)


def _load_packaged_predatory_list(filename: str) -> list[str]:
    """Load a curated, sourced venue list shipped in the package."""
    path = Path(__file__).resolve().parent / "data" / filename
    if not path.exists():
        return []
    return [
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


# Default predatory venue list: curated snapshot of Beall's List (archived mirror),
# shipped in src/lithos/data/*.txt with source/commit/retrieval notes in the file header.
# Override with --predatory-list / ValidationConfig.predatory_venue_list.
DEFAULT_PREDATORY_FILES = [
    "bealls_publishers_2016.txt",
    "bealls_standalone_journals_2017.txt",
]
DEFAULT_PREDATORY_VENUES = sorted(
    {entry for f in DEFAULT_PREDATORY_FILES for entry in _load_packaged_predatory_list(f)}
)


@dataclass
class ValidationConfig:
    """Configuration for validation."""
    check_crossref: bool = True
    check_retraction: bool = True
    check_correction: bool = True
    check_preprint_match: bool = True
    check_predatory: bool = True
    predatory_venue_list: list[str] = None
    title_similarity_threshold: float = 0.90
    year_tolerance: int = 1
    completeness_weights: dict = None

    def __post_init__(self):
        if self.predatory_venue_list is None:
            self.predatory_venue_list = DEFAULT_PREDATORY_VENUES
        if self.completeness_weights is None:
            self.completeness_weights = {
                "has_doi": 0.25,
                "has_abstract": 0.20,
                "has_authors": 0.15,
                "has_venue": 0.15,
                "has_year": 0.10,
                "has_keywords": 0.10,
                "has_citations": 0.05,
            }


def validate_record(record: Record, config: Optional[ValidationConfig] = None) -> ValidationResult:
    """
    Validate a record against Crossref and other checks.
    Updates the record in place and returns ValidationResult.
    """
    config = config or ValidationConfig()
    flags = []
    crossref_data = {}

    # Check DOI
    doi = record.doi
    if not doi:
        record.status = RecordStatus.NO_DOI
        record.flags = ["no_doi"]
        return ValidationResult(record_id=record.id, status=RecordStatus.NO_DOI, flags=["no_doi"])

    # Crossref validation
    if config.check_crossref:
        cr_adapter = get_adapter("crossref")
        if cr_adapter and isinstance(cr_adapter, CrossrefAdapter):
            cr_result = cr_adapter.validate_doi(doi)
            if not cr_result["ok"]:
                if cr_result["error"] == "not_found" or "404" in str(cr_result.get("error", "")):
                    record.status = RecordStatus.NOT_FOUND_IN_CROSSREF
                    record.flags = ["not_found_in_crossref"]
                    return ValidationResult(record_id=record.id, status=RecordStatus.NOT_FOUND_IN_CROSSREF, flags=["not_found_in_crossref"])
                else:
                    record.status = RecordStatus.CROSSREF_UNREACHABLE
                    record.flags = ["crossref_unreachable"]
                    return ValidationResult(record_id=record.id, status=RecordStatus.CROSSREF_UNREACHABLE, flags=["crossref_unreachable"])

            crossref_data = cr_result["data"]
            record.crossref_data = crossref_data

            # Check retraction
            if config.check_retraction and cr_adapter.check_retraction(crossref_data):
                record.status = RecordStatus.RETRACTED
                record.flags = ["retracted"]
                return ValidationResult(record_id=record.id, status=RecordStatus.RETRACTED, flags=["retracted"], crossref_data=crossref_data)

            # Check correction
            if config.check_correction and cr_adapter.check_correction(crossref_data):
                flags.append("has_correction")

            # Title similarity
            cr_title = (crossref_data.get("title") or [""])[0]
            sim = title_similarity(record.title, cr_title)
            if sim >= config.title_similarity_threshold:
                pass
            else:
                flags.append("title_mismatch")

            # Year check
            cr_year = None
            issued = crossref_data.get("issued", {})
            dp = issued.get("date-parts", [])
            if dp and dp[0]:
                cr_year = dp[0][0]
            rec_year = record.year
            if cr_year and rec_year:
                if cr_year == rec_year:
                    pass
                elif abs(cr_year - rec_year) <= config.year_tolerance:
                    flags.append("year_off_by_one")
                else:
                    flags.append("year_mismatch")

            # Author check
            cr_authors = crossref_data.get("author", [])
            cr_surnames = [a.get("family", "") for a in cr_authors if a.get("family")]
            rec_first_surname = first_author_surname(record.authors)
            if rec_first_surname:
                if rec_first_surname in cr_surnames:
                    if cr_surnames and cr_surnames[0] != rec_first_surname:
                        flags.append("author_order_differs")
                else:
                    flags.append("author_mismatch")

            # Preprint to published matching
            if config.check_preprint_match:
                published_doi = cr_adapter.get_preprint_relation(crossref_data)
                if published_doi and published_doi.lower() != doi.lower():
                    record.status = RecordStatus.PREPRINT_MATCHED
                    flags.append(f"preprint_of:{published_doi}")
                    # Could fetch the published version here

    # Predatory venue check
    if config.check_predatory and record.venue:
        venue_lower = record.venue.lower()
        for predatory in config.predatory_venue_list:
            if predatory in venue_lower:
                if record.status not in (RecordStatus.RETRACTED, RecordStatus.NOT_FOUND_IN_CROSSREF):
                    record.status = RecordStatus.PREDATORY_VENUE
                flags.append("predatory_venue")
                break

    # Completeness score
    record.completeness_score = compute_completeness_score(record, config.completeness_weights)

    # Determine final status
    if record.status in (RecordStatus.RETRACTED, RecordStatus.NOT_FOUND_IN_CROSSREF, RecordStatus.CROSSREF_UNREACHABLE, RecordStatus.PREDATORY_VENUE):
        pass  # Keep existing status
    elif flags:
        record.status = RecordStatus.VALIDATED_WITH_WARNINGS
    else:
        record.status = RecordStatus.VALIDATED

    record.flags = flags
    return ValidationResult(
        record_id=record.id,
        status=record.status,
        flags=flags,
        crossref_data=crossref_data,
    )


def compute_completeness_score(record: Record, weights: dict) -> float:
    """Compute metadata completeness score (0-1)."""
    score = 0.0
    if record.doi:
        score += weights.get("has_doi", 0.25)
    if record.abstract and len(record.abstract) > 50:
        score += weights.get("has_abstract", 0.20)
    if record.authors:
        score += weights.get("has_authors", 0.15)
    if record.venue:
        score += weights.get("has_venue", 0.15)
    if record.year:
        score += weights.get("has_year", 0.10)
    if record.keywords:
        score += weights.get("has_keywords", 0.10)
    if record.cited_by is not None and record.cited_by > 0:
        score += weights.get("has_citations", 0.05)
    return round(min(score, 1.0), 3)


def first_author_surname(authors: list[str]) -> Optional[str]:
    """Get normalized surname of first author."""
    if not authors:
        return None
    name = authors[0].strip()
    if "," in name:
        return name.split(",")[0].strip().lower()
    parts = name.split()
    return parts[-1].lower() if parts else None


def title_similarity(a: str, b: str) -> float:
    """Calculate title similarity."""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def load_predatory_list(path: Path) -> list[str]:
    """Load predatory venue list from file (one per line)."""
    if not path.exists():
        return DEFAULT_PREDATORY_VENUES
    with path.open() as f:
        return [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]


def check_retraction(crossref_data: dict) -> bool:
    """Check if a work has been retracted (standalone function)."""
    for item in crossref_data.get("update-to", []):
        if item.get("type") in ("retraction", "withdrawal"):
            return True
    return False