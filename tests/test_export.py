# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.export module."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import json
import tempfile
import zipfile
from pathlib import Path
import unittest
from lithos.export import (
    export_records,
    ExportFormat,
    _export_csv,
    _export_json,
    _export_ris,
    _export_bibtex,
    _export_csl_json,
    _export_xlsx,
)
from lithos.models import Record, RecordStatus, ScreenState


class TestExportCSV(unittest.TestCase):
    """Tests for CSV export."""

    def setUp(self):
        self.records = [
            Record(
                doi="10.9999/aaa",
                title="Soil consolidation settlement",
                year=2018,
                authors=["Alpha, A.", "Beta, B."],
                venue="Geotechnical Journal",
                abstract="Test abstract",
                keywords=["consolidation", "settlement"],
                publication_type="journal-article",
                cited_by=5,
                source="openalex",
                query_hits=["query1"],
                status=RecordStatus.VALIDATED,
                flags=[],
                completeness_score=0.9,
                screen_state=ScreenState.INCLUDE,
                screen_notes="Relevant",
                reviewer_decisions={"r1": ScreenState.INCLUDE},
                dedup_cluster_id="cluster_1",
                dedup_master=True,
            ),
            Record(
                doi="10.9999/bbb",
                title="Slope stability analysis",
                year=2020,
                authors=["Gamma, G."],
                venue="Slope Journal",
                abstract="Slope abstract",
                keywords=["slope", "stability"],
                publication_type="journal-article",
                cited_by=3,
                source="crossref",
                query_hits=["query2"],
                status=RecordStatus.NO_DOI,
                flags=["no_doi"],
                completeness_score=0.7,
                screen_state=ScreenState.UNSCREENED,
                screen_notes="",
                reviewer_decisions={},
                dedup_cluster_id=None,
                dedup_master=False,
            ),
        ]

    def test_write_csv_has_header(self):
        """CSV output has correct header row."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.csv"
            _export_csv(self.records, path)
            content = path.read_text()
            lines = content.strip().split("\n")
            self.assertEqual(lines[0], "id,doi,pmid,arxiv_id,semantic_scholar_id,core_id,title,year,authors,venue,volume,issue,pages,abstract,keywords,publication_type,cited_by,source,query_hits,status,flags,completeness_score,screen_state,screen_notes,reviewer_decisions,dedup_cluster_id,dedup_master")

    def test_write_csv_data_rows(self):
        """CSV contains data rows for each record."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.csv"
            _export_csv(self.records, path)
            content = path.read_text()
            lines = content.strip().split("\n")
            self.assertEqual(len(lines), 3)  # header + 2 records
            self.assertIn("10.9999/aaa", lines[1])
            self.assertIn("Soil consolidation settlement", lines[1])
            self.assertIn("Alpha, A.; Beta, B.", lines[1])
            self.assertIn("INCLUDE", lines[1])
            self.assertIn("True", lines[1])  # dedup_master
            self.assertIn("10.9999/bbb", lines[2])
            self.assertIn("Slope stability analysis", lines[2])

    def test_csv_escapes_quotes(self):
        """CSV handles quotes in fields."""
        rec = Record(title='Title with "quotes"', authors=["Author, A."], source="test")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.csv"
            _export_csv([rec], path)
            content = path.read_text()
            # CSV writer should handle quotes
            self.assertIn('Title with', content)


