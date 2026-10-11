# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.screen module."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import json
import tempfile
from pathlib import Path
import unittest
from lithos.screen import (
    ScreeningRule,
    ScreeningRules,
    KeywordScorer,
    TFIDFRanker,
    ScreeningSession,
    ScreenState,
    ScreenDecision,
    first_author_surname,
)
from lithos.models import Record


class TestScreeningRule(unittest.TestCase):
    """Tests for ScreeningRule class."""

    def setUp(self):
        self.record = Record(
            title="Soil consolidation settlement of soft clay",
            abstract="This paper studies consolidation settlement of soft clay foundations.",
            keywords=["consolidation", "settlement", "clay"],
            venue="Geotechnical Journal",
            year=2018,
            authors=["Alpha, A."],
            source="openalex",
        )

    def test_matches_title(self):
        """Rule matches on title field."""
        rule = ScreeningRule(id="r1", type="include", field="title", pattern="consolidation")
        self.assertTrue(rule.matches(self.record))

    def test_matches_abstract(self):
        """Rule matches on abstract field."""
        rule = ScreeningRule(id="r1", type="include", field="abstract", pattern="foundations")
        self.assertTrue(rule.matches(self.record))

    def test_matches_keywords(self):
        """Rule matches on keywords field."""
        rule = ScreeningRule(id="r1", type="include", field="keywords", pattern="clay")
        self.assertTrue(rule.matches(self.record))

    def test_matches_venue(self):
        """Rule matches on venue field."""
        rule = ScreeningRule(id="r1", type="include", field="venue", pattern="Geotechnical")
        self.assertTrue(rule.matches(self.record))

    def test_matches_year(self):
        """Rule matches on year field."""
        rule = ScreeningRule(id="r1", type="include", field="year", pattern="2018")
        self.assertTrue(rule.matches(self.record))

    def test_matches_any_field(self):
        """Rule matches on any field."""
        rule = ScreeningRule(id="r1", type="include", field="any", pattern="consolidation")
        self.assertTrue(rule.matches(self.record))

    def test_no_match(self):
        """Rule returns False when pattern not found."""
        rule = ScreeningRule(id="r1", type="include", field="title", pattern="slope")
        self.assertFalse(rule.matches(self.record))

    def test_case_insensitive_by_default(self):
        """Matching is case-insensitive by default."""
        rule = ScreeningRule(id="r1", type="include", field="title", pattern="CONSOLIDATION")
        self.assertTrue(rule.matches(self.record))

    def test_case_sensitive_option(self):
        """Case-sensitive matching when enabled."""
        rule = ScreeningRule(id="r1", type="include", field="title", pattern="CONSOLIDATION", case_sensitive=True)
        self.assertFalse(rule.matches(self.record))
        rule2 = ScreeningRule(id="r2", type="include", field="title", pattern="Soil", case_sensitive=True)
        self.assertTrue(rule2.matches(self.record))

    def test_regex_matching(self):
        """Regex pattern matching works."""
        rule = ScreeningRule(id="r1", type="include", field="title", pattern="consolidation|settlement", is_regex=True)
        self.assertTrue(rule.matches(self.record))

    def test_regex_case_insensitive(self):
        """Regex respects case_insensitive flag."""
        rule = ScreeningRule(id="r1", type="include", field="title", pattern="CONSOLIDATION", is_regex=True)
        self.assertTrue(rule.matches(self.record))
        rule2 = ScreeningRule(id="r2", type="include", field="title", pattern="CONSOLIDATION", is_regex=True, case_sensitive=True)
        self.assertFalse(rule2.matches(self.record))

    def test_empty_field_no_match(self):
        """Empty field returns no match."""
        record = Record(title="", abstract="", keywords=[], venue=None, year=None, source="test")
        rule = ScreeningRule(id="r1", type="include", field="title", pattern="test")
        self.assertFalse(rule.matches(record))

    def test_include_type(self):
        """Rule type include."""
        rule = ScreeningRule(id="r1", type="include", field="title", pattern="test")
        self.assertEqual(rule.type, "include")

    def test_exclude_type(self):
        """Rule type exclude."""
        rule = ScreeningRule(id="r1", type="exclude", field="title", pattern="test")
        self.assertEqual(rule.type, "exclude")


