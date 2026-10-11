# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.analytics module."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import json
import tempfile
from pathlib import Path
import unittest

from lithos.models import Record
from lithos.analytics import (
    compute_analytics,
    export_analytics,
    TrendData,
    KeywordCooccurrence,
    _find_keyword_clusters,
)


class TestComputeAnalytics(unittest.TestCase):
    """Test compute_analytics function."""

    def setUp(self):
        self.records = [
            Record(
                doi="10.9999/aaa",
                title="Paper 1",
                year=2018,
                authors=["Alpha, A.", "Beta, B."],
                venue="Journal A",
                keywords=["consolidation", "settlement", "clay"],
                publication_type="journal-article",
                source="openalex",
            ),
            Record(
                doi="10.9999/bbb",
                title="Paper 2",
                year=2019,
                authors=["Gamma, G."],
                venue="Journal B",
                keywords=["settlement", "sand"],
                publication_type="journal-article",
                source="openalex",
            ),
            Record(
                doi="10.9999/ccc",
                title="Paper 3",
                year=2019,
                authors=["Delta, D.", "Epsilon, E."],
                venue="Journal A",
                keywords=["consolidation", "clay"],
                publication_type="journal-article",
                source="crossref",
            ),
            Record(
                doi="10.9999/ddd",
                title="Paper 4",
                year=2020,
                authors=["Zeta, Z."],
                venue="Journal C",
                keywords=["pavement", "fatigue"],
                publication_type="conference",
                source="semantic_scholar",
            ),
        ]

    def test_returns_analytics_result(self):
        result = compute_analytics(self.records)
        self.assertIsInstance(result.trends, list)
        self.assertIsInstance(result.top_venues, list)
        self.assertIsInstance(result.top_authors, list)
        self.assertIsInstance(result.top_keywords, list)
        self.assertIsInstance(result.keyword_cooccurrence, KeywordCooccurrence)
        self.assertIsInstance(result.topic_clusters, list)
        self.assertIsInstance(result.publication_types, dict)
        self.assertIsInstance(result.sources, dict)
        self.assertIsInstance(result.open_access_status, dict)

    def test_trends_sorted_by_year(self):
        result = compute_analytics(self.records)
        years = [t.year for t in result.trends]
        self.assertEqual(years, sorted(years))

    def test_trends_cumulative_monotonic(self):
        result = compute_analytics(self.records)
        cumulative = [t.cumulative for t in result.trends]
        for i in range(1, len(cumulative)):
            self.assertGreaterEqual(cumulative[i], cumulative[i-1])

    def test_trends_cumulative_correct(self):
        result = compute_analytics(self.records)
        # 2018: 1, 2019: 2, 2020: 1 -> cumulative: 1, 3, 4
        trend_dict = {t.year: t for t in result.trends}
        self.assertEqual(trend_dict[2018].count, 1)
        self.assertEqual(trend_dict[2018].cumulative, 1)
        self.assertEqual(trend_dict[2019].count, 2)
        self.assertEqual(trend_dict[2019].cumulative, 3)
        self.assertEqual(trend_dict[2020].count, 1)
        self.assertEqual(trend_dict[2020].cumulative, 4)

    def test_top_venues_counts_correct(self):
        result = compute_analytics(self.records)
        venue_dict = dict(result.top_venues)
        self.assertEqual(venue_dict["Journal A"], 2)
        self.assertEqual(venue_dict["Journal B"], 1)
        self.assertEqual(venue_dict["Journal C"], 1)

    def test_top_authors_counts_correct(self):
        result = compute_analytics(self.records)
        author_dict = dict(result.top_authors)
        self.assertEqual(author_dict["Alpha, A."], 1)
        self.assertEqual(author_dict["Beta, B."], 1)
        self.assertEqual(author_dict["Gamma, G."], 1)
        self.assertEqual(author_dict["Delta, D."], 1)
        self.assertEqual(author_dict["Epsilon, E."], 1)
        self.assertEqual(author_dict["Zeta, Z."], 1)

    def test_top_keywords_counts_correct(self):
        result = compute_analytics(self.records)
        kw_dict = dict(result.top_keywords)
        self.assertEqual(kw_dict["consolidation"], 2)
        self.assertEqual(kw_dict["settlement"], 2)
        self.assertEqual(kw_dict["clay"], 2)
        self.assertEqual(kw_dict["sand"], 1)
        self.assertEqual(kw_dict["pavement"], 1)
        self.assertEqual(kw_dict["fatigue"], 1)

    def test_keyword_cooccurrence_matrix_symmetric(self):
        result = compute_analytics(self.records)
        matrix = result.keyword_cooccurrence.matrix
        n = len(matrix)
        for i in range(n):
            for j in range(n):
                self.assertEqual(matrix[i][j], matrix[j][i], f"Matrix not symmetric at ({i},{j})")

    def test_keyword_cooccurrence_diagonal_is_count(self):
        result = compute_analytics(self.records)
        kw_list = result.keyword_cooccurrence.keywords
        matrix = result.keyword_cooccurrence.matrix
        kw_dict = dict(result.top_keywords)
        for i, kw in enumerate(kw_list):
            self.assertEqual(matrix[i][i], kw_dict[kw], f"Diagonal mismatch for {kw}")

    def test_publication_types_counts(self):
        result = compute_analytics(self.records)
        self.assertEqual(result.publication_types["journal-article"], 3)
        self.assertEqual(result.publication_types["conference"], 1)

    def test_sources_counts(self):
        result = compute_analytics(self.records)
        self.assertEqual(result.sources["openalex"], 2)
        self.assertEqual(result.sources["crossref"], 1)
        self.assertEqual(result.sources["semantic_scholar"], 1)

    def test_empty_records_returns_empty_result(self):
        result = compute_analytics([])
        self.assertEqual(result.trends, [])
        self.assertEqual(result.top_venues, [])
        self.assertEqual(result.top_authors, [])
        self.assertEqual(result.top_keywords, [])
        self.assertIsNone(result.keyword_cooccurrence)
        self.assertEqual(result.topic_clusters, [])
        self.assertEqual(result.publication_types, {})
        self.assertEqual(result.sources, {})
        self.assertEqual(result.open_access_status, {})