class TestExportJSON(unittest.TestCase):
    """Tests for JSON export."""

    def setUp(self):
        self.records = [
            Record(
                doi="10.9999/aaa",
                title="Test Title",
                year=2018,
                authors=["Alpha, A."],
                source="openalex",
            )
        ]

    def test_json_roundtrip(self):
        """JSON export round-trips to list of dicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            _export_json(self.records, path)
            data = json.loads(path.read_text())
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["doi"], "10.9999/aaa")
        self.assertEqual(data[0]["title"], "Test Title")
        self.assertEqual(data[0]["year"], 2018)

    def test_json_includes_all_fields(self):
        """JSON includes all record fields."""
        rec = Record(
            doi="10.9999/aaa",
            title="Test",
            year=2018,
            authors=["A"],
            venue="Venue",
            volume="10",
            issue="2",
            pages="1-10",
            abstract="Abstract",
            keywords=["kw1", "kw2"],
            publication_type="journal-article",
            cited_by=5,
            source="test",
            query_hits=["q1"],
            status=RecordStatus.VALIDATED,
            flags=["flag1"],
            completeness_score=0.8,
            screen_state=ScreenState.INCLUDE,
            screen_notes="Notes",
            reviewer_decisions={"r1": ScreenState.INCLUDE},
            dedup_cluster_id="c1",
            dedup_master=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            _export_json([rec], path)
            data = json.loads(path.read_text())[0]
        self.assertEqual(data["venue"], "Venue")
        self.assertEqual(data["volume"], "10")
        self.assertEqual(data["keywords"], ["kw1", "kw2"])
        self.assertEqual(data["status"], "VALIDATED")
        self.assertEqual(data["screen_state"], "INCLUDE")
        self.assertEqual(data["dedup_cluster_id"], "c1")
        self.assertTrue(data["dedup_master"])


class TestExportRIS(unittest.TestCase):
    """Tests for RIS export."""

    def setUp(self):
        self.records = [
            Record(
                doi="10.9999/aaa",
                title="Soil consolidation settlement",
                year=2018,
                authors=["Alpha, A.", "Beta, B."],
                venue="Geotechnical Journal",
                volume="10",
                issue="2",
                pages="100-110",
                abstract="Test abstract line 1\nLine 2",
                keywords=["consolidation", "settlement"],
                source="openalex",
            )
        ]

    def test_ris_contains_ty_and_er(self):
        """RIS output contains TY and ER markers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.ris"
            _export_ris(self.records, path)
            content = path.read_text()
        self.assertIn("TY  - JOUR", content)
        self.assertIn("ER  - ", content)

    def test_ris_contains_doi(self):
        """RIS contains DOI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.ris"
            _export_ris(self.records, path)
            content = path.read_text()
        self.assertIn("DO  - 10.9999/aaa", content)

    def test_ris_contains_title(self):
        """RIS contains title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.ris"
            _export_ris(self.records, path)
            content = path.read_text()
        self.assertIn("TI  - Soil consolidation settlement", content)

    def test_ris_contains_authors(self):
        """RIS contains authors as AU lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.ris"
            _export_ris(self.records, path)
            content = path.read_text()
        self.assertIn("AU  - Alpha, A.", content)
        self.assertIn("AU  - Beta, B.", content)

    def test_ris_contains_year(self):
        """RIS contains year as PY."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.ris"
            _export_ris(self.records, path)
            content = path.read_text()
        self.assertIn("PY  - 2018", content)

    def test_ris_contains_venue(self):
        """RIS contains venue as JO."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.ris"
            _export_ris(self.records, path)
            content = path.read_text()
        self.assertIn("JO  - Geotechnical Journal", content)

    def test_ris_contains_volume_issue_pages(self):
        """RIS contains volume, issue, pages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.ris"
            _export_ris(self.records, path)
            content = path.read_text()
        self.assertIn("VL  - 10", content)
        self.assertIn("IS  - 2", content)
        self.assertIn("SP  - 100", content)
        self.assertIn("EP  - 110", content)

    def test_ris_abstract_multiline(self):
        """RIS abstract handles multi-line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.ris"
            _export_ris(self.records, path)
            content = path.read_text()
        self.assertIn("AB  - Test abstract line 1", content)
        self.assertIn("AB  - Line 2", content)

    def test_ris_keywords(self):
        """RIS contains keywords as KW."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.ris"
            _export_ris(self.records, path)
            content = path.read_text()
        self.assertIn("KW  - consolidation", content)
        self.assertIn("KW  - settlement", content)


