# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.benchmark module."""
from testhelpers import add_src_path
add_src_path()

import unittest

from lithos.benchmark import (
    MethodMetrics,
    default_benchmark_rules,
    evaluate_bm25,
    evaluate_combined,
    evaluate_rules,
    load_benchmark,
    metrics_markdown,
    run_benchmark,
)

METHOD_KEYS = {
    "tp", "fp", "fn", "tn",
    "precision", "recall", "f1",
    "auto_screened", "work_saved",
}


class TestLoadBenchmark(unittest.TestCase):
    """Tests for load_benchmark."""

    def test_load_benchmark_returns_expected_shape(self):
        """load_benchmark returns name, records and non-empty relevant_ids."""
        data = load_benchmark()
        self.assertIsInstance(data, dict)
        for key in ("name", "records", "relevant_ids"):
            self.assertIn(key, data)
        self.assertGreaterEqual(len(data["records"]), 50)
        self.assertGreater(len(data["relevant_ids"]), 0)


class TestRunBenchmark(unittest.TestCase):
    """Tests for run_benchmark."""

    def test_run_benchmark_returns_three_method_dicts(self):
        """run_benchmark returns n_records, n_relevant and 3 metric dicts."""
        results = run_benchmark()
        self.assertIsInstance(results, dict)
        self.assertIn("n_records", results)
        self.assertIn("n_relevant", results)
        self.assertIsInstance(results["n_records"], int)
        self.assertGreater(results["n_records"], 0)
        self.assertGreater(results["n_relevant"], 0)

        methods = results["methods"]
        self.assertIsInstance(methods, list)
        self.assertEqual(len(methods), 3)
        for method in methods:
            self.assertIsInstance(method, dict)
            self.assertTrue(METHOD_KEYS.issubset(method.keys()), method.keys())


class TestEvaluateRules(unittest.TestCase):
    """Tests for evaluate_rules."""

    def test_evaluate_rules_metrics_are_bounded(self):
        """evaluate_rules precision/recall are in [0,1] with F1 between them."""
        benchmark = load_benchmark()
        m = evaluate_rules(benchmark)
        self.assertGreaterEqual(m.precision, 0.0)
        self.assertLessEqual(m.precision, 1.0)
        self.assertGreaterEqual(m.recall, 0.0)
        self.assertLessEqual(m.recall, 1.0)
        low = min(m.precision, m.recall)
        high = max(m.precision, m.recall)
        self.assertGreaterEqual(m.f1, low)
        self.assertLessEqual(m.f1, high)
        self.assertLessEqual(m.auto_screened, len(benchmark["records"]))
        self.assertEqual(m.total, len(benchmark["records"]))


class TestEvaluateBM25(unittest.TestCase):
    """Tests for evaluate_bm25."""

    def test_evaluate_bm25_top_k_relevant_count(self):
        """evaluate_bm25 with top_k = len(relevant_ids) stays in [0,1]."""
        benchmark = load_benchmark()
        m = evaluate_bm25(benchmark, top_k=len(benchmark["relevant_ids"]))
        self.assertGreaterEqual(m.precision, 0.0)
        self.assertLessEqual(m.precision, 1.0)
        self.assertGreaterEqual(m.recall, 0.0)
        self.assertLessEqual(m.recall, 1.0)


class TestEvaluateCombined(unittest.TestCase):
    """Tests for evaluate_combined."""

    def test_evaluate_combined_auto_screened_and_work_saved(self):
        """evaluate_combined auto_screened <= n_records and work_saved in [0,1]."""
        benchmark = load_benchmark()
        m = evaluate_combined(benchmark)
        self.assertLessEqual(m.auto_screened, len(benchmark["records"]))
        self.assertGreaterEqual(m.work_saved, 0.0)
        self.assertLessEqual(m.work_saved, 1.0)


