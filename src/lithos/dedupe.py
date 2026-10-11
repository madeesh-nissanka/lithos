# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Deduplication module for LITHOS.
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

from lithos.models import Record, DedupCluster

logger = logging.getLogger(__name__)


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    if not title:
        return ""
    # Lowercase, remove punctuation, collapse whitespace
    title = title.lower()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def normalize_author(name: str) -> str:
    """Normalize author name for comparison."""
    if not name:
        return ""
    # Extract surname
    name = name.strip()
    if "," in name:
        surname = name.split(",")[0].strip()
    else:
        parts = name.split()
        surname = parts[-1] if parts else ""
    return surname.lower()


def first_author_surname(authors: list[str]) -> Optional[str]:
    """Get normalized surname of first author."""
    if not authors:
        return None
    return normalize_author(authors[0])


def title_similarity(a: str, b: str) -> float:
    """Calculate title similarity using SequenceMatcher."""
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def fuzzy_match(record1: Record, record2: Record, threshold: float = 0.85) -> bool:
    """Check if two records match via fuzzy title + year + first author."""
    # Title similarity
    sim = title_similarity(record1.title, record2.title)
    if sim < threshold:
        return False

    # Year match (exact or off by 1)
    y1, y2 = record1.year, record2.year
    if y1 and y2:
        if abs(y1 - y2) > 1:
            return False

    # First author surname match
    a1 = first_author_surname(record1.authors)
    a2 = first_author_surname(record2.authors)
    if a1 and a2 and a1 != a2:
        return False

    return True


def deduplicate(
    records: list[Record],
    doi_threshold: float = 1.0,
    title_threshold: float = 0.95,
    fuzzy_threshold: float = 0.85,
) -> tuple[list[Record], list[DedupCluster]]:
    """
    Deduplicate records using multiple strategies:
    1. Exact DOI match
    2. Normalized title match
    3. Fuzzy title + year + first author match

    Returns deduplicated records (master records only) and list of clusters.
    """
    if not records:
        return [], []

    # Phase 1: DOI-based deduplication
    doi_map: dict[str, Record] = {}
    title_map: dict[str, Record] = {}
    remaining: list[Record] = []

    for record in records:
        doi = (record.doi or "").lower().strip()
        norm_title = normalize_title(record.title)

        if doi and doi in doi_map:
            # Merge query_hits
            master = doi_map[doi]
            master.query_hits.extend(record.query_hits)
            master.query_hits = sorted(set(master.query_hits))
            continue

        if norm_title and norm_title in title_map:
            master = title_map[norm_title]
            master.query_hits.extend(record.query_hits)
            master.query_hits = sorted(set(master.query_hits))
            continue

        if doi:
            doi_map[doi] = record
        if norm_title:
            title_map[norm_title] = record
        remaining.append(record)

    # Phase 2: Fuzzy deduplication on remaining
    clusters: list[DedupCluster] = []
    master_records: list[Record] = []
    processed = set()

    for i, record in enumerate(remaining):
        if i in processed:
            continue

        cluster_id = f"cluster_{len(clusters)}"
        cluster = DedupCluster(cluster_id=cluster_id, master_record=record)
        cluster.match_reasons.append("master")

        for j in range(i + 1, len(remaining)):
            if j in processed:
                continue
            other = remaining[j]

            # Check DOI match (should have been caught in phase 1, but double-check)
            if record.doi and other.doi and record.doi.lower() == other.doi.lower():
                cluster.duplicates.append(other)
                cluster.match_reasons.append("doi")
                processed.add(j)
                continue

            # Check normalized title match
            if normalize_title(record.title) == normalize_title(other.title):
                cluster.duplicates.append(other)
                cluster.match_reasons.append("normalized_title")
                processed.add(j)
                continue

            # Check fuzzy match
            if fuzzy_match(record, other, fuzzy_threshold):
                cluster.duplicates.append(other)
                cluster.match_reasons.append(f"fuzzy_title_year_author_{fuzzy_threshold}")
                processed.add(j)
                continue

        # Mark master
        record.dedup_cluster_id = cluster_id
        record.dedup_master = True
        for dup in cluster.duplicates:
            dup.dedup_cluster_id = cluster_id
            dup.dedup_master = False

        clusters.append(cluster)
        master_records.append(record)
        processed.add(i)

    # Merge query_hits for all records in clusters
    for cluster in clusters:
        all_hits = set(cluster.master_record.query_hits)
        for dup in cluster.duplicates:
            all_hits.update(dup.query_hits)
        merged_hits = sorted(all_hits)
        cluster.master_record.query_hits = merged_hits
        for dup in cluster.duplicates:
            dup.query_hits = merged_hits

    return master_records, clusters


def generate_dedup_report(clusters: list[DedupCluster]) -> str:
    """Generate a human-readable deduplication report."""
    lines = ["# Deduplication Report\n"]
    lines.append(f"Total clusters: {len(clusters)}\n")
    lines.append(f"Total duplicates removed: {sum(len(c.duplicates) for c in clusters)}\n\n")

    for cluster in clusters:
        if not cluster.duplicates:
            continue
        lines.append(f"## Cluster {cluster.cluster_id}\n")
        lines.append(f"**Master**: {cluster.master_record.title[:80]}... ({cluster.master_record.year})\n")
        lines.append(f"  DOI: {cluster.master_record.doi or 'N/A'}\n")
        lines.append(f"  First author: {first_author_surname(cluster.master_record.authors) or 'N/A'}\n")
        lines.append(f"  Match reasons: {', '.join(set(cluster.match_reasons))}\n")
        lines.append(f"  Duplicates ({len(cluster.duplicates)}):\n")
        for dup in cluster.duplicates:
            lines.append(f"  - {dup.title[:80]}... ({dup.year}) DOI: {dup.doi or 'N/A'}\n")
        lines.append("\n")

    return "".join(lines)