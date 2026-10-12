# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.fulltext: OA discovery, extraction, caching, indexing (offline)."""
from testhelpers import add_src_path
add_src_path()

import json
import tempfile
import unittest
from pathlib import Path

from lithos.fulltext import (
    EUROPE_PMC_FULLTEXT,
    FullTextFetcher,
    fetch_full_texts,
    find_oa_locations,
    html_to_text,
    load_full_text,
    pdf_to_text,
    xml_to_text,
)
from testhelpers import make_record

OA_URL = "https://example.org/oa.html"

SLOPE_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Slope stability analysis</title>
  <style>body { color: #222; }</style>
  <script>window.tracker = "script payload must be dropped";</script>
</head>
<body>
  <h1>Slope stability analysis</h1>
  <p>Limit equilibrium methods assume a slip surface and compare resisting moments with driving moments along the failure plane of a cut slope.</p>
  <p>Soil consolidation settlement of soft clay under embankment loading is reported separately in the textbook fixture.</p>
</body>
</html>
"""

MESSY_HTML = (
    "<html><body><h1> Slope   stability\tanalysis </h1>"
    "<style>.hidden{display:none}</style>"
    "<script>var drop_me = 1;</script>"
    "<p>  Embankment   loading  </p></body></html>"
)

JATS_XML = (
    "<article>"
    "<front><article-title>Soil consolidation settlement of soft clay</article-title></front>"
    "<abstract>Consolidation of soft clay under embankment loading.</abstract>"
    "<sec><title>Method</title><p>Excess pore pressure dissipates with time.</p></sec>"
    "</article>"
)

# Literal is padded past the 50-character minimum extraction threshold.
PDF_LITERAL = (
    "Hello consolidation settlement of soft clay under sustained "
    "embankment loading in a textbook example"
)


class FakeClient:
    """Offline stand-in for lithos.http.HTTPClient: canned bytes, no network."""

    def __init__(self, responses=None):
        self.responses = dict(responses or {})
        self.calls = []

    def get_bytes(self, url):
        self.calls.append(url)
        if url not in self.responses:
            raise KeyError(f"no canned response for {url}")
        return self.responses[url]


def oa_record():
    """Record with a single Unpaywall HTML open-access location."""
    return make_record(
        id="rec1",
        pmcid=None,
        doi="10.9999/slope",
        crossref_data={
            "unpaywall": {"best_oa_url": OA_URL, "best_oa_license": "cc-by"}
        },
    )


def no_oa_record():
    """Record with no declared open-access location."""
    return make_record(id="n1", pmcid=None, doi=None, crossref_data={})


class TestHtmlToText(unittest.TestCase):
    """Tests for html_to_text."""

    def test_strips_tags_and_collapses_whitespace(self):
        """Tags are removed and runs of whitespace are collapsed."""
        text = html_to_text(MESSY_HTML)
        self.assertEqual(text, "Slope stability analysis\nEmbankment loading")
        self.assertNotIn("<", text)
        self.assertNotIn(">", text)
        self.assertNotIn("\t", text)
        self.assertNotIn("  ", text)
        self.assertEqual(text, text.strip())

    def test_drops_script_and_style_content(self):
        """script/style bodies never reach the extracted text."""
        text = html_to_text(MESSY_HTML)
        self.assertNotIn("drop_me", text)
        self.assertNotIn("display:none", text)
        self.assertIn("Slope stability analysis", text)
        self.assertIn("Embankment loading", text)


class TestXmlToText(unittest.TestCase):
    """Tests for xml_to_text."""

    def test_extracts_jats_sections(self):
        """Title, abstract and section text are extracted from JATS-like XML."""
        text = xml_to_text(JATS_XML)
        self.assertIn("Soil consolidation settlement of soft clay", text)
        self.assertIn("Consolidation of soft clay under embankment loading.", text)
        self.assertIn("Method", text)
        self.assertIn("Excess pore pressure dissipates with time.", text)

    def test_malformed_xml_returns_empty(self):
        """Malformed XML yields an empty string instead of raising."""
        self.assertEqual(xml_to_text("<article><sec>not closed"), "")
        self.assertEqual(xml_to_text(""), "")


class TestPdfToText(unittest.TestCase):
    """Tests for pdf_to_text."""

    def test_non_pdf_bytes_return_empty(self):
        """Bytes without a %PDF header are rejected."""
        self.assertEqual(pdf_to_text(b"plain text bytes, not a pdf"), "")
        self.assertEqual(pdf_to_text(b""), "")

    def test_pdf_without_text_stream_returns_empty(self):
        """A PDF whose stream has no show-text operators yields ''."""
        pdf = (
            b"%PDF-1.4\n1 0 obj\n<< /Length 13 >>\nstream\nno operators\nendstream\n"
            b"endobj\ntrailer\n%%EOF\n"
        )
        self.assertEqual(pdf_to_text(pdf), "")

    def test_extracts_literal_string_from_minimal_pdf(self):
        """A minimal uncompressed BT/Tj block yields its padded literal string."""
        pdf = (
            b"%PDF-1.4\n1 0 obj\n<< /Length 0 >>\nstream\nBT ("
            + PDF_LITERAL.encode("ascii")
            + b") Tj ET\nendstream\nendobj\ntrailer\n%%EOF\n"
        )
        text = pdf_to_text(pdf)
        self.assertIn("Hello consolidation", text)
        self.assertGreaterEqual(len(text), 50)


class TestFindOALocations(unittest.TestCase):
    """Tests for find_oa_locations."""

    def test_europe_pmc_location_when_pmcid_set(self):
        """A record with a pmcid gets the Europe PMC fullTextXML location."""
        record = make_record(pmcid="PMC123", crossref_data={})
        locations = find_oa_locations(record)
        self.assertGreaterEqual(len(locations), 1)
        first = locations[0]
        self.assertEqual(first.url, EUROPE_PMC_FULLTEXT.format(pmcid="PMC123"))
        self.assertEqual(first.kind, "xml")
        self.assertEqual(first.source, "europe_pmc")

    def test_unpaywall_best_oa_url_included(self):
        """Unpaywall best_oa_url from crossref_data becomes an OA location."""
        record = make_record(
            pmcid="PMC123",
            crossref_data={
                "unpaywall": {"best_oa_url": OA_URL, "best_oa_license": "cc-by"}
            },
        )
        locations = find_oa_locations(record)
        urls = [loc.url for loc in locations]
        self.assertIn(OA_URL, urls)
        best = next(loc for loc in locations if loc.url == OA_URL)
        self.assertEqual(best.source, "unpaywall")
        self.assertEqual(best.license, "cc-by")
        self.assertEqual(best.kind, "html")

    def test_no_location_without_pmcid_or_unpaywall(self):
        """A record with no OA metadata yields no locations."""
        self.assertEqual(find_oa_locations(no_oa_record()), [])


class TestFullTextFetcher(unittest.TestCase):
    """Tests for FullTextFetcher.fetch, caching and force."""

    def test_fetch_html_location(self):
        """HTML OA page served by FakeClient yields an ok FullTextDoc."""
        client = FakeClient({OA_URL: SLOPE_HTML.encode("utf-8")})
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = FullTextFetcher(Path(tmp) / "cache", client=client)
            doc = fetcher.fetch(oa_record())
        self.assertIsNotNone(doc)
        self.assertTrue(doc.ok)
        self.assertEqual(doc.record_id, "rec1")
        self.assertEqual(doc.url, OA_URL)
        self.assertEqual(doc.kind, "html")
        self.assertEqual(doc.source, "unpaywall")
        self.assertGreater(doc.chars, 0)
        self.assertGreaterEqual(len(doc.text), 200)
        self.assertIn("Slope stability analysis", doc.text)
        self.assertEqual(client.calls, [OA_URL])

    def test_second_fetch_hits_cache(self):
        """The same URL is fetched from the network only once."""
        client = FakeClient({OA_URL: SLOPE_HTML.encode("utf-8")})
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = FullTextFetcher(Path(tmp) / "cache", client=client)
            first = fetcher.fetch(oa_record())
            second = fetcher.fetch(oa_record())
            self.assertEqual(len(client.calls), 1)
            self.assertTrue(first.ok)
            self.assertTrue(second.ok)
            self.assertEqual(second.text, first.text)
            self.assertIn("cache", second.fetched_at)

    def test_force_refetches(self):
        """force=True bypasses the cache and fetches again."""
        client = FakeClient({OA_URL: SLOPE_HTML.encode("utf-8")})
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            fetcher = FullTextFetcher(cache_dir, client=client)
            first = fetcher.fetch(oa_record())
            self.assertTrue(first.ok)
            self.assertEqual(len(client.calls), 1)
            forced = FullTextFetcher(cache_dir, client=client, force=True)
            third = forced.fetch(oa_record())
            self.assertEqual(len(client.calls), 2)
            self.assertTrue(third.ok)
            self.assertNotIn("cache", third.fetched_at)

    def test_record_without_oa_location_never_hits_network(self):
        """No OA location returns None before any client call."""
        client = FakeClient({})
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = FullTextFetcher(Path(tmp) / "cache", client=client)
            doc = fetcher.fetch(no_oa_record())
        self.assertIsNone(doc)
        self.assertEqual(client.calls, [])


class TestFetchFullTexts(unittest.TestCase):
    """Tests for fetch_full_texts output files and load_full_text."""

    def test_writes_index_and_texts(self):
        """Index JSON, text files and per-record results are written."""
        client = FakeClient({OA_URL: SLOPE_HTML.encode("utf-8")})
        records = [oa_record(), no_oa_record()]
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "fulltext"
            index, results = fetch_full_texts(records, out_dir, client=client)

            index_path = out_dir / "fulltext_index.json"
            self.assertTrue(index_path.exists())
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["entries"], index)

            txt_files = sorted((out_dir / "texts").glob("*.txt"))
            self.assertEqual(len(txt_files), 1)
            self.assertEqual(index.get("rec1"), "texts/rec1.txt")
            self.assertIn("Slope stability analysis", txt_files[0].read_text(encoding="utf-8"))

            by_id = {res["record_id"]: res for res in results}
            self.assertTrue(by_id["rec1"]["ok"])
            self.assertEqual(by_id["n1"]["ok"], False)
            self.assertEqual(by_id["n1"]["error"], "no_oa_location")
            self.assertEqual(client.calls, [OA_URL])

    def test_load_full_text_reads_written_text(self):
        """load_full_text returns the text written by fetch_full_texts."""
        client = FakeClient({OA_URL: SLOPE_HTML.encode("utf-8")})
        records = [oa_record(), no_oa_record()]
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "fulltext"
            fetch_full_texts(records, out_dir, client=client)
            text = load_full_text("rec1", out_dir)
            self.assertIn("Slope stability analysis", text)
            self.assertIn("Soil consolidation settlement", text)
            self.assertEqual(load_full_text("n1", out_dir), "")
            self.assertEqual(load_full_text("missing", out_dir), "")


if __name__ == "__main__":
    unittest.main()