class TestMethodMetrics(unittest.TestCase):
    """Tests for MethodMetrics."""

    def test_work_saved_uses_total_as_denominator(self):
        """work_saved divides auto_screened by the explicit total field."""
        m = MethodMetrics("demo", tp=1, fp=1, fn=1, tn=1, auto_screened=6, total=24)
        self.assertEqual(m.auto_screened, 6)
        self.assertEqual(m.total, 24)
        self.assertAlmostEqual(m.work_saved, 6 / 24)
        self.assertAlmostEqual(m.work_saved, 0.25)

    def test_work_saved_falls_back_when_total_unset(self):
        """work_saved falls back to the confusion-matrix sum when total is 0."""
        m = MethodMetrics("demo", tp=1, fp=1, fn=1, tn=1, auto_screened=2, total=0)
        self.assertAlmostEqual(m.work_saved, 0.5)


class TestMetricsMarkdown(unittest.TestCase):
    """Tests for metrics_markdown."""

    def test_metrics_markdown_contains_header_and_methods(self):
        """metrics_markdown output has the header row and every method name."""
        results = run_benchmark()
        text = metrics_markdown(results)
        self.assertIn("| Method |", text)
        for method in results["methods"]:
            self.assertIn(method["method"], text)


class TestDefaultBenchmarkRules(unittest.TestCase):
    """Tests for default_benchmark_rules."""

    def test_rules_built_from_benchmark_terms(self):
        """default_benchmark_rules builds include and exclude rules from terms."""
        benchmark = load_benchmark()
        rules = default_benchmark_rules(benchmark)
        built = [(r.type, r.pattern) for r in rules.rules]
        self.assertGreater(len(benchmark["include_terms"]), 0)
        self.assertGreater(len(benchmark["exclude_terms"]), 0)
        for term in benchmark["include_terms"]:
            self.assertIn(("include", term), built)
        for term in benchmark["exclude_terms"]:
            self.assertIn(("exclude", term), built)
        self.assertEqual(
            len(rules.rules),
            len(benchmark["include_terms"]) + len(benchmark["exclude_terms"]),
        )


class TestRunBenchmarkTiny(unittest.TestCase):
    """Tests for run_benchmark on a minimal in-memory benchmark."""

    TINY = {
        "name": "tiny_consolidation",
        "description": "Tiny synthetic benchmark on soil consolidation.",
        "topic": "soil consolidation settlement",
        "queries": ["soil consolidation settlement"],
        "include_terms": ["consolidation", "settlement"],
        "exclude_terms": ["pavement"],
        "records": [
            {
                "id": "tiny-1",
                "title": "Consolidation settlement of soft clay",
                "abstract": "Time-dependent settlement of clay under load.",
                "year": 2011,
                "keywords": ["consolidation", "clay"],
                "source": "test",
            },
            {
                "id": "tiny-2",
                "title": "Slope stability of embankments",
                "abstract": "Limit equilibrium analysis of slopes.",
                "year": 2012,
                "keywords": ["slope"],
                "source": "test",
            },
            {
                "id": "tiny-3",
                "title": "Fatigue cracking of asphalt pavement",
                "abstract": "Pavement fatigue cracking under repeated loading.",
                "year": 2013,
                "keywords": ["pavement", "asphalt"],
                "source": "test",
            },
        ],
        "relevant_ids": ["tiny-1"],
    }

    def test_run_benchmark_on_tiny_benchmark(self):
        """run_benchmark on a 3-record benchmark still returns 3 methods."""
        results = run_benchmark(self.TINY)
        self.assertEqual(results["n_records"], 3)
        self.assertEqual(results["n_relevant"], 1)
        self.assertEqual(len(results["methods"]), 3)
        for method in results["methods"]:
            self.assertTrue(METHOD_KEYS.issubset(method.keys()), method.keys())
            self.assertLessEqual(method["auto_screened"], 3)
            self.assertGreaterEqual(method["work_saved"], 0.0)
            self.assertLessEqual(method["work_saved"], 1.0)


if __name__ == "__main__":
    unittest.main()
