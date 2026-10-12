# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for dual-reviewer agreement in lithos.screen (kappa, reports, round-trips)."""
from testhelpers import add_src_path
add_src_path()

import csv
import json
import tempfile
from pathlib import Path
import unittest

from lithos.screen import (
    AgreementReport,
    ScreeningSession,
    ScreenState,
    cohens_kappa,
)
from testhelpers import make_record


def _make_session(records=None, reviewers=("R1", "R2")):
    """Build a ScreeningSession with synthetic records."""
    if records is None:
        records = [
            make_record(id="1", title="Soil consolidation settlement"),
            make_record(id="2", title="Slope stability analysis", year=2019),
            make_record(id="3", title="Bearing capacity of shallow foundations", year=2020),
        ]
    return ScreeningSession(records=list(records), reviewers=list(reviewers))


class TestCohensKappa(unittest.TestCase):
    """Tests for cohens_kappa."""

    def test_perfect_agreement(self):
        """Identical label lists give kappa of 1.0."""
        labels = ["INCLUDE", "INCLUDE", "EXCLUDE"]
        self.assertEqual(cohens_kappa(labels, list(labels)), 1.0)

    def test_hand_computed_case(self):
        """Hand-computed case: po=0.75, pe=0.5 so kappa=0.5."""
        labels_1 = ["INCLUDE", "INCLUDE", "EXCLUDE", "EXCLUDE"]
        labels_2 = ["INCLUDE", "EXCLUDE", "EXCLUDE", "EXCLUDE"]
        self.assertAlmostEqual(cohens_kappa(labels_1, labels_2), 0.5)

    def test_empty_lists_raise(self):
        """Empty label lists raise ValueError."""
        with self.assertRaises(ValueError):
            cohens_kappa([], [])

    def test_unequal_lengths_raise(self):
        """Unequal-length label lists raise ValueError."""
        with self.assertRaises(ValueError):
            cohens_kappa(["INCLUDE", "EXCLUDE"], ["INCLUDE"])
        with self.assertRaises(ValueError):
            cohens_kappa(["INCLUDE"], ["INCLUDE", "EXCLUDE"])

    def test_systematic_disagreement_negative(self):
        """Complete disagreement gives po=0.0 and kappa=-1.0."""
        labels_1 = ["INCLUDE", "EXCLUDE"]
        labels_2 = ["EXCLUDE", "INCLUDE"]
        n = len(labels_1)
        po = sum(1 for a, b in zip(labels_1, labels_2) if a == b) / n
        self.assertEqual(po, 0.0)
        kappa = cohens_kappa(labels_1, labels_2)
        self.assertEqual(kappa, -1.0)
        self.assertLessEqual(kappa, po)


class TestAgreementReport(unittest.TestCase):
    """Tests for ScreeningSession.agreement_report."""

    def setUp(self):
        self.session = _make_session()
        self.session.record_decision("1", "R1", ScreenState.INCLUDE, "relevant")
        self.session.record_decision("1", "R2", ScreenState.INCLUDE, "agree")
        self.session.record_decision("2", "R1", ScreenState.INCLUDE, "maybe")
        self.session.record_decision("2", "R2", ScreenState.EXCLUDE, "no")
        self.session.record_decision("3", "R1", ScreenState.EXCLUDE, "out")
        self.session.record_decision("3", "R2", ScreenState.EXCLUDE, "out")
        self.report = self.session.agreement_report("R1", "R2")

    def test_counts_and_kappa(self):
        """Three jointly screened records with one disagreement."""
        self.assertEqual(self.report.n_both_screened, 3)
        self.assertEqual(self.report.n_agree, 2)
        # Hand check: po=2/3, pe=(2/3)(1/3)+(1/3)(2/3)=4/9 -> kappa=(2/3-4/9)/(1-4/9)=0.4
        self.assertAlmostEqual(self.report.kappa, 0.4)
        self.assertAlmostEqual(self.report.percent_agreement, 100.0 * 2 / 3)

    def test_conflicts(self):
        """Exactly one conflict, on record 2."""
        self.assertEqual(len(self.report.conflicts), 1)
        self.assertEqual(self.report.conflicts[0]["record_id"], "2")
        self.assertEqual(self.report.conflicts[0]["R1"], "INCLUDE")
        self.assertEqual(self.report.conflicts[0]["R2"], "EXCLUDE")

    def test_confusion_counts(self):
        """Confusion matrix holds the expected pair counts."""
        self.assertEqual(self.report.confusion[("INCLUDE", "INCLUDE")], 1)
        self.assertEqual(self.report.confusion[("INCLUDE", "EXCLUDE")], 1)
        self.assertEqual(self.report.confusion[("EXCLUDE", "EXCLUDE")], 1)
        self.assertEqual(len(self.report.confusion), 3)

    def test_to_dict_keys(self):
        """to_dict exposes the documented keys."""
        data = self.report.to_dict()
        expected = {
            "reviewer_1",
            "reviewer_2",
            "n_both_screened",
            "n_agree",
            "kappa",
            "percent_agreement",
            "confusion",
            "n_conflicts",
            "conflicts",
        }
        self.assertEqual(set(data.keys()), expected)
        self.assertEqual(data["reviewer_1"], "R1")
        self.assertEqual(data["reviewer_2"], "R2")
        self.assertEqual(data["n_both_screened"], 3)
        self.assertEqual(data["n_agree"], 2)
        self.assertEqual(data["n_conflicts"], 1)
        self.assertEqual(data["kappa"], 0.4)
        self.assertEqual(data["confusion"]["INCLUDE|EXCLUDE"], 1)

    def test_single_reviewer_records_ignored(self):
        """Records screened by only one reviewer are excluded from the report."""
        self.session.record_decision("4", "R1", ScreenState.INCLUDE, "only R1")
        report = self.session.agreement_report("R1", "R2")
        self.assertEqual(report.n_both_screened, 3)
        self.assertEqual(report.n_agree, 2)
        self.assertEqual(len(report.conflicts), 1)
        self.assertNotIn("4", {c["record_id"] for c in report.conflicts})

    def test_empty_report_defaults(self):
        """A default AgreementReport serialises with zero counts."""
        data = AgreementReport().to_dict()
        self.assertEqual(data["n_both_screened"], 0)
        self.assertEqual(data["n_agree"], 0)
        self.assertEqual(data["kappa"], 0.0)
        self.assertEqual(data["confusion"], {})
        self.assertEqual(data["conflicts"], [])