class TestScreeningRules(unittest.TestCase):
    """Tests for ScreeningRules collection."""

    def setUp(self):
        self.rules = ScreeningRules()
        self.record = Record(
            title="Soil consolidation settlement",
            abstract="Consolidation study",
            keywords=["consolidation"],
            venue="Journal",
            year=2018,
            source="test",
        )

    def test_add_include_rule(self):
        """add_include adds include rule."""
        rule = self.rules.add_include("title", "consolidation")
        self.assertEqual(rule.type, "include")
        self.assertEqual(rule.field, "title")
        self.assertEqual(rule.pattern, "consolidation")
        self.assertEqual(len(self.rules.rules), 1)

    def test_add_exclude_rule(self):
        """add_exclude adds exclude rule."""
        rule = self.rules.add_exclude("abstract", "slope")
        self.assertEqual(rule.type, "exclude")
        self.assertEqual(len(self.rules.rules), 1)

    def test_evaluate_exclude_precedence(self):
        """Exclude rules take precedence over include."""
        self.rules.add_include("title", "consolidation")
        self.rules.add_exclude("abstract", "study")
        state, hits = self.rules.evaluate(self.record)
        self.assertEqual(state, ScreenState.EXCLUDE)
        self.assertIn("exc_1", hits)

    def test_evaluate_include_only(self):
        """Include rule matches when no exclude."""
        self.rules.add_include("title", "consolidation")
        state, hits = self.rules.evaluate(self.record)
        self.assertEqual(state, ScreenState.INCLUDE)
        self.assertIn("inc_0", hits)

    def test_evaluate_no_match(self):
        """No matching rules returns UNSCREENED."""
        self.rules.add_include("title", "slope")
        state, hits = self.rules.evaluate(self.record)
        self.assertEqual(state, ScreenState.UNSCREENED)
        self.assertEqual(hits, [])

    def test_evaluate_multiple_excludes(self):
        """Multiple exclude rules all recorded."""
        self.rules.add_exclude("title", "consolidation")
        self.rules.add_exclude("abstract", "study")
        state, hits = self.rules.evaluate(self.record)
        self.assertEqual(state, ScreenState.EXCLUDE)
        self.assertEqual(len(hits), 2)

    def test_save_load_roundtrip(self):
        """Rules save and load correctly."""
        self.rules.add_include("title", "consolidation", is_regex=True, case_sensitive=False, description="Test")
        self.rules.add_exclude("abstract", "slope")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rules.json"
            self.rules.save(path)
            loaded = ScreeningRules.load(path)
        self.assertEqual(len(loaded.rules), 2)
        self.assertEqual(loaded.rules[0].pattern, "consolidation")
        self.assertTrue(loaded.rules[0].is_regex)
        self.assertEqual(loaded.rules[1].type, "exclude")


