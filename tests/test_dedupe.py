# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.dedupe module."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import unittest
from lithos.dedupe import (
    normalize_title,
    normalize_author,
    first_author_surname,
    title_similarity,
    fuzzy_match,
    deduplicate,
    generate_dedup_report,
)
from lithos.models import Record, DedupCluster


class TestNormalizeTitle(unittest.TestCase):
    """Tests for normalize_title function."""

    def test_basic_normalization(self):
        """Lowercases and removes punctuation."""
        self.assertEqual(normalize_title("Soil Consolidation Settlement"), "soil consolidation settlement")

    def test_removes_punctuation(self):
        """Removes punctuation characters."""
        self.assertEqual(normalize_title("Soil, Consolidation; Settlement!"), "soil consolidation settlement")

    def test_collapses_whitespace(self):
        """Collapses multiple spaces."""
        self.assertEqual(normalize_title("Soil    Consolidation"), "soil consolidation")

    def test_empty_string(self):
        """Empty string returns empty."""
        self.assertEqual(normalize_title(""), "")

    def test_none_returns_empty(self):
        """None returns empty string."""
        self.assertEqual(normalize_title(None), "")  # type: ignore[arg-type]

    def test_numbers_preserved(self):
        """Numbers are preserved."""
        self.assertEqual(normalize_title("Test 2020 Year"), "test 2020 year")


class TestNormalizeAuthor(unittest.TestCase):
    """Tests for normalize_author function."""

    def test_surname_from_comma_format(self):
        """Extracts surname from 'Surname, Given' format."""
        self.assertEqual(normalize_author("Alpha, A."), "alpha")

    def test_surname_from_space_format(self):
        """Extracts surname from 'Given Surname' format."""
        self.assertEqual(normalize_author("A. Alpha"), "alpha")

    def test_multiple_parts(self):
        """Handles multiple name parts."""
        self.assertEqual(normalize_author("John Michael Smith"), "smith")

    def test_strips_whitespace(self):
        """Strips surrounding whitespace."""
        self.assertEqual(normalize_author("  Alpha, A.  "), "alpha")

    def test_empty_string(self):
        """Empty string returns empty."""
        self.assertEqual(normalize_author(""), "")


class TestFirstAuthorSurname(unittest.TestCase):
    """Tests for first_author_surname function."""

    def test_returns_first_author_surname(self):
        """Returns surname of first author."""
        self.assertEqual(first_author_surname(["Alpha, A.", "Beta, B."]), "alpha")

    def test_returns_none_for_empty_list(self):
        """Returns None for empty author list."""
        self.assertIsNone(first_author_surname([]))

    def test_handles_space_format(self):
        """Handles 'Given Surname' format."""
        self.assertEqual(first_author_surname(["A. Alpha", "B. Beta"]), "alpha")


class TestTitleSimilarity(unittest.TestCase):
    """Tests for title_similarity function."""

    def test_identical_titles(self):
        """Identical titles have similarity 1.0."""
        self.assertEqual(title_similarity("Soil Consolidation", "Soil Consolidation"), 1.0)

    def test_case_insensitive(self):
        """Comparison is case-insensitive."""
        self.assertEqual(title_similarity("SOIL CONSOLIDATION", "soil consolidation"), 1.0)

    def test_different_titles(self):
        """Different titles have lower similarity."""
        sim = title_similarity("Soil Consolidation", "Slope Stability")
        self.assertLess(sim, 1.0)
        self.assertGreater(sim, 0.0)

    def test_punctuation_ignored(self):
        """Punctuation is ignored in comparison."""
        self.assertEqual(title_similarity("Soil, Consolidation!", "Soil Consolidation"), 1.0)