class TestExportBibTeX(unittest.TestCase):
    """Tests for BibTeX export."""

    def setUp(self):
        self.records = [
            Record(
                doi="10.9999/aaa",
                title="Soil consolidation settlement",
                year=2018,
                authors=["Alpha, A.", "Beta, B."],
                venue="Geotechnical Journal",
                volume="10",
                issue="2",
                pages="100-110",
                abstract="Test abstract",
                keywords=["consolidation", "settlement"],
                source="openalex",
            )
        ]

    def test_bibtex_contains_article(self):
        """BibTeX output contains @article."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.bib"
            _export_bibtex(self.records, path)
            content = path.read_text()
        self.assertIn("@article{", content)

    def test_bibtex_contains_doi(self):
        """BibTeX contains DOI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.bib"
            _export_bibtex(self.records, path)
            content = path.read_text()
        self.assertIn("doi = {10.9999/aaa}", content)

    def test_bibtex_contains_title(self):
        """BibTeX contains title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.bib"
            _export_bibtex(self.records, path)
            content = path.read_text()
        self.assertIn("title = {Soil consolidation settlement}", content)

    def test_bibtex_contains_authors(self):
        """BibTeX contains authors joined by 'and'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.bib"
            _export_bibtex(self.records, path)
            content = path.read_text()
        self.assertIn("author = {Alpha, A. and Beta, B.}", content)

    def test_bibtex_contains_year(self):
        """BibTeX contains year."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.bib"
            _export_bibtex(self.records, path)
            content = path.read_text()
        self.assertIn("year = {2018}", content)

    def test_bibtex_contains_journal(self):
        """BibTeX contains journal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.bib"
            _export_bibtex(self.records, path)
            content = path.read_text()
        self.assertIn("journal = {Geotechnical Journal}", content)

    def test_bibtex_citation_key_format(self):
        """BibTeX citation key follows expected format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.bib"
            _export_bibtex(self.records, path)
            content = path.read_text()
        # Key should be based on first author surname + year + first title word
        self.assertIn("@article{Alpha2018Soil", content)


class TestExportCSLJSON(unittest.TestCase):
    """Tests for CSL-JSON export."""

    def setUp(self):
        self.records = [
            Record(
                doi="10.9999/aaa",
                title="Soil consolidation settlement",
                year=2018,
                authors=["Alpha, A.", "Beta, B."],
                venue="Geotechnical Journal",
                volume="10",
                issue="2",
                pages="100-110",
                abstract="Test abstract",
                keywords=["consolidation", "settlement"],
                publication_type="journal-article",
                cited_by=5,
                source="openalex",
            )
        ]

    def test_csl_json_valid_json_list(self):
        """CSL-JSON output is valid JSON list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            _export_csl_json(self.records, path)
            data = json.loads(path.read_text())
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_csl_json_has_title(self):
        """CSL-JSON items have title field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            _export_csl_json(self.records, path)
            data = json.loads(path.read_text())
        self.assertEqual(data[0]["title"], "Soil consolidation settlement")

    def test_csl_json_has_author_structure(self):
        """CSL-JSON authors have family/given structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            _export_csl_json(self.records, path)
            data = json.loads(path.read_text())
        authors = data[0]["author"]
        self.assertIsInstance(authors, list)
        self.assertEqual(len(authors), 2)
        self.assertEqual(authors[0]["family"], "Alpha")
        self.assertEqual(authors[0]["given"], "A.")
        self.assertEqual(authors[1]["family"], "Beta")
        self.assertEqual(authors[1]["given"], "B.")

    def test_csl_json_has_issued_date(self):
        """CSL-JSON has issued date-parts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            _export_csl_json(self.records, path)
            data = json.loads(path.read_text())
        self.assertEqual(data[0]["issued"], {"date-parts": [[2018]]})

    def test_csl_json_has_container_title(self):
        """CSL-JSON has container-title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            _export_csl_json(self.records, path)
            data = json.loads(path.read_text())
        self.assertEqual(data[0]["container-title"], "Geotechnical Journal")

    def test_csl_json_has_doi(self):
        """CSL-JSON has DOI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            _export_csl_json(self.records, path)
            data = json.loads(path.read_text())
        self.assertEqual(data[0]["DOI"], "10.9999/aaa")

    def test_csl_json_type_mapping(self):
        """CSL-JSON type maps publication_type correctly."""
        rec = Record(publication_type="preprint", title="Test", year=2020, authors=["A"], source="arxiv")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            _export_csl_json([rec], path)
            data = json.loads(path.read_text())
        self.assertEqual(data[0]["type"], "preprint")

        rec2 = Record(publication_type="conference-paper", title="Test", year=2020, authors=["A"], source="crossref")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            _export_csl_json([rec2], path)
            data = json.loads(path.read_text())
        self.assertEqual(data[0]["type"], "paper-conference")


class TestExportXLSX(unittest.TestCase):
    """Tests for XLSX export (dependency-free OOXML)."""

    def setUp(self):
        self.records = [
            Record(
                doi="10.9999/aaa",
                title="Soil consolidation settlement",
                year=2018,
                authors=["Alpha, A."],
                venue="Geotechnical Journal",
                source="openalex",
            )
        ]

    def test_xlsx_is_valid_zip(self):
        """XLSX output is a valid zip file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.xlsx"
            _export_xlsx(self.records, path)
            self.assertTrue(zipfile.is_zipfile(path))

    def test_xlsx_contains_sheet1_xml(self):
        """XLSX contains xl/worksheets/sheet1.xml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.xlsx"
            _export_xlsx(self.records, path)
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                self.assertIn("xl/worksheets/sheet1.xml", names)

    def test_xlsx_contains_workbook(self):
        """XLSX contains workbook.xml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.xlsx"
            _export_xlsx(self.records, path)
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                self.assertIn("xl/workbook.xml", names)

    def test_xlsx_contains_content_types(self):
        """XLSX contains [Content_Types].xml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.xlsx"
            _export_xlsx(self.records, path)
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                self.assertIn("[Content_Types].xml", names)

    def test_xlsx_sheet_has_header_row(self):
        """Sheet XML contains header row."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.xlsx"
            _export_xlsx(self.records, path)
            with zipfile.ZipFile(path, "r") as zf:
                sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("<row r=\"1\">", sheet_xml)
        self.assertIn("title", sheet_xml.lower())

    def test_xlsx_sheet_has_data_row(self):
        """Sheet XML contains data row."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.xlsx"
            _export_xlsx(self.records, path)
            with zipfile.ZipFile(path, "r") as zf:
                sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("<row r=\"2\">", sheet_xml)
        self.assertIn("Soil consolidation settlement", sheet_xml)
        self.assertIn("10.9999/aaa", sheet_xml)

    def test_xlsx_no_openpyxl_dependency(self):
        """XLSX export works without openpyxl (uses zipfile only)."""
        # This test passes if _export_xlsx doesn't import openpyxl
        # We verify by checking the module doesn't have openpyxl import
        import lithos.export as export_module
        self.assertFalse(hasattr(export_module, "openpyxl"))


class TestExportRecordsDispatcher(unittest.TestCase):
    """Tests for export_records dispatcher function."""

    def setUp(self):
        self.records = [Record(title="Test", year=2020, authors=["A"], source="test")]

    def test_export_records_csv(self):
        """export_records with CSV format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.csv"
            export_records(self.records, path, ExportFormat.CSV)
            self.assertTrue(path.exists())

    def test_export_records_json(self):
        """export_records with JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            export_records(self.records, path, ExportFormat.JSON)
            self.assertTrue(path.exists())

    def test_export_records_ris(self):
        """export_records with RIS format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.ris"
            export_records(self.records, path, ExportFormat.RIS)
            self.assertTrue(path.exists())

    def test_export_records_bibtex(self):
        """export_records with BIBTEX format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.bib"
            export_records(self.records, path, ExportFormat.BIBTEX)
            self.assertTrue(path.exists())

    def test_export_records_csl_json(self):
        """export_records with CSL_JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            export_records(self.records, path, ExportFormat.CSL_JSON)
            self.assertTrue(path.exists())

    def test_export_records_xlsx(self):
        """export_records with XLSX format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.xlsx"
            export_records(self.records, path, ExportFormat.XLSX)
            self.assertTrue(path.exists())

    def test_export_records_unknown_format_raises(self):
        """export_records raises ValueError for unknown format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.unknown"
            with self.assertRaises(ValueError):
                export_records(self.records, path, "unknown")  # type: ignore[arg-type]

    def test_export_records_include_screened_only(self):
        """export_records filters by screen_state when include_screened_only=True."""
        rec1 = Record(title="Included", screen_state=ScreenState.INCLUDE, source="a")
        rec2 = Record(title="Excluded", screen_state=ScreenState.EXCLUDE, source="b")
        rec3 = Record(title="Unscreened", screen_state=ScreenState.UNSCREENED, source="c")
        records = [rec1, rec2, rec3]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.json"
            export_records(records, path, ExportFormat.JSON, include_screened_only=True)
            data = json.loads(path.read_text())
        self.assertEqual(len(data), 2)
        titles = {r["title"] for r in data}
        self.assertIn("Included", titles)
        self.assertIn("Excluded", titles)
        self.assertNotIn("Unscreened", titles)


if __name__ == "__main__":
    unittest.main()