class TestKeywordScorer(unittest.TestCase):
    """Tests for KeywordScorer class."""

    def setUp(self):
        self.scorer = KeywordScorer(
            include_keywords={"consolidation": 2.0, "clay": 1.0},
            exclude_keywords={"slope": 1.5, "rock": 1.0},
        )
        self.record = Record(
            title="Soil consolidation settlement of soft clay",
            abstract="Consolidation of clay soils.",
            keywords=["consolidation", "clay", "settlement"],
            source="test",
        )

    def test_score_positive_for_include_keywords(self):
        """Score increases for include keywords."""
        score = self.scorer.score(self.record)
        self.assertGreater(score, 0)

    def test_score_negative_for_exclude_keywords(self):
        """Score decreases for exclude keywords."""
        record = Record(title="Slope stability in rock", abstract="Rock slope analysis", keywords=["slope", "rock"], source="test")
        score = self.scorer.score(record)
        self.assertLess(score, 0)

    def test_score_zero_for_no_keywords(self):
        """Score is zero when no keywords match."""
        record = Record(title="Unrelated topic", abstract="Nothing here", keywords=["other"], source="test")
        score = self.scorer.score(record)
        self.assertEqual(score, 0.0)

    def test_case_insensitive(self):
        """Scoring is case-insensitive."""
        record = Record(title="CONSOLIDATION study", abstract="", keywords=[], source="test")
        score = self.scorer.score(record)
        self.assertEqual(score, 2.0)

    def test_multiple_occurrences_count_once(self):
        """Each keyword counts once per record."""
        record = Record(title="consolidation consolidation", abstract="consolidation", keywords=["consolidation"], source="test")
        score = self.scorer.score(record)
        self.assertEqual(score, 2.0)  # Only counted once


class TestTFIDFRanker(unittest.TestCase):
    """Tests for TFIDFRanker class."""

    def setUp(self):
        self.records = [
            Record(title="Soil consolidation settlement", abstract="Consolidation of clay soils under loading", keywords=["consolidation", "clay"], year=2018, source="a"),
            Record(title="Slope stability analysis", abstract="Stability of slopes using limit equilibrium", keywords=["slope", "stability"], year=2019, source="b"),
            Record(title="Bearing capacity of shallow foundations", abstract="Foundation bearing capacity on sand", keywords=["foundation", "bearing", "capacity"], year=2020, source="c"),
        ]
        self.ranker = TFIDFRanker()

    def test_fit_creates_model(self):
        """fit builds document frequencies and avgdl."""
        self.ranker.fit(self.records)
        self.assertTrue(self.ranker._fitted)
        self.assertGreater(len(self.ranker.doc_freqs), 0)
        self.assertGreater(self.ranker.avgdl, 0)
        self.assertEqual(len(self.ranker.doc_lengths), 3)

    def test_score_before_fit_returns_zero(self):
        """score returns 0 before fit."""
        score = self.ranker.score("consolidation", self.records[0])
        self.assertEqual(score, 0.0)

    def test_score_after_fit(self):
        """score returns positive for relevant query."""
        self.ranker.fit(self.records)
        score = self.ranker.score("consolidation clay", self.records[0])
        self.assertGreater(score, 0)

    def test_score_irrelevant_query(self):
        """score returns low for irrelevant query."""
        self.ranker.fit(self.records)
        score = self.ranker.score("unrelated topic", self.records[0])
        self.assertEqual(score, 0.0)

    def test_rank_returns_sorted(self):
        """rank returns records sorted by score descending."""
        self.ranker.fit(self.records)
        ranked = self.ranker.rank("consolidation clay", self.records)
        self.assertEqual(len(ranked), 3)
        self.assertGreaterEqual(ranked[0][1], ranked[1][1])
        self.assertGreaterEqual(ranked[1][1], ranked[2][1])
        # First record should be most relevant
        self.assertEqual(ranked[0][0].title, "Soil consolidation settlement")

    def test_rank_empty_query_returns_zeros(self):
        """Empty query returns zero scores."""
        self.ranker.fit(self.records)
        ranked = self.ranker.rank("", self.records)
        self.assertEqual(len(ranked), 3)
        for _, score in ranked:
            self.assertEqual(score, 0.0)

    def test_rank_query_not_in_corpus(self):
        """Query terms not in corpus return zero scores."""
        self.ranker.fit(self.records)
        ranked = self.ranker.rank("completely unknown terms", self.records)
        for _, score in ranked:
            self.assertEqual(score, 0.0)


