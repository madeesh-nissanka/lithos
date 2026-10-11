# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.presets module."""
from __future__ import annotations

from testhelpers import add_src_path
add_src_path()

import unittest
from lithos.presets import (
    ALL_PRESETS,
    CIVIL_PRESETS,
    GEOTECH_PRESETS,
    STRUCTURAL_PRESETS,
    ENVIRONMENTAL_PRESETS,
    SCIENCE_PRESETS,
    get_preset,
    list_presets,
    get_all_profiles,
)
from lithos.query import SearchProfile


class TestListPresets(unittest.TestCase):
    """Tests for list_presets function."""

    def test_returns_dict_of_domains(self):
        """list_presets returns dict mapping domain to preset names."""
        result = list_presets()
        self.assertIsInstance(result, dict)
        self.assertIn("civil", result)
        self.assertIn("geotechnical", result)
        self.assertIn("structural", result)
        self.assertIn("environmental", result)
        self.assertIn("science", result)

    def test_civil_presets_list(self):
        """Civil domain has expected presets."""
        result = list_presets()
        civil = result["civil"]
        self.assertIn("soil_consolidation", civil)
        self.assertIn("slope_stability", civil)
        self.assertIn("bearing_capacity", civil)
        self.assertIn("retaining_walls", civil)
        self.assertIn("ground_improvement", civil)

    def test_structural_presets_list(self):
        """Structural domain has expected presets."""
        result = list_presets()
        structural = result["structural"]
        self.assertIn("concrete_durability", structural)
        self.assertIn("reinforced_concrete", structural)
        self.assertIn("steel_structures", structural)
        self.assertIn("structural_dynamics", structural)
        self.assertIn("bridge_engineering", structural)

    def test_all_domains_non_empty(self):
        """All domains have at least one preset."""
        result = list_presets()
        for domain, presets in result.items():
            self.assertGreater(len(presets), 0, f"Domain {domain} has no presets")


class TestGetPreset(unittest.TestCase):
    """Tests for get_preset function."""

    def test_get_preset_civil_slope_stability(self):
        """get_preset returns SearchProfile for civil/slope_stability."""
        profile = get_preset("civil", "slope_stability")
        self.assertIsNotNone(profile)
        self.assertIsInstance(profile, SearchProfile)
        self.assertEqual(profile.name, "slope_stability")
        self.assertEqual(profile.description, "Slope stability analysis and landslide risk")

    def test_get_preset_civil_slope_stability_queries(self):
        """Preset has >= 2 queries."""
        profile = get_preset("civil", "slope_stability")
        self.assertGreaterEqual(len(profile.queries), 2)
        self.assertEqual(len(profile.queries), 4)

    def test_get_preset_civil_slope_stability_sources(self):
        """Preset has sources list."""
        profile = get_preset("civil", "slope_stability")
        self.assertIsInstance(profile.sources, list)
        self.assertGreater(len(profile.sources), 0)
        self.assertIn("openalex", profile.sources)
        self.assertIn("crossref", profile.sources)

    def test_get_preset_structural_concrete_durability(self):
        """get_preset returns SearchProfile for structural/concrete_durability."""
        profile = get_preset("structural", "concrete_durability")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "concrete_durability")
        self.assertGreaterEqual(len(profile.queries), 2)
        self.assertGreater(len(profile.sources), 0)

    def test_get_preset_unknown_domain_returns_none(self):
        """get_preset returns None for unknown domain."""
        profile = get_preset("unknown_domain", "any")
        self.assertIsNone(profile)

    def test_get_preset_unknown_name_returns_none(self):
        """get_preset returns None for unknown preset name."""
        profile = get_preset("civil", "unknown_preset")
        self.assertIsNone(profile)

    def test_get_preset_geotech_foundation_design(self):
        """get_preset works for geotechnical domain."""
        profile = get_preset("geotechnical", "foundation_design")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "foundation_design")
        self.assertGreaterEqual(len(profile.queries), 2)

    def test_get_preset_environmental_water_treatment(self):
        """get_preset works for environmental domain."""
        profile = get_preset("environmental", "water_treatment")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "water_treatment")
        self.assertGreaterEqual(len(profile.queries), 2)

    def test_get_preset_science_machine_learning(self):
        """get_preset works for science domain."""
        profile = get_preset("science", "machine_learning_science")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "machine_learning_science")
        self.assertGreaterEqual(len(profile.queries), 2)


class TestGetAllProfiles(unittest.TestCase):
    """Tests for get_all_profiles function."""

    def test_returns_non_empty_list(self):
        """get_all_profiles returns list with > 0 profiles."""
        profiles = get_all_profiles()
        self.assertIsInstance(profiles, list)
        self.assertGreater(len(profiles), 0)

    def test_all_are_search_profiles(self):
        """All returned items are SearchProfile instances."""
        profiles = get_all_profiles()
        for p in profiles:
            self.assertIsInstance(p, SearchProfile)

    def test_includes_all_domains(self):
        """Profiles include all domains."""
        profiles = get_all_profiles()
        names = {p.name for p in profiles}
        # Check at least one from each domain
        self.assertIn("slope_stability", names)  # civil
        self.assertIn("foundation_design", names)  # geotechnical
        self.assertIn("concrete_durability", names)  # structural
        self.assertIn("water_treatment", names)  # environmental
        self.assertIn("machine_learning_science", names)  # science

    def test_total_profile_count(self):
        """Total profile count matches sum of domain presets."""
        profiles = get_all_profiles()
        expected = sum(len(v) for v in ALL_PRESETS.values())
        self.assertEqual(len(profiles), expected)


