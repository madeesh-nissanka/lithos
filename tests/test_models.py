# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.models module."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import json
import unittest
from lithos.models import (
    Record,
    RecordStatus,
    ScreenState,
    ScreenDecision,
    AnalyticsResult,
    RunManifest,
    SearchQuery,
)


class TestRecordAutoId(unittest.TestCase):
    """Test Record ID auto-generation from various identifiers."""

    def test_id_from_doi(self):
        r = Record(doi="10.9999/aaa", title="Test")
        self.assertTrue(r.id.startswith("doi:10.9999/aaa"))

    def test_id_from_pmid(self):
        r = Record(pmid="12345678", title="Test")
        self.assertTrue(r.id.startswith("pmid:12345678"))

    def test_id_from_arxiv(self):
        r = Record(arxiv_id="2001.00001", title="Test")
        self.assertTrue(r.id.startswith("arxiv:2001.00001"))

    def test_id_from_openalex(self):
        r = Record(openalex_id="W12345", title="Test")
        self.assertTrue(r.id.startswith("oa:W12345"))

    def test_id_from_semantic_scholar(self):
        r = Record(semantic_scholar_id="s2abc", title="Test")
        self.assertTrue(r.id.startswith("s2:s2abc"))

    def test_id_from_core(self):
        r = Record(core_id="core123", title="Test")
        self.assertTrue(r.id.startswith("core:core123"))

    def test_id_fallback_to_title_hash(self):
        r = Record(title="Unique Title for Hash Generation")
        self.assertTrue(r.id.startswith("title:"))
        self.assertEqual(len(r.id), len("title:") + 12)  # 12-char md5 prefix


class TestRecordContentHash(unittest.TestCase):
    """Test content_hash changes when title/content changes."""

    def test_content_hash_changes_with_title(self):
        r1 = Record(doi="10.9999/aaa", title="Title One", year=2020, authors=["A. Author"], venue="Journal", abstract="Abstract")
        r2 = Record(doi="10.9999/aaa", title="Title Two", year=2020, authors=["A. Author"], venue="Journal", abstract="Abstract")
        self.assertNotEqual(r1.content_hash, r2.content_hash)

    def test_content_hash_changes_with_year(self):
        r1 = Record(doi="10.9999/aaa", title="Title", year=2020, authors=["A. Author"], venue="Journal", abstract="Abstract")
        r2 = Record(doi="10.9999/aaa", title="Title", year=2021, authors=["A. Author"], venue="Journal", abstract="Abstract")
        self.assertNotEqual(r1.content_hash, r2.content_hash)

    def test_content_hash_changes_with_authors(self):
        r1 = Record(doi="10.9999/aaa", title="Title", year=2020, authors=["A. Author"], venue="Journal", abstract="Abstract")
        r2 = Record(doi="10.9999/aaa", title="Title", year=2020, authors=["B. Author"], venue="Journal", abstract="Abstract")
        self.assertNotEqual(r1.content_hash, r2.content_hash)

    def test_content_hash_changes_with_venue(self):
        r1 = Record(doi="10.9999/aaa", title="Title", year=2020, authors=["A. Author"], venue="Journal A", abstract="Abstract")
        r2 = Record(doi="10.9999/aaa", title="Title", year=2020, authors=["A. Author"], venue="Journal B", abstract="Abstract")
        self.assertNotEqual(r1.content_hash, r2.content_hash)

    def test_content_hash_changes_with_abstract(self):
        r1 = Record(doi="10.9999/aaa", title="Title", year=2020, authors=["A. Author"], venue="Journal", abstract="Abstract one")
        r2 = Record(doi="10.9999/aaa", title="Title", year=2020, authors=["A. Author"], venue="Journal", abstract="Abstract two")
        self.assertNotEqual(r1.content_hash, r2.content_hash)

    def test_content_hash_same_for_identical_content(self):
        r1 = Record(doi="10.9999/aaa", title="Title", year=2020, authors=["A. Author"], venue="Journal", abstract="Abstract")
        r2 = Record(doi="10.9999/aaa", title="Title", year=2020, authors=["A. Author"], venue="Journal", abstract="Abstract")
        self.assertEqual(r1.content_hash, r2.content_hash)


