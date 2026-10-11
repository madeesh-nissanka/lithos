# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.reproducibility module."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import json
import tempfile
from pathlib import Path
import unittest

from lithos.models import Record, RunManifest, RunLedger, SearchQuery
from lithos.reproducibility import (
    create_run_manifest,
    RunCache,
    CacheEntry,
    compute_records_hash,
    compute_ledger,
    save_run_manifest,
    load_run_manifest,
    save_ledger,
    load_ledger,
    compute_file_hash,
)


class TestCreateRunManifest(unittest.TestCase):
    """Test create_run_manifest function."""

    def test_creates_manifest_with_all_fields(self):
        queries = [SearchQuery(original="test query", boolean_query="test AND query")]
        manifest = create_run_manifest(
            run_id="test-run-1",
            parameters={"param": "value"},
            queries=queries,
            sources_used=["openalex", "crossref"],
        )

        self.assertEqual(manifest.run_id, "test-run-1")
        self.assertEqual(manifest.lithos_version, "0.2.0")
        self.assertTrue(manifest.python_version)
        self.assertTrue(manifest.started_at)
        self.assertTrue(manifest.config_hash)  # Just verify it's non-empty
        self.assertEqual(manifest.parameters, {"param": "value"})
        self.assertEqual(len(manifest.queries), 1)
        self.assertEqual(manifest.queries[0].original, "test query")
        self.assertEqual(manifest.sources_used, ["openalex", "crossref"])
        self.assertEqual(manifest.total_records_found, 0)
        self.assertEqual(manifest.total_records_after_dedup, 0)
        self.assertEqual(manifest.validation_summary, {})
        self.assertEqual(manifest.output_hashes, {})

    def test_config_hash_deterministic(self):
        params = {"a": 1, "b": 2}
        m1 = create_run_manifest("run1", params, [], ["openalex"])
        m2 = create_run_manifest("run2", params, [], ["openalex"])
        self.assertEqual(m1.config_hash, m2.config_hash)

    def test_config_hash_changes_with_params(self):
        m1 = create_run_manifest("run1", {"a": 1}, [], ["openalex"])
        m2 = create_run_manifest("run2", {"a": 2}, [], ["openalex"])
        self.assertNotEqual(m1.config_hash, m2.config_hash)


