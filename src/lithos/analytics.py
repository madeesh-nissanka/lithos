# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Analytics module for LITHOS - publication trends, top venues/authors/countries, keyword co-occurrence, topic clusters.
"""
from __future__ import annotations
import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from lithos.models import Record, AnalyticsResult

logger = logging.getLogger(__name__)


@dataclass
class TrendData:
    """Publication trend data point."""
    year: int
    count: int
    cumulative: int = 0


@dataclass
class TopItems:
    """Top N items with counts."""
    items: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class KeywordCooccurrence:
    """Keyword co-occurrence matrix."""
    keywords: list[str] = field(default_factory=list)
    matrix: list[list[int]] = field(default_factory=list)  # symmetric matrix

    def to_dict(self) -> dict:
        return {"keywords": self.keywords, "matrix": self.matrix}


def compute_analytics(records: list[Record], top_n: int = 20) -> AnalyticsResult:
    """Compute all analytics on a set of records."""
    if not records:
        return AnalyticsResult()

    # Publication trends by year
    year_counts = Counter(r.year for r in records if r.year)
    years = sorted(year_counts.keys())
    trends = []
    cumulative = 0
    for year in years:
        cumulative += year_counts[year]
        trends.append(TrendData(year=year, count=year_counts[year], cumulative=cumulative))

    # Top venues
    venue_counts = Counter(r.venue for r in records if r.venue)
    top_venues = venue_counts.most_common(top_n)

    # Top authors
    author_counts = Counter()
    for r in records:
        for author in r.authors:
            author_counts[author] += 1
    top_authors = author_counts.most_common(top_n)

    # Top countries (from venue names - approximate)
    country_counts = Counter()
    for r in records:
        if r.venue:
            # Simple heuristic: look for country names in venue
            pass  # Would need affiliation data for accurate country analysis

    # Keyword co-occurrence
    kw_counts = Counter()
    for r in records:
        for kw in r.keywords:
            kw_counts[kw.lower()] += 1
    top_keywords = [kw for kw, _ in kw_counts.most_common(top_n)]

    # Build co-occurrence matrix
    kw_to_idx = {kw: i for i, kw in enumerate(top_keywords)}
    matrix = [[0] * len(top_keywords) for _ in range(len(top_keywords))]

    for r in records:
        record_kws = [kw.lower() for kw in r.keywords if kw.lower() in kw_to_idx]
        for i, kw1 in enumerate(record_kws):
            idx1 = kw_to_idx[kw1]
            matrix[idx1][idx1] += 1
            for kw2 in record_kws[i+1:]:
                idx2 = kw_to_idx[kw2]
                matrix[idx1][idx2] += 1
                matrix[idx2][idx1] += 1

    cooccurrence = KeywordCooccurrence(keywords=top_keywords, matrix=matrix)

    # Simple topic clusters via keyword co-occurrence (connected components)
    clusters = _find_keyword_clusters(top_keywords, matrix, min_cooccurrence=2)

    # Publication types
    type_counts = Counter(r.publication_type for r in records if r.publication_type)

    # Sources
    source_counts = Counter(r.source for r in records)

    # Open access status (from Unpaywall data in crossref_data)
    oa_status = Counter()
    for r in records:
        upw = r.crossref_data.get("unpaywall", {})
        if upw:
            oa_status[upw.get("oa_status", "unknown")] += 1
        elif r.doi:
            oa_status["unknown"] += 1

    return AnalyticsResult(
        trends=trends,
        top_venues=top_venues,
        top_authors=top_authors,
        top_keywords=kw_counts.most_common(top_n),
        keyword_cooccurrence=cooccurrence,
        topic_clusters=clusters,
        publication_types=dict(type_counts),
        sources=dict(source_counts),
        open_access_status=dict(oa_status),
    )


def _find_keyword_clusters(keywords: list[str], matrix: list[list[int]], min_cooccurrence: int = 2) -> list[list[str]]:
    """Find keyword clusters using simple connected components on co-occurrence graph."""
    n = len(keywords)
    visited = [False] * n
    clusters = []

    def dfs(node: int, cluster: list[int]):
        visited[node] = True
        cluster.append(node)
        for neighbor in range(n):
            if not visited[neighbor] and matrix[node][neighbor] >= min_cooccurrence:
                dfs(neighbor, cluster)

    for i in range(n):
        if not visited[i]:
            cluster = []
            dfs(i, cluster)
            if len(cluster) > 1:  # Only keep clusters with multiple keywords
                clusters.append([keywords[idx] for idx in cluster])

    return clusters


def export_analytics(analytics: AnalyticsResult, output_dir: Path) -> dict[str, Path]:
    """Export analytics tables as CSV/JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    # Trends
    import csv
    trends_path = output_dir / "analytics_trends.csv"
    with trends_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "count", "cumulative"])
        for t in analytics.trends:
            writer.writerow([t.year, t.count, t.cumulative])
    paths["trends"] = trends_path

    # Top venues
    venues_path = output_dir / "analytics_top_venues.csv"
    with venues_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["venue", "count"])
        for venue, count in analytics.top_venues:
            writer.writerow([venue, count])
    paths["top_venues"] = venues_path

    # Top authors
    authors_path = output_dir / "analytics_top_authors.csv"
    with authors_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["author", "count"])
        for author, count in analytics.top_authors:
            writer.writerow([author, count])
    paths["top_authors"] = authors_path

    # Top keywords
    keywords_path = output_dir / "analytics_top_keywords.csv"
    with keywords_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["keyword", "count"])
        for kw, count in analytics.top_keywords:
            writer.writerow([kw, count])
    paths["top_keywords"] = keywords_path

    # Keyword co-occurrence (as JSON for matrix)
    coocc_path = output_dir / "analytics_keyword_cooccurrence.json"
    coocc_path.write_text(json.dumps(analytics.keyword_cooccurrence.to_dict(), indent=2))
    paths["keyword_cooccurrence"] = coocc_path

    # Topic clusters
    clusters_path = output_dir / "analytics_topic_clusters.json"
    clusters_path.write_text(json.dumps(analytics.topic_clusters, indent=2))
    paths["topic_clusters"] = clusters_path

    # Publication types
    types_path = output_dir / "analytics_publication_types.csv"
    with types_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["type", "count"])
        for ptype, count in analytics.publication_types.items():
            writer.writerow([ptype, count])
    paths["publication_types"] = types_path

    # Sources
    sources_path = output_dir / "analytics_sources.csv"
    with sources_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "count"])
        for source, count in analytics.sources.items():
            writer.writerow([source, count])
    paths["sources"] = sources_path

    # Open access
    oa_path = output_dir / "analytics_open_access.csv"
    with oa_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["oa_status", "count"])
        for status, count in analytics.open_access_status.items():
            writer.writerow([status, count])
    paths["open_access"] = oa_path

    return paths