class TestRecordToDictFromDict(unittest.TestCase):
    """Test to_dict/from_dict round-trip preserves fields."""

    def test_round_trip_preserves_core_fields(self):
        original = Record(
            doi="10.9999/aaa",
            title="Test Title",
            year=2020,
            authors=["Author, A.", "Author, B."],
            venue="Test Journal",
            abstract="Test abstract",
            keywords=["keyword1", "keyword2"],
            publication_type="journal-article",
            cited_by=10,
            referenced_works=["10.9999/ref1"],
            citing_works=["10.9999/cite1"],
            source="openalex",
            query_hits=["query1"],
            status=RecordStatus.VALIDATED,
            flags=["flag1"],
            crossref_data={"key": "value"},
            completeness_score=0.95,
            screen_state=ScreenState.INCLUDE,
            screen_notes="Included",
            reviewer_decisions={"reviewer1": ScreenState.INCLUDE},
            dedup_cluster_id="cluster1",
            dedup_master=True,
            retrieved_at="2024-01-01T00:00:00",
            retrieved_by="openalex",
        )
        data = original.to_dict()
        restored = Record.from_dict(data)

        self.assertEqual(restored.doi, original.doi)
        self.assertEqual(restored.title, original.title)
        self.assertEqual(restored.year, original.year)
        self.assertEqual(restored.authors, original.authors)
        self.assertEqual(restored.venue, original.venue)
        self.assertEqual(restored.abstract, original.abstract)
        self.assertEqual(restored.keywords, original.keywords)
        self.assertEqual(restored.publication_type, original.publication_type)
        self.assertEqual(restored.cited_by, original.cited_by)
        self.assertEqual(restored.referenced_works, original.referenced_works)
        self.assertEqual(restored.citing_works, original.citing_works)
        self.assertEqual(restored.source, original.source)
        self.assertEqual(restored.query_hits, original.query_hits)
        self.assertEqual(restored.status, original.status)
        self.assertEqual(restored.flags, original.flags)
        self.assertEqual(restored.crossref_data, original.crossref_data)
        self.assertEqual(restored.completeness_score, original.completeness_score)
        self.assertEqual(restored.screen_state, original.screen_state)
        self.assertEqual(restored.screen_notes, original.screen_notes)
        self.assertEqual(restored.reviewer_decisions, original.reviewer_decisions)
        self.assertEqual(restored.dedup_cluster_id, original.dedup_cluster_id)
        self.assertEqual(restored.dedup_master, original.dedup_master)
        self.assertEqual(restored.retrieved_at, original.retrieved_at)
        self.assertEqual(restored.retrieved_by, original.retrieved_by)
        self.assertEqual(restored.content_hash, original.content_hash)

    def test_round_trip_preserves_id(self):
        original = Record(id="custom-id", doi="10.9999/aaa", title="Test")
        data = original.to_dict()
        restored = Record.from_dict(data)
        self.assertEqual(restored.id, "custom-id")

    def test_from_dict_generates_id_if_missing(self):
        data = {"title": "Test", "doi": "10.9999/aaa"}
        restored = Record.from_dict(data)
        self.assertTrue(restored.id.startswith("doi:10.9999/aaa"))

    def test_from_dict_generates_content_hash_if_missing(self):
        data = {"title": "Test", "doi": "10.9999/aaa", "year": 2020, "authors": ["A"], "venue": "J", "abstract": "Abs"}
        restored = Record.from_dict(data)
        self.assertTrue(restored.content_hash)
        self.assertEqual(len(restored.content_hash), 16)


class TestRecordStatusEnum(unittest.TestCase):
    """Test RecordStatus enum values."""

    def test_all_statuses_exist(self):
        expected = {
            "VALIDATED",
            "VALIDATED_WITH_WARNINGS",
            "NO_DOI",
            "NOT_FOUND_IN_CROSSREF",
            "CROSSREF_UNREACHABLE",
            "RETRACTED",
            "PREDATORY_VENUE",
            "PREPRINT",
            "PREPRINT_MATCHED",
        }
        actual = {s.name for s in RecordStatus}
        self.assertEqual(actual, expected)

    def test_status_values_are_strings(self):
        for status in RecordStatus:
            self.assertIsInstance(status.value, str)


class TestScreenStateEnum(unittest.TestCase):
    """Test ScreenState enum values."""

    def test_all_states_exist(self):
        expected = {"UNSCREENED", "INCLUDE", "EXCLUDE", "CONFLICT"}
        actual = {s.name for s in ScreenState}
        self.assertEqual(actual, expected)


class TestScreenDecision(unittest.TestCase):
    """Test ScreenDecision dataclass."""

    def test_defaults(self):
        sd = ScreenDecision()
        self.assertEqual(sd.reviewer, "")
        self.assertEqual(sd.decision, ScreenState.UNSCREENED)
        self.assertEqual(sd.notes, "")
        self.assertTrue(sd.decided_at)

    def test_custom_values(self):
        sd = ScreenDecision(reviewer="R1", decision=ScreenState.INCLUDE, notes="Good")
        self.assertEqual(sd.reviewer, "R1")
        self.assertEqual(sd.decision, ScreenState.INCLUDE)
        self.assertEqual(sd.notes, "Good")


class TestAnalyticsResultDefaults(unittest.TestCase):
    """Test AnalyticsResult default values."""

    def test_defaults_are_empty_collections(self):
        ar = AnalyticsResult()
        self.assertEqual(ar.trends, [])
        self.assertEqual(ar.top_venues, [])
        self.assertEqual(ar.top_authors, [])
        self.assertEqual(ar.top_keywords, [])
        self.assertIsNone(ar.keyword_cooccurrence)
        self.assertEqual(ar.topic_clusters, [])
        self.assertEqual(ar.publication_types, {})
        self.assertEqual(ar.sources, {})
        self.assertEqual(ar.open_access_status, {})


class TestRunManifestToJson(unittest.TestCase):
    """Test RunManifest.to_json produces valid JSON."""

    def test_to_json_parses_as_json(self):
        manifest = RunManifest(
            run_id="test-run-1",
            lithos_version="0.2.0",
            python_version="3.10.0",
            started_at="2024-01-01T00:00:00",
            config_hash="abc123",
            parameters={"param": "value"},
            queries=[SearchQuery(original="test query")],
            sources_used=["openalex"],
        )
        json_str = manifest.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["run_id"], "test-run-1")
        self.assertEqual(parsed["lithos_version"], "0.2.0")
        self.assertEqual(parsed["parameters"]["param"], "value")

    def test_to_json_handles_nested_objects(self):
        manifest = RunManifest(
            run_id="test-run-2",
            queries=[SearchQuery(original="query", boolean_query="boolean", filters={"year": 2020})],
        )
        json_str = manifest.to_json()
        parsed = json.loads(json_str)
        # Note: SearchQuery is serialized as string due to default=str in to_json()
        self.assertIsInstance(parsed["queries"][0], str)
        self.assertIn("original='query'", parsed["queries"][0])
        self.assertIn("filters={'year': 2020}", parsed["queries"][0])


if __name__ == "__main__":
    unittest.main()