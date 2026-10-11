# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for LITHOS adapters (offline, synthetic data only)."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io
import json
import tempfile
from pathlib import Path

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


class TestOpenAlexAdapter(unittest.TestCase):
    """Tests for OpenAlexAdapter."""

    def setUp(self):
        from lithos.adapters_openalex import OpenAlexAdapter
        from lithos.adapters import init_adapters
        init_adapters({})
        self.adapter = OpenAlexAdapter()

    def test_search_parses_payload(self):
        """Search should parse OPENALEX_PAYLOAD into 2 records with correct fields."""
        from lithos.models import SearchQuery

        query = SearchQuery(original="soil consolidation", boolean_query="soil consolidation")
        with fake_http(json_payload=OPENALEX_PAYLOAD):
            result = self.adapter.search(query, limit=10)

        self.assertEqual(len(result.records), 2)
        r0, r1 = result.records

        # First record has all fields
        self.assertEqual(r0.doi, "10.9999/aaa")
        self.assertEqual(r0.title, "Soil consolidation settlement of soft clay")
        self.assertEqual(r0.year, 2018)
        self.assertEqual(r0.authors, ["A. Alpha"])
        self.assertEqual(r0.venue, "Geotechnical Engineering Journal")
        self.assertEqual(r0.cited_by, 5)
        self.assertEqual(r0.publication_type, "journal-article")
        self.assertEqual(r0.source, "openalex")
        self.assertIn("settlement of clay", r0.abstract.lower())

        # Second record has None DOI and no primary_location
        self.assertIsNone(r1.doi)
        self.assertEqual(r1.title, "Slope stability analysis methods")
        self.assertEqual(r1.year, 2020)
        self.assertEqual(r1.authors, ["B. Beta"])
        self.assertIsNone(r1.venue)
        self.assertEqual(r1.cited_by, 2)

    def test_rebuild_abstract(self):
        """rebuild_abstract should reconstruct text from inverted index."""
        from lithos.adapters_openalex import rebuild_abstract

        inv = {"settlement": [0], "of": [1], "clay": [2]}
        abstract = rebuild_abstract(inv)
        self.assertEqual(abstract, "settlement of clay")

        self.assertEqual(rebuild_abstract(None), "")
        self.assertEqual(rebuild_abstract({}), "")

    def test_extract_venue(self):
        """extract_venue should get venue from primary_location."""
        from lithos.adapters_openalex import extract_venue

        loc = {"source": {"display_name": "Journal of Geotech"}}
        self.assertEqual(extract_venue(loc), "Journal of Geotech")

        self.assertIsNone(extract_venue(None))
        self.assertIsNone(extract_venue({}))
        self.assertIsNone(extract_venue({"source": {}}))

    def test_extract_authors(self):
        """extract_authors should pull display_name from authorships."""
        from lithos.adapters_openalex import extract_authors

        auths = [{"author": {"display_name": "A. Alpha"}}, {"author": {"display_name": "B. Beta"}}]
        self.assertEqual(extract_authors(auths), ["A. Alpha", "B. Beta"])

        # Missing author or display_name
        self.assertEqual(extract_authors([{"author": {}}]), [])
        self.assertEqual(extract_authors([]), [])

    def test_extract_publication_type(self):
        """extract_publication_type should map OpenAlex types."""
        from lithos.adapters_openalex import extract_publication_type

        self.assertEqual(extract_publication_type("journal-article"), "journal-article")
        self.assertEqual(extract_publication_type("preprint"), "preprint")
        self.assertEqual(extract_publication_type("conference"), "conference-paper")
        self.assertEqual(extract_publication_type("book"), "book")
        self.assertEqual(extract_publication_type("unknown"), "unknown")
        self.assertIsNone(extract_publication_type(None))

    def test_translate_query_identity(self):
        """translate_query should return boolean_query or original."""
        from lithos.models import SearchQuery

        q1 = SearchQuery(original="test", boolean_query="test boolean")
        self.assertEqual(self.adapter.translate_query(q1), "test boolean")

        q2 = SearchQuery(original="simple query")
        self.assertEqual(self.adapter.translate_query(q2), "simple query")

    def test_normalize_doi(self):
        """normalize_doi should strip doi.org prefix."""
        self.assertEqual(self.adapter.normalize_doi("https://doi.org/10.9999/aaa"), "10.9999/aaa")
        self.assertEqual(self.adapter.normalize_doi("doi:10.9999/aaa"), "10.9999/aaa")
        self.assertEqual(self.adapter.normalize_doi("10.9999/aaa"), "10.9999/aaa")
        self.assertIsNone(self.adapter.normalize_doi(None))
        self.assertIsNone(self.adapter.normalize_doi(""))


