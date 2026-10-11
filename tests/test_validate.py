# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.validate module."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import tempfile
from pathlib import Path
import unittest
from unittest import mock

from lithos.models import Record, RecordStatus
from lithos.validate import (
    validate_record,
    ValidationConfig,
    compute_completeness_score,
    first_author_surname,
    title_similarity,
    load_predatory_list,
    check_retraction,
    DEFAULT_PREDATORY_VENUES,
)


class TestValidateRecordNoDoi(unittest.TestCase):
    """Test validate_record NO_DOI path."""

    def test_no_doi_sets_status_no_doi(self):
        record = Record(title="Test", year=2020, authors=["A. Author"], venue="Journal", abstract="Abstract")
        result = validate_record(record)
        self.assertEqual(record.status, RecordStatus.NO_DOI)
        self.assertEqual(result.status, RecordStatus.NO_DOI)
        self.assertIn("no_doi", record.flags)

    def test_no_doi_returns_validation_result(self):
        record = Record(title="Test")
        result = validate_record(record)
        self.assertEqual(result.record_id, record.id)
        self.assertEqual(result.flags, ["no_doi"])


class TestTitleSimilarity(unittest.TestCase):
    """Test title_similarity function."""

    def test_identical_titles_return_1_0(self):
        sim = title_similarity("Soil consolidation settlement", "Soil consolidation settlement")
        self.assertEqual(sim, 1.0)

    def test_similar_titles_return_high_score(self):
        sim = title_similarity("Soil consolidation settlement of soft clay", "Soil consolidation settlement of clay")
        self.assertGreater(sim, 0.8)

    def test_different_titles_return_low_score(self):
        sim = title_similarity("Soil consolidation", "Slope stability analysis")
        self.assertLess(sim, 0.5)

    def test_empty_titles_return_0(self):
        sim = title_similarity("", "Something")
        self.assertEqual(sim, 0.0)
        sim = title_similarity("Something", "")
        self.assertEqual(sim, 0.0)

    def test_case_insensitive(self):
        sim = title_similarity("SOIL CONSOLIDATION", "soil consolidation")
        self.assertEqual(sim, 1.0)

    def test_punctuation_ignored(self):
        sim = title_similarity("Soil consolidation: settlement!", "Soil consolidation settlement")
        self.assertEqual(sim, 1.0)


class TestComputeCompletenessScore(unittest.TestCase):
    """Test compute_completeness_score function."""

    def test_full_record_high_score(self):
        record = Record(
            doi="10.9999/aaa",
            title="Test",
            year=2020,
            authors=["A. Author"],
            venue="Journal",
            abstract="This is a sufficiently long abstract for testing purposes.",
            keywords=["kw1", "kw2"],
            cited_by=5,
        )
        weights = {
            "has_doi": 0.25,
            "has_abstract": 0.20,
            "has_authors": 0.15,
            "has_venue": 0.15,
            "has_year": 0.10,
            "has_keywords": 0.10,
            "has_citations": 0.05,
        }
        score = compute_completeness_score(record, weights)
        self.assertGreaterEqual(score, 0.9)

    def test_empty_record_low_score(self):
        record = Record(title="Test")
        weights = {
            "has_doi": 0.25,
            "has_abstract": 0.20,
            "has_authors": 0.15,
            "has_venue": 0.15,
            "has_year": 0.10,
            "has_keywords": 0.10,
            "has_citations": 0.05,
        }
        score = compute_completeness_score(record, weights)
        self.assertLess(score, 0.3)

    def test_score_capped_at_1_0(self):
        record = Record(
            doi="10.9999/aaa",
            title="Test",
            year=2020,
            authors=["A. Author"],
            venue="Journal",
            abstract="Long abstract " * 10,
            keywords=["kw1"],
            cited_by=100,
        )
        weights = {k: 1.0 for k in ["has_doi", "has_abstract", "has_authors", "has_venue", "has_year", "has_keywords", "has_citations"]}
        score = compute_completeness_score(record, weights)
        self.assertLessEqual(score, 1.0)


class TestFirstAuthorSurname(unittest.TestCase):
    """Test first_author_surname function."""

    def test_surname_given_format(self):
        surname = first_author_surname(["Surname, Given"])
        self.assertEqual(surname, "surname")

    def test_given_surname_format(self):
        surname = first_author_surname(["Given Surname"])
        self.assertEqual(surname, "surname")

    def test_multiple_authors_returns_first(self):
        surname = first_author_surname(["First, A.", "Second, B."])
        self.assertEqual(surname, "first")

    def test_empty_list_returns_none(self):
        surname = first_author_surname([])
        self.assertIsNone(surname)

    def test_strips_whitespace(self):
        surname = first_author_surname(["  Surname, Given  "])
        self.assertEqual(surname, "surname")

    def test_single_name_returns_name(self):
        surname = first_author_surname(["Cher"])
        self.assertEqual(surname, "cher")


class TestCheckRetraction(unittest.TestCase):
    """Test check_retraction function."""

    def test_detects_retraction_in_update_to(self):
        crossref_data = {
            "update-to": [
                {"type": "retraction", "doi": "10.9999/retracted"},
                {"type": "correction", "doi": "10.9999/correction"},
            ]
        }
        self.assertTrue(check_retraction(crossref_data))

    def test_detects_withdrawal_in_update_to(self):
        crossref_data = {
            "update-to": [
                {"type": "withdrawal", "doi": "10.9999/withdrawn"},
            ]
        }
        self.assertTrue(check_retraction(crossref_data))

    def test_no_retraction_returns_false(self):
        crossref_data = {
            "update-to": [
                {"type": "correction", "doi": "10.9999/correction"},
            ]
        }
        self.assertFalse(check_retraction(crossref_data))

    def test_empty_update_to_returns_false(self):
        crossref_data = {"update-to": []}
        self.assertFalse(check_retraction(crossref_data))

    def test_missing_update_to_returns_false(self):
        crossref_data = {}
        self.assertFalse(check_retraction(crossref_data))