class TestScreeningSession(unittest.TestCase):
    """Tests for ScreeningSession class."""

    def setUp(self):
        self.records = [
            Record(id="1", title="Soil consolidation", year=2018, authors=["Alpha, A."], source="a"),
            Record(id="2", title="Slope stability", year=2019, authors=["Beta, B."], source="b"),
            Record(id="3", title="Bearing capacity", year=2020, authors=["Gamma, G."], source="c"),
        ]
        self.session = ScreeningSession(records=self.records, reviewers=["Reviewer1", "Reviewer2"])

    def test_add_reviewer(self):
        """add_reviewer adds reviewer to list."""
        self.session.add_reviewer("Reviewer3")
        self.assertIn("Reviewer3", self.session.reviewers)

    def test_record_decision(self):
        """record_decision stores decision."""
        self.session.record_decision("1", "Reviewer1", ScreenState.INCLUDE, "Relevant")
        decisions = self.session.decisions["1"]
        self.assertEqual(decisions["Reviewer1"].decision, ScreenState.INCLUDE)
        self.assertEqual(decisions["Reviewer1"].notes, "Relevant")

    def test_get_consensus_agree(self):
        """Consensus returns agreed state."""
        self.session.record_decision("1", "Reviewer1", ScreenState.INCLUDE)
        self.session.record_decision("1", "Reviewer2", ScreenState.INCLUDE)
        state, conflict = self.session.get_consensus("1")
        self.assertEqual(state, ScreenState.INCLUDE)
        self.assertFalse(conflict)

    def test_get_consensus_conflict(self):
        """Consensus returns CONFLICT when reviewers disagree."""
        self.session.record_decision("1", "Reviewer1", ScreenState.INCLUDE)
        self.session.record_decision("1", "Reviewer2", ScreenState.EXCLUDE)
        state, conflict = self.session.get_consensus("1")
        self.assertEqual(state, ScreenState.CONFLICT)
        self.assertTrue(conflict)

    def test_get_consensus_unscreened(self):
        """Consensus returns UNSCREENED for no decisions."""
        state, conflict = self.session.get_consensus("1")
        self.assertEqual(state, ScreenState.UNSCREENED)
        self.assertFalse(conflict)

    def test_apply_rules_sets_states(self):
        """apply_rules sets screen_state on records."""
        self.session.rules = ScreeningRules()
        self.session.rules.add_include("title", "consolidation")
        self.session.rules.add_exclude("title", "slope")
        self.session.apply_rules()
        self.assertEqual(self.records[0].screen_state, ScreenState.INCLUDE)
        self.assertEqual(self.records[1].screen_state, ScreenState.EXCLUDE)
        self.assertEqual(self.records[2].screen_state, ScreenState.UNSCREENED)

    def test_apply_keyword_scoring(self):
        """apply_keyword_scoring sets states based on threshold."""
        self.session.keyword_scorer = KeywordScorer(
            include_keywords={"consolidation": 2.0},
            exclude_keywords={"slope": 2.0},
        )
        self.session.apply_keyword_scoring(threshold=1.0)
        self.assertEqual(self.records[0].screen_state, ScreenState.INCLUDE)
        self.assertEqual(self.records[1].screen_state, ScreenState.EXCLUDE)
        self.assertEqual(self.records[2].screen_state, ScreenState.UNSCREENED)

    def test_apply_tfidf_ranking(self):
        """apply_tfidf_ranking auto-includes top K."""
        self.session.tfidf_ranker = TFIDFRanker()
        self.session.apply_tfidf_ranking("consolidation", top_k=1)
        self.assertEqual(self.records[0].screen_state, ScreenState.INCLUDE)
        self.assertIn("TF-IDF rank: 1", self.records[0].screen_notes)

    def test_export_two_reviewer_writes_file(self):
        """export_two_reviewer writes markdown table file."""
        self.session.record_decision("1", "Reviewer1", ScreenState.INCLUDE, "Good")
        self.session.record_decision("1", "Reviewer2", ScreenState.INCLUDE, "Agree")
        self.session.record_decision("2", "Reviewer1", ScreenState.EXCLUDE, "Irrelevant")
        self.session.record_decision("2", "Reviewer2", ScreenState.INCLUDE, "Maybe")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "screening.md"
            self.session.export_two_reviewer(path)
            content = path.read_text()
        self.assertIn("| Include? (Y/N) | ID | DOI | Year | First Author | Title | Venue | Reviewer 1 | Reviewer 2 | Agreement | Notes |", content)
        self.assertIn("Soil consolidation", content)
        self.assertIn("Slope stability", content)
        self.assertIn("Alpha", content)
        self.assertIn("Beta", content)
        self.assertIn("Y", content)  # Agreement for record 1
        self.assertIn("N", content)  # Disagreement for record 2

    def test_export_two_reviewer_warns_wrong_count(self):
        """export_two_reviewer warns if not exactly 2 reviewers."""
        session = ScreeningSession(records=self.records, reviewers=["OnlyOne"])
        # Add some decisions so reviewer names appear
        session.record_decision("1", "OnlyOne", ScreenState.INCLUDE, "Good")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "screening.md"
            # Should not raise, just warn
            session.export_two_reviewer(path)
            content = path.read_text()
        self.assertIn("R1: Good", content)
        self.assertIn("Reviewer 2", content)  # default second reviewer (with space)

    def test_export_decisions_json(self):
        """export_decisions writes JSON."""
        self.session.record_decision("1", "Reviewer1", ScreenState.INCLUDE, "Notes")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.json"
            self.session.export_decisions(path)
            data = json.loads(path.read_text())
        self.assertEqual(data["reviewers"], ["Reviewer1", "Reviewer2"])
        self.assertEqual(data["decisions"]["1"]["Reviewer1"]["decision"], "INCLUDE")
        self.assertEqual(data["decisions"]["1"]["Reviewer1"]["notes"], "Notes")

    def test_load_decisions(self):
        """load_decisions reads JSON."""
        data = {"reviewers": ["R1"], "decisions": {"1": {"R1": {"decision": "INCLUDE", "notes": "Note"}}}}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decisions.json"
            path.write_text(json.dumps(data))
            loaded = ScreeningSession.load_decisions(path)
        self.assertEqual(loaded, data)