class TestCrossrefAdapter(unittest.TestCase):
    """Tests for CrossrefAdapter."""

    def setUp(self):
        from lithos.adapters_crossref import CrossrefAdapter
        from lithos.adapters import init_adapters
        init_adapters({})
        self.adapter = CrossrefAdapter()

    def test_search_parses_payload(self):
        """Search should parse CROSSREF_PAYLOAD into 1 record."""
        from lithos.models import SearchQuery

        query = SearchQuery(original="soil consolidation", boolean_query="soil consolidation")
        with fake_http(json_payload=CROSSREF_PAYLOAD):
            result = self.adapter.search(query, limit=10)

        self.assertEqual(len(result.records), 1)
        r = result.records[0]
        self.assertEqual(r.doi, "10.9999/aaa")
        self.assertEqual(r.title, "Soil consolidation settlement of soft clay")
        self.assertEqual(r.year, 2018)
        self.assertEqual(r.authors, ["A. Alpha"])
        self.assertEqual(r.venue, "Geotechnical Engineering Journal")
        self.assertEqual(r.publication_type, "journal-article")
        self.assertEqual(r.source, "crossref")

    def test_validate_doi_returns_ok(self):
        """validate_doi should return {'ok': True, 'data': ...} on success."""
        from testhelpers import CROSSREF_VALIDATE_PAYLOAD
        with fake_http(json_payload=CROSSREF_VALIDATE_PAYLOAD):
            result = self.adapter.validate_doi("10.9999/aaa")

        self.assertTrue(result["ok"])
        self.assertIn("data", result)
        self.assertEqual(result["data"].get("DOI"), "10.9999/aaa")

    def test_check_retraction_true(self):
        """check_retraction should return True when update-to lists retraction."""
        from lithos.adapters_crossref import CrossrefAdapter

        msg = {"update-to": [{"type": "retraction"}, {"type": "correction"}]}
        self.assertTrue(self.adapter.check_retraction(msg))

        msg2 = {"update-to": [{"type": "withdrawal"}]}
        self.assertTrue(self.adapter.check_retraction(msg2))

        msg3 = {"update-to": [{"type": "correction"}]}
        self.assertFalse(self.adapter.check_retraction(msg3))

        self.assertFalse(self.adapter.check_retraction({}))

    def test_check_correction(self):
        """check_correction should return True when update-to lists correction."""
        msg = {"update-to": [{"type": "correction"}]}
        self.assertTrue(self.adapter.check_correction(msg))

        msg2 = {"update-to": [{"type": "retraction"}]}
        self.assertFalse(self.adapter.check_correction(msg2))

    def test_get_preprint_relation(self):
        """get_preprint_relation should find published version DOI."""
        msg = {"relation": {"is-preprint-of": [{"id": "https://doi.org/10.9999/published"}]}}
        self.assertEqual(self.adapter.get_preprint_relation(msg), "10.9999/published")

        msg2 = {"relation": {"has-preprint": [{"id": "https://doi.org/10.9999/preprint"}]}}
        self.assertEqual(self.adapter.get_preprint_relation(msg2), "10.9999/preprint")

        self.assertIsNone(self.adapter.get_preprint_relation({}))

    def test_normalize_doi_strips_prefixes(self):
        """normalize_doi should strip https://doi.org/, http://doi.org/, and doi:."""
        self.assertEqual(self.adapter.normalize_doi("https://doi.org/10.9999/aaa"), "10.9999/aaa")
        self.assertEqual(self.adapter.normalize_doi("http://doi.org/10.9999/aaa"), "10.9999/aaa")
        self.assertEqual(self.adapter.normalize_doi("doi:10.9999/aaa"), "10.9999/aaa")
        self.assertEqual(self.adapter.normalize_doi("10.9999/aaa"), "10.9999/aaa")
        self.assertIsNone(self.adapter.normalize_doi(None))
        self.assertIsNone(self.adapter.normalize_doi(""))


class TestSemanticScholarAdapter(unittest.TestCase):
    """Tests for SemanticScholarAdapter."""

    def setUp(self):
        from lithos.adapters_semantic_scholar import SemanticScholarAdapter
        from lithos.adapters import init_adapters
        init_adapters({})
        self.adapter = SemanticScholarAdapter()

    def test_search_parses_payload(self):
        """Search should parse SEMANTICSCHOLAR_PAYLOAD."""
        from lithos.models import SearchQuery

        query = SearchQuery(original="pavement fatigue", boolean_query="pavement fatigue")
        with fake_http(json_payload=SEMANTICSCHOLAR_PAYLOAD):
            result = self.adapter.search(query, limit=10)

        self.assertEqual(len(result.records), 1)
        r = result.records[0]
        self.assertEqual(r.title, "Pavement fatigue cracking models")
        self.assertEqual(r.year, 2019)
        self.assertEqual(r.authors, ["C. Gamma"])
        self.assertEqual(r.venue, "Road Materials Journal")
        self.assertEqual(r.abstract, "Fatigue cracking of flexible pavements under traffic loading.")
        self.assertEqual(r.doi, "10.9999/ddd")
        self.assertEqual(r.publication_type, "JournalArticle")
        self.assertEqual(r.cited_by, 3)
        self.assertEqual(r.source, "semantic_scholar")