class TestAllPresetsStructure(unittest.TestCase):
    """Tests for ALL_PRESETS structure."""

    def test_all_presets_keys(self):
        """ALL_PRESETS has expected domain keys."""
        self.assertEqual(set(ALL_PRESETS.keys()), {"civil", "geotechnical", "structural", "environmental", "science"})

    def test_civil_presets_content(self):
        """CIVIL_PRESETS contains expected keys."""
        self.assertIn("soil_consolidation", CIVIL_PRESETS)
        self.assertIn("slope_stability", CIVIL_PRESETS)
        self.assertIn("bearing_capacity", CIVIL_PRESETS)
        self.assertIn("retaining_walls", CIVIL_PRESETS)
        self.assertIn("ground_improvement", CIVIL_PRESETS)

    def test_structural_presets_content(self):
        """STRUCTURAL_PRESETS contains expected keys."""
        self.assertIn("concrete_durability", STRUCTURAL_PRESETS)
        self.assertIn("reinforced_concrete", STRUCTURAL_PRESETS)
        self.assertIn("steel_structures", STRUCTURAL_PRESETS)
        self.assertIn("structural_dynamics", STRUCTURAL_PRESETS)
        self.assertIn("bridge_engineering", STRUCTURAL_PRESETS)

    def test_geotech_presets_content(self):
        """GEOTECH_PRESETS contains expected keys."""
        self.assertIn("foundation_design", GEOTECH_PRESETS)
        self.assertIn("soil_structure_interaction", GEOTECH_PRESETS)
        self.assertIn("geotechnical_earthquake", GEOTECH_PRESETS)

    def test_environmental_presets_content(self):
        """ENVIRONMENTAL_PRESETS contains expected keys."""
        self.assertIn("water_treatment", ENVIRONMENTAL_PRESETS)
        self.assertIn("contaminant_transport", ENVIRONMENTAL_PRESETS)
        self.assertIn("air_quality", ENVIRONMENTAL_PRESETS)
        self.assertIn("solid_waste", ENVIRONMENTAL_PRESETS)

    def test_science_presets_content(self):
        """SCIENCE_PRESETS contains expected keys."""
        self.assertIn("machine_learning_science", SCIENCE_PRESETS)
        self.assertIn("systematic_review_methods", SCIENCE_PRESETS)

    def test_all_profiles_have_queries_and_sources(self):
        """Every profile in ALL_PRESETS has queries and sources."""
        for domain, presets in ALL_PRESETS.items():
            for name, profile in presets.items():
                self.assertIsInstance(profile, SearchProfile)
                self.assertGreaterEqual(len(profile.queries), 2, f"{domain}/{name} has < 2 queries")
                self.assertGreater(len(profile.sources), 0, f"{domain}/{name} has no sources")
                self.assertIn("openalex", profile.sources)


class TestPresetQueryContent(unittest.TestCase):
    """Tests for preset query content quality."""

    def test_slope_stability_queries_relevant(self):
        """Slope stability preset queries are relevant."""
        profile = get_preset("civil", "slope_stability")
        query_texts = [q.boolean_query.lower() for q in profile.queries]
        # Check relevance
        self.assertTrue(any("slope stability" in q for q in query_texts))
        self.assertTrue(any("factor of safety" in q for q in query_texts))
        self.assertTrue(any("landslide" in q for q in query_texts))

    def test_concrete_durability_queries_relevant(self):
        """Concrete durability preset queries are relevant."""
        profile = get_preset("structural", "concrete_durability")
        query_texts = [q.boolean_query.lower() for q in profile.queries]
        self.assertTrue(any("chloride" in q for q in query_texts))
        self.assertTrue(any("carbonation" in q for q in query_texts))
        self.assertTrue(any("freeze thaw" in q for q in query_texts))

    def test_machine_learning_queries_relevant(self):
        """Machine learning preset queries are relevant."""
        profile = get_preset("science", "machine_learning_science")
        query_texts = [q.boolean_query.lower() for q in profile.queries]
        self.assertTrue(any("machine learning" in q or "deep learning" in q for q in query_texts))
        self.assertTrue(any("image segmentation" in q for q in query_texts))
        self.assertTrue(any("physics informed" in q for q in query_texts))

    def test_preset_filters_have_from_year(self):
        """All presets have from_year filter."""
        for domain, presets in ALL_PRESETS.items():
            for name, profile in presets.items():
                self.assertIn("from_year", profile.filters, f"{domain}/{name} missing from_year")
                self.assertIsInstance(profile.filters["from_year"], int)


if __name__ == "__main__":
    unittest.main()