class TestLoadPredatoryList(unittest.TestCase):
    """Test load_predatory_list function."""

    def test_missing_file_returns_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nonexistent.txt"
            result = load_predatory_list(path)
            self.assertEqual(result, DEFAULT_PREDATORY_VENUES)

    def test_loads_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predatory.txt"
            path.write_text("bad journal\nanother bad\n# comment\n")
            result = load_predatory_list(path)
            self.assertEqual(result, ["bad journal", "another bad"])

    def test_skips_empty_lines_and_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "predatory.txt"
            path.write_text("\n# comment\n  \njournal\n")
            result = load_predatory_list(path)
            self.assertEqual(result, ["journal"])


class TestValidateRecordWithConfig(unittest.TestCase):
    """Test validate_record with ValidationConfig options."""

    def test_check_crossref_false_sets_validated_for_full_record(self):
        record = Record(
            doi="10.9999/aaa",
            title="Soil consolidation settlement",
            year=2020,
            authors=["Author, A."],
            venue="Journal",
            abstract="Long abstract " * 10,
            keywords=["kw1"],
            cited_by=5,
        )
        config = ValidationConfig(check_crossref=False)
        result = validate_record(record, config)
        self.assertEqual(record.status, RecordStatus.VALIDATED)
        self.assertEqual(result.status, RecordStatus.VALIDATED)

    def test_check_crossref_false_skips_crossref_calls(self):
        record = Record(doi="10.9999/aaa", title="Test", year=2020, authors=["A"], venue="J", abstract="Abs", keywords=["k"])
        config = ValidationConfig(check_crossref=False)
        with mock.patch("lithos.validate.get_adapter") as mock_get:
            validate_record(record, config)
            mock_get.assert_not_called()

    def test_predatory_venue_detected(self):
        record = Record(
            doi="10.9999/aaa",
            title="Test",
            year=2020,
            authors=["A"],
            venue="International Journal of Advanced Research",
            abstract="Abstract",
            keywords=["k"],
        )
        config = ValidationConfig(check_crossref=False)
        result = validate_record(record, config)
        self.assertEqual(record.status, RecordStatus.PREDATORY_VENUE)
        self.assertIn("predatory_venue", record.flags)


class TestValidateRecordTitleMismatch(unittest.TestCase):
    """Test title mismatch flagging."""

    def test_title_mismatch_flag(self):
        record = Record(
            doi="10.9999/aaa",
            title="Completely Different Title",
            year=2020,
            authors=["Author, A."],
            venue="Journal",
            abstract="Abstract",
            keywords=["k"],
        )
        # Mock CrossrefAdapter.validate_doi to return different title
        with mock.patch("lithos.validate.get_adapter") as mock_get:
            from lithos.adapters_crossref import CrossrefAdapter
            mock_adapter = mock.MagicMock(spec=CrossrefAdapter)
            mock_adapter.validate_doi.return_value = {"ok": True, "data": {"title": ["Soil consolidation settlement"]}}
            mock_adapter.check_retraction.return_value = False
            mock_adapter.check_correction.return_value = False
            mock_adapter.get_preprint_relation.return_value = None
            mock_get.return_value = mock_adapter
            config = ValidationConfig(check_crossref=True, title_similarity_threshold=0.9)
            validate_record(record, config)
            self.assertIn("title_mismatch", record.flags)


class TestValidateRecordYearCheck(unittest.TestCase):
    """Test year tolerance in validation."""

    def test_year_off_by_one_flag(self):
        record = Record(
            doi="10.9999/aaa",
            title="Test",
            year=2020,
            authors=["Author, A."],
            venue="Journal",
            abstract="Abstract",
            keywords=["k"],
        )
        with mock.patch("lithos.validate.get_adapter") as mock_get:
            from lithos.adapters_crossref import CrossrefAdapter
            mock_adapter = mock.MagicMock(spec=CrossrefAdapter)
            mock_adapter.validate_doi.return_value = {"ok": True, "data": {"title": ["Test"], "issued": {"date-parts": [[2019]]}, "author": [{"family": "Author"}]}}
            mock_adapter.check_retraction.return_value = False
            mock_adapter.check_correction.return_value = False
            mock_adapter.get_preprint_relation.return_value = None
            mock_get.return_value = mock_adapter
            config = ValidationConfig(check_crossref=True, year_tolerance=1)
            validate_record(record, config)
            self.assertIn("year_off_by_one", record.flags)

    def test_year_mismatch_flag(self):
        record = Record(
            doi="10.9999/aaa",
            title="Test",
            year=2020,
            authors=["Author, A."],
            venue="Journal",
            abstract="Abstract",
            keywords=["k"],
        )
        with mock.patch("lithos.validate.get_adapter") as mock_get:
            from lithos.adapters_crossref import CrossrefAdapter
            mock_adapter = mock.MagicMock(spec=CrossrefAdapter)
            mock_adapter.validate_doi.return_value = {"ok": True, "data": {"title": ["Test"], "issued": {"date-parts": [[2015]]}, "author": [{"family": "Author"}]}}
            mock_adapter.check_retraction.return_value = False
            mock_adapter.check_correction.return_value = False
            mock_adapter.get_preprint_relation.return_value = None
            mock_get.return_value = mock_adapter
            config = ValidationConfig(check_crossref=True, year_tolerance=1)
            validate_record(record, config)
            self.assertIn("year_mismatch", record.flags)


if __name__ == "__main__":
    unittest.main()