def plot_trends(analytics: AnalyticsResult, output_path: Path, title: str = "Publication Trends"):
    """Plot publication trends (requires matplotlib)."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib required for plotting. Install with: pip install matplotlib")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not analytics.trends:
        return

    years = [t.year for t in analytics.trends]
    counts = [t.count for t in analytics.trends]
    cumulative = [t.cumulative for t in analytics.trends]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    color = 'tab:blue'
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Annual Count', color=color)
    ax1.bar(years, counts, color=color, alpha=0.7, label='Annual')
    ax1.tick_params(axis='y', labelcolor=color)

    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Cumulative Count', color=color)
    ax2.plot(years, cumulative, color=color, marker='o', label='Cumulative')
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title(title)
    fig.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def plot_top_venues(analytics: AnalyticsResult, output_path: Path, top_n: int = 15, title: str = "Top Venues"):
    """Plot top venues (requires matplotlib)."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib required for plotting. Install with: pip install matplotlib")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not analytics.top_venues:
        return

    venues = [v[0][:50] for v in analytics.top_venues[:top_n]]
    counts = [v[1] for v in analytics.top_venues[:top_n]]

    fig, ax = plt.subplots(figsize=(10, max(6, len(venues) * 0.4)))
    y_pos = range(len(venues))
    ax.barh(y_pos, counts, align='center', color='tab:blue', alpha=0.7)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(venues)
    ax.invert_yaxis()
    ax.set_xlabel('Count')
    ax.set_title(title)
    fig.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()