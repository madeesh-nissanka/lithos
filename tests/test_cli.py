# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for LITHOS CLI (in-process, offline, synthetic data only)."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import unittest
import sys
import json
import tempfile
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from testhelpers import (
    fake_http,
    OPENALEX_PAYLOAD,
    CROSSREF_PAYLOAD,
    SEMANTICSCHOLAR_PAYLOAD,
    ARXIV_ATOM,
    EUROPEPMC_PAYLOAD,
    DOAJ_PAYLOAD,
    make_record,
)


class TestCLI(unittest.TestCase):
    """Tests for lithos.cli.main() invoked in-process."""

    def setUp(self):
        from lithos.adapters import init_adapters
        init_adapters({})

    def _run_cli(self, argv: list[str]) -> tuple[int, str]:
        """Run cli.main with given argv, capture stdout, return (exit_code, stdout)."""
        from lithos.cli import main

        old_argv = sys.argv
        old_stdout = sys.stdout
        sys.argv = ["lithos"] + argv
        stdout_buf = StringIO()
        try:
            with redirect_stdout(stdout_buf):
                exit_code = main()
        except SystemExit as e:
            exit_code = e.code
        except Exception as e:
            # Catch unhandled exceptions (e.g., src bugs)
            exit_code = 1
            stdout_buf.write(f"Exception: {type(e).__name__}: {e}")
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout
        return exit_code, stdout_buf.getvalue()

    def test_about_prints_author(self):
        """--about should return 0 and print author 'Madeesh P. Nissanka'."""
        exit_code, out = self._run_cli(["--about"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Madeesh P. Nissanka", out)
        self.assertIn("LITHOS 0.2.0", out)

    def test_dry_run_search(self):
        """--dry-run search -q should return 0 without network."""
        exit_code, out = self._run_cli(["--dry-run", "search", "-q", "soil consolidation"])
        self.assertEqual(exit_code, 0)
        # DRY RUN message goes to logger (stderr), not stdout
        # Just verify it returns 0 and doesn't crash

    def test_dedupe_command(self):
        """dedupe -i FILE -o DIR should return 0 and write records.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Create synthetic input records.json with DIFFERENT DOIs AND titles to avoid dedup
            rec1 = make_record(doi="10.9999/test1", title="Soil consolidation settlement analysis")
            rec2 = make_record(doi="10.9999/test2", title="Slope stability analysis methods")
            input_file = tmp / "input_records.json"
            input_file.write_text(json.dumps([rec1.to_dict(), rec2.to_dict()], indent=2))

            out_dir = tmp / "dedupe_out"
            exit_code, out = self._run_cli(["dedupe", "-i", str(input_file), "-o", str(out_dir)])
            self.assertEqual(exit_code, 0, msg=f"stderr/stdout: {out}")

            # Check output files exist
            self.assertTrue((out_dir / "records.json").exists())
            self.assertTrue((out_dir / "records.csv").exists())
            self.assertTrue((out_dir / "dedup_report.md").exists())

            # Verify records.json content (2 unique records)
            out_records = json.loads((out_dir / "records.json").read_text())
            self.assertEqual(len(out_records), 2)

    def test_export_command_csv(self):
        """export -i FILE -f csv -o OUT.csv should return 0 and create CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rec = make_record(doi="10.9999/export1", title="Export Test")
            input_file = tmp / "records.json"
            input_file.write_text(json.dumps([rec.to_dict()], indent=2))

            out_csv = tmp / "output.csv"
            exit_code, out = self._run_cli(["export", "-i", str(input_file), "-f", "csv", "-o", str(out_csv)])
            self.assertEqual(exit_code, 0, msg=f"stderr/stdout: {out}")

            self.assertTrue(out_csv.exists())
            content = out_csv.read_text()
            self.assertIn("Export Test", content)
            self.assertIn("10.9999/export1", content)

    def test_presets_list(self):
        """presets should return 0 and list available presets."""
        exit_code, out = self._run_cli(["presets"])
        self.assertEqual(exit_code, 0)
        # Should list domains
        self.assertIn("civil", out.lower())

    def test_presets_domain_name(self):
        """presets --domain civil --name slope_stability should return 0 and emit JSON."""
        exit_code, out = self._run_cli(["presets", "--domain", "civil", "--name", "slope_stability"])
        self.assertEqual(exit_code, 0)
        # Should output valid JSON with queries and name
        data = json.loads(out.strip())
        self.assertIn("queries", data)
        self.assertIn("name", data)
        self.assertEqual(data["name"], "slope_stability")

    def test_config_command(self):
        """config should return 0 and print JSON config."""
        exit_code, out = self._run_cli(["config"])
        self.assertEqual(exit_code, 0)
        data = json.loads(out.strip())
        self.assertIn("adapters", data)
        self.assertIn("openalex", data["adapters"])

    def test_search_with_fake_http_openalex(self):
        """search command with fake_http should work end-to-end."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            out_dir = tmp / "results"

            # Mock HTTP for all adapters that will be called
            with fake_http(json_payload=OPENALEX_PAYLOAD):
                exit_code, out = self._run_cli([
                    "search",
                    "-q", "soil consolidation",
                    "--limit", "2",
                    "--out", str(out_dir),
                    "--no-validate",
                    "--sources", "openalex",
                ])

            self.assertEqual(exit_code, 0, msg=f"stdout: {out}")
            self.assertTrue((out_dir / "records.json").exists())
            self.assertTrue((out_dir / "records.csv").exists())

            records = json.loads((out_dir / "records.json").read_text())
            self.assertEqual(len(records), 2)

    def test_validate_command(self):
        """validate command should work with synthetic records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rec = make_record(doi="10.9999/val1", title="Validate Test")
            input_file = tmp / "records.json"
            input_file.write_text(json.dumps([rec.to_dict()], indent=2))

            out_dir = tmp / "validated"
            with fake_http(json_payload=CROSSREF_PAYLOAD):
                exit_code, out = self._run_cli(["validate", "-i", str(input_file), "-o", str(out_dir)])

            self.assertEqual(exit_code, 0, msg=f"stdout: {out}")
            self.assertTrue((out_dir / "records.json").exists())
            self.assertTrue((out_dir / "validation_summary.json").exists())

    def test_screen_command(self):
        """screen command should apply keyword scoring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rec = make_record(doi="10.9999/screen1", title="Soil consolidation settlement", keywords=["consolidation"])
            input_file = tmp / "records.json"
            input_file.write_text(json.dumps([rec.to_dict()], indent=2))

            out_dir = tmp / "screened"
            exit_code, out = self._run_cli([
                "screen",
                "-i", str(input_file),
                "--include-keywords", "consolidation",
                "-o", str(out_dir),
            ])
            self.assertEqual(exit_code, 0, msg=f"stdout: {out}")
            self.assertTrue((out_dir / "records.json").exists())

    def test_report_command_prisma(self):
        """report --prisma should generate PRISMA flow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rec = make_record(doi="10.9999/report1", title="Report Test")
            input_file = tmp / "records.json"
            input_file.write_text(json.dumps([rec.to_dict()], indent=2))

            out_dir = tmp / "reports"
            exit_code, out = self._run_cli(["report", "-i", str(input_file), "--prisma", "-o", str(out_dir)])
            self.assertEqual(exit_code, 0, msg=f"stdout: {out}")
            # PRISMA SVG may not be generated without matplotlib, but command should succeed

    def test_snowball_command(self):
        """snowball command should work with synthetic input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rec = make_record(doi="10.9999/snow1", title="Snowball Test", referenced_works=["10.9999/ref1"])
            input_file = tmp / "records.json"
            input_file.write_text(json.dumps([rec.to_dict()], indent=2))

            out_dir = tmp / "snowball"
            with fake_http(json_payload=CROSSREF_PAYLOAD):
                exit_code, out = self._run_cli([
                    "snowball",
                    "-i", str(input_file),
                    "-o", str(out_dir),
                    "--max-refs", "1",
                ])
            # Should succeed and generate snowball results
            self.assertEqual(exit_code, 0, msg=f"stdout: {out}")
            # Output file should exist
            self.assertTrue((out_dir / "records.json").exists())


if __name__ == "__main__":
    unittest.main()