class TestScreenStateEnum(unittest.TestCase):
    """Tests for ScreenState enum."""

    def test_values(self):
        """ScreenState has expected values."""
        self.assertEqual(ScreenState.UNSCREENED, "UNSCREENED")
        self.assertEqual(ScreenState.INCLUDE, "INCLUDE")
        self.assertEqual(ScreenState.EXCLUDE, "EXCLUDE")
        self.assertEqual(ScreenState.CONFLICT, "CONFLICT")

    def test_screen_state_set_on_record(self):
        """Record screen_state can be set to enum values."""
        rec = Record(title="Test", source="test")
        rec.screen_state = ScreenState.INCLUDE
        self.assertEqual(rec.screen_state, ScreenState.INCLUDE)
        rec.screen_state = ScreenState.EXCLUDE
        self.assertEqual(rec.screen_state, ScreenState.EXCLUDE)
        rec.screen_state = ScreenState.CONFLICT
        self.assertEqual(rec.screen_state, ScreenState.CONFLICT)


class TestFirstAuthorSurnameScreen(unittest.TestCase):
    """Tests for first_author_surname in screen module."""

    def test_comma_format(self):
        """Handles 'Surname, Given' format."""
        self.assertEqual(first_author_surname(["Alpha, A."]), "Alpha")

    def test_space_format(self):
        """Handles 'Given Surname' format."""
        self.assertEqual(first_author_surname(["A. Alpha"]), "Alpha")

    def test_empty_list(self):
        """Returns None for empty list."""
        self.assertIsNone(first_author_surname([]))

    def test_multiple_authors(self):
        """Returns first author only."""
        self.assertEqual(first_author_surname(["Alpha, A.", "Beta, B."]), "Alpha")


if __name__ == "__main__":
    unittest.main()