# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.query module."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from lithos.query import (
    SynonymGroup,
    SynonymExpander,
    QueryBuilder,
    SearchProfile,
    SearchLogger,
)
from lithos.models import SearchQuery, SearchResult, Record, RecordStatus


class TestSynonymGroup(unittest.TestCase):
    """Tests for SynonymGroup class."""

    def test_expand_canonical(self):
        """Expanding canonical term returns canonical + synonyms."""
        group = SynonymGroup(canonical="consolidation", synonyms=["compaction", "settlement"])
        expanded = group.expand("consolidation")
        self.assertEqual(expanded, ["consolidation", "compaction", "settlement"])

    def test_expand_synonym(self):
        """Expanding a synonym returns canonical + synonyms."""
        group = SynonymGroup(canonical="consolidation", synonyms=["compaction", "settlement"])
        expanded = group.expand("compaction")
        self.assertEqual(expanded, ["consolidation", "compaction", "settlement"])

    def test_expand_unknown(self):
        """Expanding unknown term returns the term itself."""
        group = SynonymGroup(canonical="consolidation", synonyms=["compaction"])
        expanded = group.expand("unknown")
        self.assertEqual(expanded, ["unknown"])

    def test_case_insensitive(self):
        """Expansion is case-insensitive."""
        group = SynonymGroup(canonical="Consolidation", synonyms=["Compaction"])
        expanded = group.expand("COMPACTION")
        self.assertEqual(expanded, ["Consolidation", "Compaction"])