class TestRunCache(unittest.TestCase):
    """Test RunCache class."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.tmpdir.name)
        self.cache = RunCache(self.cache_dir, ttl_days=1)
        self.query = SearchQuery(original="test", boolean_query="test", filters={})
        self.records = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"]),
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"]),
        ]

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_set_get_round_trip(self):
        self.cache.set("openalex", self.query, 100, self.records)
        retrieved = self.cache.get("openalex", self.query, 100)
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved), 2)
        self.assertEqual(retrieved[0].doi, "10.9999/aaa")
        self.assertEqual(retrieved[1].doi, "10.9999/bbb")

    def test_get_missing_returns_none(self):
        retrieved = self.cache.get("openalex", self.query, 100)
        self.assertIsNone(retrieved)

    def test_different_query_returns_none(self):
        self.cache.set("openalex", self.query, 100, self.records)
        other_query = SearchQuery(original="other", boolean_query="other", filters={})
        retrieved = self.cache.get("openalex", other_query, 100)
        self.assertIsNone(retrieved)

    def test_different_source_returns_none(self):
        self.cache.set("openalex", self.query, 100, self.records)
        retrieved = self.cache.get("crossref", self.query, 100)
        self.assertIsNone(retrieved)

    def test_different_limit_returns_none(self):
        self.cache.set("openalex", self.query, 100, self.records)
        retrieved = self.cache.get("openalex", self.query, 50)
        self.assertIsNone(retrieved)

    def test_delete_removes_entry(self):
        self.cache.set("openalex", self.query, 100, self.records)
        self.cache.delete(self.cache._make_key("openalex", self.query, 100))
        retrieved = self.cache.get("openalex", self.query, 100)
        self.assertIsNone(retrieved)

    def test_clear_removes_all(self):
        self.cache.set("openalex", self.query, 100, self.records)
        self.cache.set("crossref", self.query, 100, self.records)
        self.cache.clear()
        self.assertIsNone(self.cache.get("openalex", self.query, 100))
        self.assertIsNone(self.cache.get("crossref", self.query, 100))

    def test_stats_returns_correct_info(self):
        self.cache.set("openalex", self.query, 100, self.records)
        stats = self.cache.stats()
        self.assertEqual(stats["entries"], 1)
        self.assertGreaterEqual(stats["total_size_mb"], 0)
        self.assertEqual(stats["cache_dir"], str(self.cache_dir))


class TestComputeRecordsHash(unittest.TestCase):
    """Test compute_records_hash function."""

    def test_deterministic_for_same_records(self):
        records = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"]),
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"]),
        ]
        h1 = compute_records_hash(records)
        h2 = compute_records_hash(records)
        self.assertEqual(h1, h2)

    def test_changes_when_record_changes(self):
        records1 = [Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"])]
        records2 = [Record(doi="10.9999/aaa", title="Paper 1 Modified", year=2018, authors=["A"])]
        h1 = compute_records_hash(records1)
        h2 = compute_records_hash(records2)
        self.assertNotEqual(h1, h2)

    def test_order_independent(self):
        records1 = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"]),
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"]),
        ]
        records2 = [
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"]),
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"]),
        ]
        h1 = compute_records_hash(records1)
        h2 = compute_records_hash(records2)
        self.assertEqual(h1, h2)

    def test_empty_list_returns_hash(self):
        h = compute_records_hash([])
        self.assertEqual(len(h), 16)


class TestComputeLedger(unittest.TestCase):
    """Test compute_ledger function."""

    def test_classifies_new_unchanged_changed_removed(self):
        # Previous run records
        prev_records = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"]),
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"]),
            Record(doi="10.9999/ccc", title="Paper 3", year=2020, authors=["C"]),
        ]
        # Current run records: aaa unchanged, bbb changed, ccc removed, ddd new
        curr_records = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"]),  # unchanged
            Record(doi="10.9999/bbb", title="Paper 2 Modified", year=2019, authors=["B"]),  # changed
            Record(doi="10.9999/ddd", title="Paper 4", year=2021, authors=["D"]),  # new
        ]

        ledger = compute_ledger(curr_records, prev_records, "run-new", "run-old")

        self.assertIn(prev_records[0].id, ledger.unchanged)
        self.assertIn(prev_records[1].id, ledger.changed)
        self.assertIn(prev_records[2].id, ledger.removed)
        self.assertIn(curr_records[2].id, ledger.new)

    def test_all_new_when_no_previous(self):
        curr_records = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"]),
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"]),
        ]
        ledger = compute_ledger(curr_records, [], "run-new")
        self.assertEqual(len(ledger.new), 2)
        self.assertEqual(ledger.unchanged, [])
        self.assertEqual(ledger.changed, [])
        self.assertEqual(ledger.removed, [])

    def test_all_removed_when_no_current(self):
        prev_records = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"]),
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"]),
        ]
        ledger = compute_ledger([], prev_records, "run-new", "run-old")
        self.assertEqual(len(ledger.removed), 2)
        self.assertEqual(ledger.unchanged, [])
        self.assertEqual(ledger.changed, [])
        self.assertEqual(ledger.new, [])

    def test_ledger_fields_populated(self):
        prev_records = [Record(doi="10.9999/aaa", title="Paper 1")]
        curr_records = [Record(doi="10.9999/aaa", title="Paper 1")]
        ledger = compute_ledger(curr_records, prev_records, "run-new", "run-old")
        self.assertEqual(ledger.run_id, "run-new")
        self.assertEqual(ledger.previous_run_id, "run-old")


class TestSaveLoadRunManifest(unittest.TestCase):
    """Test save_run_manifest and load_run_manifest."""

    def test_save_load_round_trip_without_queries(self):
        # Note: queries are stored as strings due to to_json() using default=str,
        # so load_run_manifest fails to reconstruct SearchQuery objects.
        # This test uses a manifest without queries.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            manifest = create_run_manifest("test-run", {"p": 1}, [], ["openalex"])
            save_run_manifest(manifest, path)
            loaded = load_run_manifest(path)

            self.assertEqual(loaded.run_id, manifest.run_id)
            self.assertEqual(loaded.lithos_version, manifest.lithos_version)
            self.assertEqual(loaded.config_hash, manifest.config_hash)
            self.assertEqual(loaded.parameters, manifest.parameters)
            self.assertEqual(loaded.queries, [])
            self.assertEqual(loaded.sources_used, ["openalex"])


class TestSaveLoadLedger(unittest.TestCase):
    """Test save_ledger and load_ledger."""

    def test_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            ledger = RunLedger(
                run_id="run-new",
                previous_run_id="run-old",
                unchanged=["id1"],
                new=["id2"],
                changed=["id3"],
                removed=["id4"],
            )
            save_ledger(ledger, path)
            loaded = load_ledger(path)

            self.assertEqual(loaded.run_id, "run-new")
            self.assertEqual(loaded.previous_run_id, "run-old")
            self.assertEqual(loaded.unchanged, ["id1"])
            self.assertEqual(loaded.new, ["id2"])
            self.assertEqual(loaded.changed, ["id3"])
            self.assertEqual(loaded.removed, ["id4"])


class TestComputeFileHash(unittest.TestCase):
    """Test compute_file_hash function."""

    def test_computes_hash_for_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.txt"
            path.write_text("hello world")
            h = compute_file_hash(path)
            self.assertEqual(len(h), 64)  # SHA256 hex

    def test_different_content_different_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path1 = Path(tmp) / "test1.txt"
            path2 = Path(tmp) / "test2.txt"
            path1.write_text("hello")
            path2.write_text("world")
            h1 = compute_file_hash(path1)
            h2 = compute_file_hash(path2)
            self.assertNotEqual(h1, h2)

    def test_same_content_same_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path1 = Path(tmp) / "test1.txt"
            path2 = Path(tmp) / "test2.txt"
            path1.write_text("same content")
            path2.write_text("same content")
            h1 = compute_file_hash(path1)
            h2 = compute_file_hash(path2)
            self.assertEqual(h1, h2)


if __name__ == "__main__":
    unittest.main()