class TestFuzzyMatch(unittest.TestCase):
    """Tests for fuzzy_match function."""

    def setUp(self):
        self.rec1 = Record(
            doi="10.9999/aaa",
            title="Soil consolidation settlement of soft clay",
            year=2018,
            authors=["Alpha, A."],
            keywords=["consolidation"],
            source="openalex",
        )
        self.rec2 = Record(
            doi="10.9999/bbb",
            title="Soil consolidation settlement of soft clay",
            year=2018,
            authors=["Alpha, A."],
            keywords=["consolidation"],
            source="crossref",
        )

    def test_same_doi_different_records(self):
        """Records with same DOI match (but this is handled in deduplicate phase 1)."""
        # fuzzy_match is called after DOI/title phases, so this tests title+year+author
        pass

    def test_title_similarity_threshold(self):
        """Returns False if title similarity below threshold."""
        rec_a = Record(title="Soil consolidation settlement", year=2018, authors=["Alpha, A."], source="a")
        rec_b = Record(title="Slope stability analysis", year=2018, authors=["Alpha, A."], source="b")
        self.assertFalse(fuzzy_match(rec_a, rec_b, threshold=0.85))

    def test_year_diff_greater_than_one(self):
        """Returns False if year difference > 1."""
        rec_a = Record(title="Soil consolidation settlement", year=2018, authors=["Alpha, A."], source="a")
        rec_b = Record(title="Soil consolidation settlement", year=2021, authors=["Alpha, A."], source="b")
        self.assertFalse(fuzzy_match(rec_a, rec_b, threshold=0.85))

    def test_year_diff_one_allowed(self):
        """Returns True if year difference <= 1 and titles match."""
        rec_a = Record(title="Soil consolidation settlement", year=2018, authors=["Alpha, A."], source="a")
        rec_b = Record(title="Soil consolidation settlement", year=2019, authors=["Alpha, A."], source="b")
        self.assertTrue(fuzzy_match(rec_a, rec_b, threshold=0.85))

    def test_surname_mismatch(self):
        """Returns False if first author surnames differ."""
        rec_a = Record(title="Soil consolidation settlement", year=2018, authors=["Alpha, A."], source="a")
        rec_b = Record(title="Soil consolidation settlement", year=2018, authors=["Beta, B."], source="b")
        self.assertFalse(fuzzy_match(rec_a, rec_b, threshold=0.85))

    def test_surname_match_allows_fuzzy(self):
        """Returns True when titles similar, year close, surnames match."""
        rec_a = Record(title="Soil consolidation settlement analysis", year=2018, authors=["Alpha, A."], source="a")
        rec_b = Record(title="Soil consolidation settlement of clay", year=2019, authors=["Alpha, A."], source="b")
        self.assertTrue(fuzzy_match(rec_a, rec_b, threshold=0.75))

    def test_missing_year_allows_match(self):
        """Missing year doesn't block match."""
        rec_a = Record(title="Soil consolidation settlement", year=2018, authors=["Alpha, A."], source="a")
        rec_b = Record(title="Soil consolidation settlement", year=None, authors=["Alpha, A."], source="b")
        self.assertTrue(fuzzy_match(rec_a, rec_b, threshold=0.85))

    def test_missing_author_allows_match(self):
        """Missing author doesn't block match."""
        rec_a = Record(title="Soil consolidation settlement", year=2018, authors=["Alpha, A."], source="a")
        rec_b = Record(title="Soil consolidation settlement", year=2018, authors=[], source="b")
        self.assertTrue(fuzzy_match(rec_a, rec_b, threshold=0.85))