class TestSynonymExpander(unittest.TestCase):
    """Tests for SynonymExpander class."""

    def setUp(self):
        self.expander = SynonymExpander([
            SynonymGroup(canonical="consolidation", synonyms=["compaction", "settlement"]),
            SynonymGroup(canonical="slope stability", synonyms=["landslide", "slope failure"]),
        ])

    def test_expand_term_known(self):
        """expand_term returns expanded list for known term."""
        result = self.expander.expand_term("compaction")
        self.assertEqual(result, ["consolidation", "compaction", "settlement"])

    def test_expand_term_unknown(self):
        """expand_term returns original term for unknown term."""
        result = self.expander.expand_term("unknown")
        self.assertEqual(result, ["unknown"])

    def test_expand_query_single_term(self):
        """expand_query expands single term."""
        result = self.expander.expand_query("compaction")
        self.assertIn("consolidation", result)
        self.assertIn("compaction", result)
        self.assertIn("settlement", result)

    def test_expand_query_with_and(self):
        """expand_query preserves boolean operators."""
        result = self.expander.expand_query("compaction AND clay")
        self.assertIn("AND", result)
        self.assertIn("consolidation", result)

    def test_expand_query_quoted_phrase_not_expanded(self):
        """expand_query does not expand terms inside quoted phrases."""
        result = self.expander.expand_query('"compaction test" clay')
        # The quoted phrase should remain unchanged
        self.assertIn('"compaction test"', result)
        # But clay should be processed (not expanded since not in synonyms)
        self.assertIn("clay", result)

    def test_expand_query_multiple_groups(self):
        """expand_query handles multiple synonym groups."""
        result = self.expander.expand_query("compaction landslide")
        self.assertIn("consolidation", result)
        self.assertIn("slope stability", result)

    def test_load_from_file(self):
        """load_from_file loads synonym groups from JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "synonyms.json"
            path.write_text('[{"canonical": "test", "synonyms": ["exam", "trial"]}]')
            expander = SynonymExpander()
            expander.load_from_file(path)
            result = expander.expand_term("exam")
            self.assertEqual(result, ["test", "exam", "trial"])


class TestQueryBuilder(unittest.TestCase):
    """Tests for QueryBuilder class."""

    def test_add_term(self):
        """add_term adds a simple term."""
        builder = QueryBuilder()
        builder.add_term("consolidation")
        self.assertEqual(builder.build(), "consolidation")

    def test_add_term_with_field(self):
        """add_term with field prefix."""
        builder = QueryBuilder()
        builder.add_term("consolidation", field="title")
        self.assertEqual(builder.build(), "title:consolidation")

    def test_add_term_with_operator(self):
        """add_term respects boolean operator."""
        builder = QueryBuilder()
        builder.add_term("consolidation")
        builder.add_term("clay", operator="OR")
        self.assertEqual(builder.build(), "consolidation OR clay")

    def test_add_phrase(self):
        """add_phrase adds quoted phrase."""
        builder = QueryBuilder()
        builder.add_phrase("soil consolidation")
        self.assertEqual(builder.build(), '"soil consolidation"')

    def test_add_phrase_with_field(self):
        """add_phrase with field prefix."""
        builder = QueryBuilder()
        builder.add_phrase("soil consolidation", field="title")
        self.assertEqual(builder.build(), 'title:"soil consolidation"')

    def test_add_year_range_both(self):
        """add_year_range with from and to years."""
        builder = QueryBuilder()
        builder.add_year_range(2010, 2020)
        self.assertEqual(builder.build(), "year:[2010 TO 2020]")

    def test_add_year_range_from_only(self):
        """add_year_range with from year only."""
        builder = QueryBuilder()
        builder.add_year_range(from_year=2015)
        self.assertEqual(builder.build(), "year:[2015 TO *]")

    def test_add_year_range_to_only(self):
        """add_year_range with to year only."""
        builder = QueryBuilder()
        builder.add_year_range(to_year=2018)
        self.assertEqual(builder.build(), "year:[* TO 2018]")

    def test_add_type_filter(self):
        """add_type_filter adds publication type filter."""
        builder = QueryBuilder()
        builder.add_type_filter("journal-article")
        self.assertEqual(builder.build(), "type:journal-article")

    def test_build_empty(self):
        """build returns empty string for no terms."""
        builder = QueryBuilder()
        self.assertEqual(builder.build(), "")

    def test_to_search_query(self):
        """to_search_query creates SearchQuery object."""
        builder = QueryBuilder()
        builder.add_term("consolidation")
        sq = builder.to_search_query("original query")
        self.assertIsInstance(sq, SearchQuery)
        self.assertEqual(sq.original, "original query")
        self.assertEqual(sq.boolean_query, "consolidation")


class TestSearchProfile(unittest.TestCase):
    """Tests for SearchProfile save/load round-trip."""

    def test_save_load_roundtrip(self):
        """SearchProfile saves and loads correctly."""
        profile = SearchProfile(
            name="test_profile",
            description="Test description",
            queries=[
                SearchQuery(original="query 1", boolean_query="query 1"),
                SearchQuery(original="query 2", boolean_query="query 2"),
            ],
            sources=["openalex", "crossref"],
            filters={"from_year": 2000},
            deduplicate=True,
            validate=False,
            screen=True,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "profile.json"
            profile.save(path)
            loaded = SearchProfile.load(path)

        self.assertEqual(loaded.name, "test_profile")
        self.assertEqual(loaded.description, "Test description")
        self.assertEqual(len(loaded.queries), 2)
        self.assertEqual(loaded.queries[0].original, "query 1")
        self.assertEqual(loaded.sources, ["openalex", "crossref"])
        self.assertEqual(loaded.filters, {"from_year": 2000})
        self.assertTrue(loaded.deduplicate)
        self.assertFalse(loaded.validate)
        self.assertTrue(loaded.screen)

    def test_save_load_empty_queries(self):
        """SearchProfile with empty queries round-trips."""
        profile = SearchProfile(name="empty", queries=[])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "profile.json"
            profile.save(path)
            loaded = SearchProfile.load(path)
        self.assertEqual(loaded.queries, [])

    def test_to_dict_includes_all_fields(self):
        """to_dict includes all profile fields."""
        profile = SearchProfile(name="test", queries=[SearchQuery(original="q")])
        d = profile.to_dict()
        self.assertIn("name", d)
        self.assertIn("description", d)
        self.assertIn("queries", d)
        self.assertIn("sources", d)
        self.assertIn("filters", d)
        self.assertIn("deduplicate", d)
        self.assertIn("validate", d)
        self.assertIn("screen", d)
        self.assertIn("created_at", d)
        self.assertIn("updated_at", d)


class TestSearchLogger(unittest.TestCase):
    """Tests for SearchLogger class."""

    def setUp(self):
        self.logger = SearchLogger()

    def test_log_search_basic(self):
        """log_search records an entry."""
        query = SearchQuery(original="test", boolean_query="test")
        result = MagicMock(spec=SearchResult)
        result.total_hits = 10
        result.records = [MagicMock(spec=Record) for _ in range(5)]
        result.duration_seconds = 1.5
        result.errors = []

        self.logger.log_search("openalex", query, result)
        self.assertEqual(len(self.logger.entries), 1)
        entry = self.logger.entries[0]
        self.assertEqual(entry["source"], "openalex")
        self.assertEqual(entry["total_hits"], 10)
        self.assertEqual(entry["records_retrieved"], 5)

    def test_log_search_with_errors(self):
        """log_search records errors."""
        query = SearchQuery(original="test", boolean_query="test")
        result = MagicMock(spec=SearchResult)
        result.total_hits = 0
        result.records = []
        result.duration_seconds = 0.5
        result.errors = ["timeout", "rate limit"]

        self.logger.log_search("crossref", query, result)
        entry = self.logger.entries[0]
        self.assertEqual(entry["errors"], ["timeout", "rate limit"])

    def test_log_deduplication(self):
        """log_deduplication records deduplication step."""
        self.logger.log_deduplication(before=100, after=80, method="doi+title", clusters=15)
        self.assertEqual(len(self.logger.entries), 1)
        entry = self.logger.entries[0]
        self.assertEqual(entry["step"], "deduplication")
        self.assertEqual(entry["records_before"], 100)
        self.assertEqual(entry["records_after"], 80)
        self.assertEqual(entry["duplicates_removed"], 20)
        self.assertEqual(entry["clusters"], 15)

    def test_log_validation(self):
        """log_validation records validation step."""
        self.logger.log_validation(validated=50, warnings=5, errors=2, retractions=1)
        entry = self.logger.entries[0]
        self.assertEqual(entry["step"], "validation")
        self.assertEqual(entry["validated"], 50)
        self.assertEqual(entry["with_warnings"], 5)
        self.assertEqual(entry["errors"], 2)
        self.assertEqual(entry["retracted"], 1)

    def test_log_screening(self):
        """log_screening records screening step."""
        self.logger.log_screening(included=30, excluded=20, conflicts=3, unscreened=10)
        entry = self.logger.entries[0]
        self.assertEqual(entry["step"], "screening")
        self.assertEqual(entry["included"], 30)
        self.assertEqual(entry["excluded"], 20)
        self.assertEqual(entry["conflicts"], 3)
        self.assertEqual(entry["unscreened"], 10)

    def test_export_prisma_s_writes_markdown_table(self):
        """export_prisma_s writes a markdown table with search entries."""
        query = SearchQuery(original="test", boolean_query="test query")
        result = MagicMock(spec=SearchResult)
        result.total_hits = 100
        result.records = [MagicMock(spec=Record) for _ in range(50)]
        result.duration_seconds = 2.3
        result.errors = ["warning"]

        self.logger.log_search("openalex", query, result)
        self.logger.log_deduplication(50, 40, "doi", 8)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prisma.md"
            self.logger.export_prisma_s(path)
            content = path.read_text()

        # Check markdown table structure
        self.assertIn("# PRISMA-S Search Log", content)
        self.assertIn("| Timestamp | Source | Query | Hits | Retrieved | Duration (s) | Errors |", content)
        self.assertIn("|---|---|---|---|---|---|---|", content)
        self.assertIn("openalex", content)
        self.assertIn("test query", content)
        self.assertIn("100", content)
        self.assertIn("50", content)
        # Check processing steps section
        self.assertIn("## Processing Steps", content)
        self.assertIn("Deduplication", content)
        self.assertIn("doi", content)
        self.assertIn("50 → 40", content)

    def test_export_json(self):
        """export_json writes valid JSON."""
        self.logger.log_search("openalex", SearchQuery(original="q"), MagicMock(
            spec=SearchResult, total_hits=1, records=[], duration_seconds=0.1, errors=[]))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "log.json"
            self.logger.export_json(path)
            import json
            data = json.loads(path.read_text())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["source"], "openalex")


if __name__ == "__main__":
    unittest.main()