class TestArxivAdapter(unittest.TestCase):
    """Tests for ArxivAdapter."""

    def setUp(self):
        from lithos.adapters_arxiv import ArxivAdapter
        from lithos.adapters import init_adapters
        init_adapters({})
        self.adapter = ArxivAdapter()

    def test_search_parses_atom(self):
        """Search should parse ARXIV_ATOM into 1 preprint record."""
        from lithos.models import SearchQuery

        query = SearchQuery(original="bearing capacity", boolean_query="bearing capacity")
        with fake_http(text_payload=ARXIV_ATOM):
            result = self.adapter.search(query, limit=10)

        self.assertEqual(len(result.records), 1)
        r = result.records[0]
        self.assertEqual(r.title, "Bearing capacity of shallow foundations")
        self.assertEqual(r.year, 2020)
        self.assertEqual(r.authors, ["D. Delta"])
        self.assertEqual(r.abstract, "Bearing capacity of shallow foundations on sand.")
        self.assertEqual(r.arxiv_id, "2001.00001v1")
        self.assertEqual(r.publication_type, "preprint")
        self.assertEqual(r.source, "arxiv")


class TestEuropePMCAdapter(unittest.TestCase):
    """Tests for EuropePMCAdapter."""

    def setUp(self):
        from lithos.adapters_europe_pmc import EuropePMCAdapter
        from lithos.adapters import init_adapters
        init_adapters({})
        self.adapter = EuropePMCAdapter()

    def test_search_parses_payload(self):
        """Search should parse EUROPEPMC_PAYLOAD.

        The Record model has pmcid field, so parsing should succeed and return 1 record.
        """
        from lithos.models import SearchQuery

        query = SearchQuery(original="chloride concrete", boolean_query="chloride concrete")
        with fake_http(json_payload=EUROPEPMC_PAYLOAD):
            result = self.adapter.search(query, limit=10)

        # Should return 1 record with all fields parsed correctly
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.total_hits, 1)
        r = result.records[0]
        self.assertEqual(r.pmid, "12345678")
        self.assertEqual(r.pmcid, "PMC123456")
        self.assertEqual(r.doi, "10.9999/eee")
        self.assertEqual(r.title, "Chloride ingress in reinforced concrete")
        self.assertEqual(r.year, 2017)
        self.assertEqual(r.authors, ["E. Epsilon"])
        self.assertEqual(r.venue, "Concrete Durability")


class TestDOAJAdapter(unittest.TestCase):
    """Tests for DOAJAdapter."""

    def setUp(self):
        from lithos.adapters_doaj import DOAJAdapter
        from lithos.adapters import init_adapters
        init_adapters({})
        self.adapter = DOAJAdapter()

    def test_search_parses_payload(self):
        """Search should parse DOAJ_PAYLOAD."""
        from lithos.models import SearchQuery

        query = SearchQuery(original="machine learning image segmentation", boolean_query="machine learning image segmentation")
        with fake_http(json_payload=DOAJ_PAYLOAD):
            result = self.adapter.search(query, limit=10)

        self.assertEqual(len(result.records), 1)
        r = result.records[0]
        self.assertEqual(r.doi, "10.9999/fff")
        self.assertEqual(r.title, "Machine learning for image segmentation")
        # DOAJ adapter converts year to int
        self.assertEqual(r.year, 2021)
        self.assertEqual(r.authors, ["F. Zeta"])
        self.assertEqual(r.venue, "Applied Computing")
        self.assertEqual(r.abstract, "Segmentation of engineering imagery.")
        self.assertEqual(r.publication_type, "journal-article")
        self.assertEqual(r.source, "doaj")


class TestAdapterRegistry(unittest.TestCase):
    """Tests for adapter registry initialization."""

    def test_init_adapters_registry_names(self):
        """init_adapters({}) should register all 8 adapters."""
        from lithos.adapters import init_adapters, registry

        init_adapters({})
        names = registry.list_names()

        expected = {"openalex", "crossref", "semantic_scholar", "arxiv", "europe_pmc", "core", "doaj", "unpaywall"}
        self.assertEqual(set(names), expected)

    def test_get_enabled_adapters_excludes_core(self):
        """get_enabled_adapters should exclude 'core' (disabled by default)."""
        from lithos.adapters import init_adapters, get_enabled_adapters

        init_adapters({})
        enabled = get_enabled_adapters()
        enabled_names = [a.name for a in enabled]

        self.assertIn("openalex", enabled_names)
        self.assertIn("crossref", enabled_names)
        self.assertNotIn("core", enabled_names)
        self.assertEqual(len(enabled), 7)  # 8 total - 1 disabled core


if __name__ == "__main__":
    unittest.main()