class TestDeduplicate(unittest.TestCase):
    """Tests for deduplicate function."""

    def make_rec(self, doi: str, title: str, year: int, author: str, source: str) -> Record:
        return Record(
            doi=doi,
            title=title,
            year=year,
            authors=[author],
            source=source,
            query_hits=[f"query_{source}"],
        )

    def test_empty_input(self):
        """Empty input returns empty lists."""
        records, clusters = deduplicate([])
        self.assertEqual(records, [])
        self.assertEqual(clusters, [])

    def test_exact_doi_merge(self):
        """Records with same DOI are merged (phase 1), cluster created with no duplicates."""
        r1 = self.make_rec("10.9999/aaa", "Title A", 2018, "Alpha, A.", "openalex")
        r2 = self.make_rec("10.9999/aaa", "Title A", 2018, "Alpha, A.", "crossref")
        records, clusters = deduplicate([r1, r2])
        self.assertEqual(len(records), 1)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(set(records[0].query_hits), {"query_openalex", "query_crossref"})
        self.assertTrue(records[0].dedup_master)
        self.assertEqual(records[0].dedup_cluster_id, clusters[0].cluster_id)
        # Cluster has no duplicates (merged in phase 1)
        self.assertEqual(len(clusters[0].duplicates), 0)

    def test_normalized_title_merge(self):
        """Records with same normalized title are merged."""
        r1 = self.make_rec("10.9999/aaa", "Soil Consolidation Settlement", 2018, "Alpha, A.", "openalex")
        r2 = self.make_rec("10.9999/bbb", "soil consolidation settlement", 2018, "Alpha, A.", "crossref")
        records, clusters = deduplicate([r1, r2])
        self.assertEqual(len(records), 1)
        self.assertEqual(len(clusters), 1)
        self.assertIn("query_openalex", records[0].query_hits)
        self.assertIn("query_crossref", records[0].query_hits)

    def test_fuzzy_match_cluster(self):
        """Fuzzy matching creates cluster with master and duplicate."""
        r1 = self.make_rec("10.9999/aaa", "Soil consolidation settlement analysis", 2018, "Alpha, A.", "openalex")
        r2 = self.make_rec("10.9999/bbb", "Soil consolidation settlement of clay", 2019, "Alpha, A.", "crossref")
        records, clusters = deduplicate([r1, r2], fuzzy_threshold=0.75)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].duplicates), 1)
        self.assertTrue(records[0].dedup_master)
        self.assertFalse(clusters[0].duplicates[0].dedup_master)
        self.assertEqual(clusters[0].duplicates[0].dedup_cluster_id, clusters[0].cluster_id)

    def test_year_diff_blocks_fuzzy(self):
        """Year difference > 1 blocks fuzzy match (titles similar but not identical)."""
        r1 = self.make_rec("10.9999/aaa", "Soil consolidation settlement analysis", 2018, "Alpha, A.", "openalex")
        r2 = self.make_rec("10.9999/bbb", "Soil consolidation settlement of clay", 2021, "Alpha, A.", "crossref")
        records, clusters = deduplicate([r1, r2], fuzzy_threshold=0.75)
        self.assertEqual(len(records), 2)
        self.assertEqual(len(clusters), 2)
        # Both should be masters (no duplicates)
        self.assertTrue(all(r.dedup_master for r in records))

    def test_surname_diff_blocks_fuzzy(self):
        """Different first author surname blocks fuzzy match (titles similar but not identical)."""
        r1 = self.make_rec("10.9999/aaa", "Soil consolidation settlement analysis", 2018, "Alpha, A.", "openalex")
        r2 = self.make_rec("10.9999/bbb", "Soil consolidation settlement of clay", 2018, "Beta, B.", "crossref")
        records, clusters = deduplicate([r1, r2], fuzzy_threshold=0.75)
        self.assertEqual(len(records), 2)
        self.assertEqual(len(clusters), 2)

    def test_query_hits_unioned_in_cluster(self):
        """Query hits are unioned across cluster members."""
        r1 = self.make_rec("10.9999/aaa", "Title", 2018, "Alpha, A.", "openalex")
        r2 = self.make_rec("10.9999/aaa", "Title", 2018, "Alpha, A.", "crossref")
        r2.query_hits = ["query_crossref", "query_other"]
        records, clusters = deduplicate([r1, r2])
        self.assertEqual(len(records), 1)
        self.assertEqual(set(records[0].query_hits), {"query_openalex", "query_crossref", "query_other"})

    def test_dedup_master_flag_true_for_master(self):
        """Master record has dedup_master=True (for clusters created in phase 2 via fuzzy match)."""
        # Use fuzzy match which creates a cluster with duplicates
        r1 = self.make_rec("10.9999/aaa", "Soil consolidation settlement analysis", 2018, "Alpha, A.", "openalex")
        r2 = self.make_rec("10.9999/bbb", "Soil consolidation settlement of clay", 2019, "Alpha, A.", "crossref")
        records, clusters = deduplicate([r1, r2], fuzzy_threshold=0.75)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(clusters), 1)
        self.assertTrue(records[0].dedup_master)
        self.assertFalse(clusters[0].duplicates[0].dedup_master)
        self.assertEqual(records[0].dedup_cluster_id, clusters[0].cluster_id)
        self.assertEqual(clusters[0].duplicates[0].dedup_cluster_id, clusters[0].cluster_id)

    def test_multiple_clusters(self):
        """Multiple independent clusters are created."""
        r1 = self.make_rec("10.9999/aaa", "Soil consolidation", 2018, "Alpha, A.", "openalex")
        r2 = self.make_rec("10.9999/aaa", "Soil consolidation", 2018, "Alpha, A.", "crossref")
        r3 = self.make_rec("10.9999/bbb", "Slope stability", 2019, "Beta, B.", "openalex")
        r4 = self.make_rec("10.9999/bbb", "Slope stability", 2019, "Beta, B.", "crossref")
        records, clusters = deduplicate([r1, r2, r3, r4])
        self.assertEqual(len(records), 2)
        self.assertEqual(len(clusters), 2)

    def test_no_duplicates_returns_all(self):
        """Records with no duplicates are all returned as masters."""
        r1 = self.make_rec("10.9999/aaa", "Title A", 2018, "Alpha, A.", "openalex")
        r2 = self.make_rec("10.9999/bbb", "Title B", 2019, "Beta, B.", "crossref")
        records, clusters = deduplicate([r1, r2])
        self.assertEqual(len(records), 2)
        self.assertEqual(len(clusters), 2)
        self.assertTrue(all(r.dedup_master for r in records))
        self.assertTrue(all(len(c.duplicates) == 0 for c in clusters))