class TestExportAgreement(unittest.TestCase):
    """Tests for ScreeningSession.export_agreement."""

    def test_writes_summary_and_conflicts(self):
        """agreement_summary.md and conflicts.csv are written with content."""
        session = _make_session()
        session.record_decision("1", "R1", ScreenState.INCLUDE, "relevant")
        session.record_decision("1", "R2", ScreenState.INCLUDE, "agree")
        session.record_decision("2", "R1", ScreenState.INCLUDE, "maybe")
        session.record_decision("2", "R2", ScreenState.EXCLUDE, "no")
        session.record_decision("3", "R1", ScreenState.EXCLUDE, "out")
        session.record_decision("3", "R2", ScreenState.EXCLUDE, "out")
        report = session.agreement_report("R1", "R2")
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            session.export_agreement(report, out_dir)
            summary = (out_dir / "agreement_summary.md").read_text()
            with (out_dir / "conflicts.csv").open(newline="", encoding="utf-8") as fh:
                rows = list(csv.reader(fh))
        self.assertIn("Cohen's kappa", summary)
        self.assertIn(f"{report.kappa:.4f}", summary)
        self.assertEqual(len(rows), 2)
        self.assertIn("record_id", rows[0])
        self.assertEqual(rows[1][0], "2")


class TestReviewerFormRoundTrip(unittest.TestCase):
    """Tests for export_reviewer_form / import_reviewer_decisions."""

    def test_form_round_trip(self):
        """Export a blank form, fill two decisions, import them back."""
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "R1.csv"
            session.export_reviewer_form(path, "R1")
            with path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 3)
            rows[0]["decision"] = "INCLUDE"
            rows[0]["reason"] = "relevant"
            rows[1]["decision"] = "EXCLUDE"
            rows[1]["reason"] = "out of scope"
            with path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            imported = session.import_reviewer_decisions(path, "R1")
        self.assertEqual(imported, 2)
        self.assertIn("1", session.decisions)
        self.assertIn("2", session.decisions)
        self.assertEqual(session.decisions["1"]["R1"].decision, ScreenState.INCLUDE)
        self.assertEqual(session.decisions["1"]["R1"].notes, "relevant")
        self.assertEqual(session.decisions["2"]["R1"].decision, ScreenState.EXCLUDE)
        self.assertEqual(session.decisions["2"]["R1"].notes, "out of scope")
        self.assertNotIn("3", session.decisions)


class TestDecisionsRoundTrip(unittest.TestCase):
    """Tests for export_decisions / load_decisions round-trip."""

    def test_decisions_round_trip(self):
        """export_decisions output is returned unchanged by load_decisions."""
        session = _make_session()
        session.record_decision("1", "R1", ScreenState.INCLUDE, "yes")
        session.record_decision("1", "R2", ScreenState.EXCLUDE, "no")
        session.record_decision("2", "R1", ScreenState.EXCLUDE, "skip")
        expected = {
            "reviewers": ["R1", "R2"],
            "decisions": {
                "1": {
                    "R1": {"decision": "INCLUDE", "notes": "yes"},
                    "R2": {"decision": "EXCLUDE", "notes": "no"},
                },
                "2": {
                    "R1": {"decision": "EXCLUDE", "notes": "skip"},
                },
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.json"
            session.export_decisions(path)
            raw = json.loads(path.read_text())
            loaded = ScreeningSession.load_decisions(path)
        self.assertEqual(raw, expected)
        self.assertEqual(loaded, expected)


if __name__ == "__main__":
    unittest.main()
