# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.report module."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import tempfile
from pathlib import Path
import unittest

from lithos.models import Record, RunManifest, SearchQuery
from lithos.report import (
    PrismaCounts,
    generate_prisma_flow,
    generate_search_report,
    generate_evidence_maps,
)


class TestPrismaCountsDefaults(unittest.TestCase):
    """Test PrismaCounts default values."""

    def test_records_identified_defaults_to_empty_dict(self):
        counts = PrismaCounts()
        self.assertEqual(counts.records_identified, {})

    def test_numeric_fields_default_to_zero(self):
        counts = PrismaCounts()
        self.assertEqual(counts.records_before_dedup, 0)
        self.assertEqual(counts.duplicates_removed, 0)
        self.assertEqual(counts.records_after_dedup, 0)
        self.assertEqual(counts.records_screened, 0)
        self.assertEqual(counts.records_excluded_automatic, 0)
        self.assertEqual(counts.records_excluded_manual, 0)
        self.assertEqual(counts.records_included, 0)
        self.assertEqual(counts.records_conflicts, 0)

    def test_can_set_records_identified(self):
        counts = PrismaCounts(records_identified={"openalex": 100, "crossref": 50})
        self.assertEqual(counts.records_identified, {"openalex": 100, "crossref": 50})


class TestGeneratePrismaFlow(unittest.TestCase):
    """Test generate_prisma_flow function."""

    def setUp(self):
        self.records = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"], venue="Journal A"),
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"], venue="Journal B"),
        ]
        self.counts = PrismaCounts(
            records_identified={"openalex": 100, "crossref": 50},
            records_before_dedup=150,
            duplicates_removed=20,
            records_after_dedup=130,
            records_screened=130,
            records_excluded_automatic=30,
            records_excluded_manual=20,
            records_included=80,
            records_conflicts=5,
        )

    def test_generates_svg_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "prisma_flow.svg"
            generate_prisma_flow(self.records, self.counts, output_path, format="svg")
            self.assertTrue(output_path.exists())

    def test_svg_contains_svg_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "prisma_flow.svg"
            generate_prisma_flow(self.records, self.counts, output_path, format="svg")
            content = output_path.read_text()
            self.assertIn("<svg", content)

    def test_svg_contains_included_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "prisma_flow.svg"
            generate_prisma_flow(self.records, self.counts, output_path, format="svg")
            content = output_path.read_text()
            self.assertIn("Records included: 80", content)

    def test_svg_contains_identified_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "prisma_flow.svg"
            generate_prisma_flow(self.records, self.counts, output_path, format="svg")
            content = output_path.read_text()
            self.assertIn("Records identified: 150", content)

    def test_svg_contains_dedup_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "prisma_flow.svg"
            generate_prisma_flow(self.records, self.counts, output_path, format="svg")
            content = output_path.read_text()
            self.assertIn("Records before dedup: 150", content)
            self.assertIn("Duplicates removed: 20", content)
            self.assertIn("Records after dedup: 130", content)

    def test_svg_contains_screening_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "prisma_flow.svg"
            generate_prisma_flow(self.records, self.counts, output_path, format="svg")
            content = output_path.read_text()
            self.assertIn("Records screened: 130", content)
            self.assertIn("Excluded (automatic): 30", content)
            self.assertIn("Excluded (manual): 20", content)
            self.assertIn("Conflicts: 5", content)

    def test_invalid_format_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "prisma_flow.pdf"
            with self.assertRaises(ValueError):
                generate_prisma_flow(self.records, self.counts, output_path, format="pdf")