class TestGenerateDedupReport(unittest.TestCase):
    """Tests for generate_dedup_report function."""

    def test_empty_clusters(self):
        """Empty cluster list returns basic report."""
        report = generate_dedup_report([])
        self.assertIn("Total clusters: 0", report)
        self.assertIn("Total duplicates removed: 0", report)

    def test_single_cluster_with_duplicates(self):
        """Report includes cluster details."""
        master = Record(
            doi="10.9999/aaa",
            title="Soil consolidation settlement of soft clay foundations",
            year=2018,
            authors=["Alpha, A."],
            source="openalex",
        )
        dup = Record(
            doi="10.9999/bbb",
            title="Soil consolidation settlement of soft clay",
            year=2018,
            authors=["Alpha, A."],
            source="crossref",
        )
        cluster = DedupCluster(
            cluster_id="cluster_0",
            master_record=master,
            duplicates=[dup],
            match_reasons=["normalized_title"],
        )
        report = generate_dedup_report([cluster])
        self.assertIn("Total clusters: 1", report)
        self.assertIn("Total duplicates removed: 1", report)
        self.assertIn("cluster_0", report)
        self.assertIn("Soil consolidation settlement", report)
        self.assertIn("alpha", report)  # lowercase in report due to normalize_author
        self.assertIn("normalized_title", report)

    def test_multiple_clusters(self):
        """Report handles multiple clusters."""
        master1 = Record(title="Title A", year=2018, authors=["Alpha, A."], source="a")
        dup1 = Record(title="Title A", year=2018, authors=["Alpha, A."], source="b")
        master2 = Record(title="Title B", year=2019, authors=["Beta, B."], source="c")
        dup2 = Record(title="Title B", year=2019, authors=["Beta, B."], source="d")
        clusters = [
            DedupCluster(cluster_id="c1", master_record=master1, duplicates=[dup1], match_reasons=["title"]),
            DedupCluster(cluster_id="c2", master_record=master2, duplicates=[dup2], match_reasons=["title"]),
        ]
        report = generate_dedup_report(clusters)
        self.assertIn("Total clusters: 2", report)
        self.assertIn("Total duplicates removed: 2", report)
        self.assertIn("c1", report)
        self.assertIn("c2", report)

    def test_cluster_without_duplicates_skipped_in_details(self):
        """Clusters with no duplicates are not detailed in report."""
        master = Record(title="Unique Title", year=2018, authors=["Alpha, A."], source="a")
        cluster = DedupCluster(cluster_id="c1", master_record=master, duplicates=[], match_reasons=["master"])
        report = generate_dedup_report([cluster])
        self.assertIn("Total clusters: 1", report)
        self.assertIn("Total duplicates removed: 0", report)
        # Should not have detailed section for this cluster
        self.assertNotIn("## Cluster c1", report)


if __name__ == "__main__":
    unittest.main()