# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.dashboard offline HTML dashboard."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import json
import tempfile
from pathlib import Path
import unittest

from lithos._version import VERSION
from lithos.dashboard import build_dashboard
from testhelpers import make_record


def extract_payload(html: str) -> tuple[str, dict]:
    """Return (raw_payload_text, parsed_payload) from the embedded const DATA= line."""
    start = html.index("const DATA=") + len("const DATA=")
    end = html.index(";\n", start)
    raw = html[start:end]
    return raw, json.loads(raw)


class TestBuildDashboard(unittest.TestCase):
    """Tests for build_dashboard HTML generation."""

    def test_writes_file_and_returns_path(self):
        """build_dashboard writes a non-empty file and returns the Path."""
        records = [make_record(id="r1")]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "dashboard.html"
            result = build_dashboard(records, out)
            self.assertIsInstance(result, Path)
            self.assertEqual(result, out)
            self.assertTrue(result.exists())
            self.assertGreater(result.stat().st_size, 0)
            self.assertGreater(len(result.read_text(encoding="utf-8")), 0)

    def test_html_contains_version_and_title(self):
        """HTML embeds the current VERSION and the dashboard title."""
        records = [make_record(id="r1")]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "dashboard.html"
            build_dashboard(records, out)
            html = out.read_text(encoding="utf-8")
        self.assertIn("LITHOS screening dashboard", html)
        self.assertIn(VERSION, html)

    def test_dataset_id_embedded(self):
        """dataset_id string is embedded in the payload JSON."""
        records = [make_record(id="r1", title="Slope stability analysis")]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "dashboard.html"
            build_dashboard(records, out, dataset_id="unit-test-ds")
            html = out.read_text(encoding="utf-8")
        _, payload = extract_payload(html)
        self.assertEqual(payload["dataset_id"], "unit-test-ds")
        self.assertIn("unit-test-ds", html)
        self.assertIn("Slope stability analysis", html)

    def test_three_records_embedded(self):
        """All record ids of a 3-record dataset appear in the embedded payload."""
        records = [
            make_record(id="rec-a", title="Soil consolidation settlement"),
            make_record(id="rec-b", title="Slope stability analysis"),
            make_record(id="rec-c", title="Bearing capacity of shallow foundations"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "dashboard.html"
            build_dashboard(records, out, dataset_id="ds3")
            html = out.read_text(encoding="utf-8")
        _, payload = extract_payload(html)
        self.assertEqual(len(payload["records"]), 3)
        embedded_ids = {r["id"] for r in payload["records"]}
        self.assertEqual(embedded_ids, {"rec-a", "rec-b", "rec-c"})
        for rid in ("rec-a", "rec-b", "rec-c"):
            self.assertIn(rid, html)
        for title in (
            "Soil consolidation settlement",
            "Slope stability analysis",
            "Bearing capacity of shallow foundations",
        ):
            self.assertIn(title, html)

    def test_end_tag_escaping(self):
        """A title containing </script> is escaped so the HTML stays well-formed."""
        records = [make_record(id="x1", title="Concrete durability </script> chloride ingress")]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "dashboard.html"
            build_dashboard(records, out)
            html = out.read_text(encoding="utf-8")
        raw, _ = extract_payload(html)
        self.assertIn("<\\/script>", raw)
        self.assertNotIn("</script>", raw)
        self.assertIn("<\\/script>", html)

    def test_rules_go_into_payload_reasons(self):
        """Rule descriptions are placed into the payload rules.reasons list."""
        rules = {
            "rules": [
                {"pattern": "wrong population", "description": "wrong population"},
                {"pattern": "no abstract"},
            ]
        }
        records = [make_record(id="r1")]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "dashboard.html"
            build_dashboard(records, out, rules=rules)
            html = out.read_text(encoding="utf-8")
        raw, payload = extract_payload(html)
        self.assertIn("wrong population", payload["rules"]["reasons"])
        self.assertIn("no abstract", payload["rules"]["reasons"])
        self.assertIn("wrong population", raw)

    def test_parent_directory_created(self):
        """Output parent directory is created when missing."""
        records = [make_record(id="r1")]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "nested" / "deeper" / "dashboard.html"
            self.assertFalse(out.parent.exists())
            result = build_dashboard(records, out)
            self.assertTrue(result.exists())
            self.assertGreater(result.stat().st_size, 0)

    def test_html_is_self_contained(self):
        """Generated HTML needs no network: no cdn. and no https://."""
        records = [make_record(id="r1")]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "dashboard.html"
            build_dashboard(records, out)
            html = out.read_text(encoding="utf-8")
        self.assertNotIn("cdn.", html)
        self.assertNotIn("https://", html)

    def test_reviewer_embedded(self):
        """reviewer string is embedded in the payload."""
        records = [make_record(id="r1")]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "dashboard.html"
            build_dashboard(records, out, reviewer="R1")
            html = out.read_text(encoding="utf-8")
        _, payload = extract_payload(html)
        self.assertEqual(payload["reviewer"], "R1")
        self.assertIn('"reviewer": "R1"', html)


if __name__ == "__main__":
    unittest.main()