class TestGenerateSearchReport(unittest.TestCase):
    """Test generate_search_report function."""

    def setUp(self):
        self.records = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"], venue="Journal A"),
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"], venue="Journal B"),
        ]
        self.manifest = RunManifest(
            run_id="test-run",
            lithos_version="0.2.0",
            python_version="3.10.0",
            started_at="2024-01-01T00:00:00",
            config_hash="abc123",
            parameters={"query": "test"},
            queries=[SearchQuery(original="soil consolidation", boolean_query="soil AND consolidation")],
            sources_used=["openalex", "crossref"],
            total_records_found=150,
            total_records_after_dedup=130,
            validation_summary={"VALIDATED": 100, "NO_DOI": 30},
        )

    def test_generates_md_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "search_report.md"
            generate_search_report(self.records, self.manifest, output_path, format="md")
            self.assertTrue(output_path.exists())

    def test_md_mentions_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "search_report.md"
            generate_search_report(self.records, self.manifest, output_path, format="md")
            content = output_path.read_text()
            self.assertIn("soil consolidation", content)

    def test_md_contains_run_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "search_report.md"
            generate_search_report(self.records, self.manifest, output_path, format="md")
            content = output_path.read_text()
            self.assertIn("test-run", content)

    def test_md_contains_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "search_report.md"
            generate_search_report(self.records, self.manifest, output_path, format="md")
            content = output_path.read_text()
            self.assertIn("openalex", content)
            self.assertIn("crossref", content)

    def test_md_contains_results_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "search_report.md"
            generate_search_report(self.records, self.manifest, output_path, format="md")
            content = output_path.read_text()
            self.assertIn("Total records identified: 150", content)
            self.assertIn("Records after deduplication: 130", content)

    def test_md_contains_validation_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "search_report.md"
            generate_search_report(self.records, self.manifest, output_path, format="md")
            content = output_path.read_text()
            self.assertIn("VALIDATED: 100", content)
            self.assertIn("NO_DOI: 30", content)

    def test_md_contains_evidence_maps(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "search_report.md"
            generate_search_report(self.records, self.manifest, output_path, format="md")
            content = output_path.read_text()
            self.assertIn("By Publication Year", content)
            self.assertIn("By Venue", content)
            self.assertIn("By Topic", content)

    def test_invalid_format_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "search_report.txt"
            with self.assertRaises(ValueError):
                generate_search_report(self.records, self.manifest, output_path, format="txt")


class TestGenerateEvidenceMaps(unittest.TestCase):
    """Test generate_evidence_maps function."""

    def setUp(self):
        self.records = [
            Record(doi="10.9999/aaa", title="Paper 1", year=2018, authors=["A"], venue="Journal A", keywords=["kw1", "kw2"], publication_type="journal-article", source="openalex"),
            Record(doi="10.9999/bbb", title="Paper 2", year=2019, authors=["B"], venue="Journal B", keywords=["kw2", "kw3"], publication_type="journal-article", source="crossref"),
            Record(doi="10.9999/ccc", title="Paper 3", year=2018, authors=["C"], venue="Journal A", keywords=["kw1"], publication_type="conference", source="openalex"),
        ]

    def test_creates_expected_csv_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = generate_evidence_maps(self.records, output_dir)

            expected = ["by_year", "by_venue", "by_keyword", "by_type", "by_source"]
            for key in expected:
                self.assertIn(key, paths)
                self.assertTrue(paths[key].exists(), f"Missing file: {key}")

    def test_by_year_csv_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = generate_evidence_maps(self.records, output_dir)
            content = paths["by_year"].read_text()
            lines = content.strip().split("\n")
            self.assertEqual(lines[0], "year,count")
            # 2018: 2, 2019: 1
            self.assertIn("2018,2", content)
            self.assertIn("2019,1", content)

    def test_by_venue_csv_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = generate_evidence_maps(self.records, output_dir)
            content = paths["by_venue"].read_text()
            lines = content.strip().split("\n")
            self.assertEqual(lines[0], "venue,count")
            self.assertIn("Journal A,2", content)
            self.assertIn("Journal B,1", content)

    def test_by_keyword_csv_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = generate_evidence_maps(self.records, output_dir)
            content = paths["by_keyword"].read_text()
            lines = content.strip().split("\n")
            self.assertEqual(lines[0], "keyword,count")
            self.assertIn("kw1,2", content)
            self.assertIn("kw2,2", content)
            self.assertIn("kw3,1", content)

    def test_by_type_csv_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = generate_evidence_maps(self.records, output_dir)
            content = paths["by_type"].read_text()
            lines = content.strip().split("\n")
            self.assertEqual(lines[0], "publication_type,count")
            self.assertIn("journal-article,2", content)
            self.assertIn("conference,1", content)

    def test_by_source_csv_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            paths = generate_evidence_maps(self.records, output_dir)
            content = paths["by_source"].read_text()
            lines = content.strip().split("\n")
            self.assertEqual(lines[0], "source,count")
            self.assertIn("openalex,2", content)
            self.assertIn("crossref,1", content)


if __name__ == "__main__":
    unittest.main()