class TestKeywordCooccurrenceToDict(unittest.TestCase):
    """Test KeywordCooccurrence.to_dict."""

    def test_to_dict_returns_correct_structure(self):
        kc = KeywordCooccurrence(keywords=["a", "b"], matrix=[[1, 2], [2, 3]])
        d = kc.to_dict()
        self.assertEqual(d["keywords"], ["a", "b"])
        self.assertEqual(d["matrix"], [[1, 2], [2, 3]])


class TestFindKeywordClusters(unittest.TestCase):
    """Test _find_keyword_clusters function."""

    def test_finds_connected_components(self):
        keywords = ["a", "b", "c", "d"]
        matrix = [
            [1, 2, 0, 0],  # a-b connected
            [2, 1, 0, 0],  # b-a connected
            [0, 0, 1, 3],  # c-d connected
            [0, 0, 3, 1],  # d-c connected
        ]
        clusters = _find_keyword_clusters(keywords, matrix, min_cooccurrence=2)
        self.assertEqual(len(clusters), 2)
        # Order may vary, check sets
        cluster_sets = [set(c) for c in clusters]
        self.assertIn({"a", "b"}, cluster_sets)
        self.assertIn({"c", "d"}, cluster_sets)

    def test_singletons_excluded(self):
        keywords = ["a", "b", "c"]
        matrix = [
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1],
        ]
        clusters = _find_keyword_clusters(keywords, matrix, min_cooccurrence=2)
        self.assertEqual(clusters, [])


class TestExportAnalytics(unittest.TestCase):
    """Test export_analytics function."""

    def setUp(self):
        self.records = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"], venue="Journal A", keywords=["kw1"], publication_type="journal-article", source="openalex"),
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"], venue="Journal B", keywords=["kw2"], publication_type="journal-article", source="crossref"),
        ]
        self.analytics = compute_analytics(self.records)

    def test_creates_expected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = export_analytics(self.analytics, output_dir)

            expected_keys = [
                "trends",
                "top_venues",
                "top_authors",
                "top_keywords",
                "keyword_cooccurrence",
                "topic_clusters",
                "publication_types",
                "sources",
                "open_access",
            ]
            for key in expected_keys:
                self.assertIn(key, paths)
                self.assertTrue(paths[key].exists(), f"Missing file: {key}")

    def test_trends_csv_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = export_analytics(self.analytics, output_dir)
            content = paths["trends"].read_text()
            lines = content.strip().split("\n")
            self.assertEqual(lines[0], "year,count,cumulative")
            self.assertEqual(len(lines), 3)  # header + 2 years

    def test_top_venues_csv_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = export_analytics(self.analytics, output_dir)
            content = paths["top_venues"].read_text()
            lines = content.strip().split("\n")
            self.assertEqual(lines[0], "venue,count")

    def test_keyword_cooccurrence_json_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = export_analytics(self.analytics, output_dir)
            content = paths["keyword_cooccurrence"].read_text()
            data = json.loads(content)
            self.assertIn("keywords", data)
            self.assertIn("matrix", data)
            self.assertEqual(len(data["keywords"]), len(data["matrix"]))

    def test_topic_clusters_json_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = export_analytics(self.analytics, output_dir)
            content = paths["topic_clusters"].read_text()
            data = json.loads(content)
            self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()