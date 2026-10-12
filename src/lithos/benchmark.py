# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Measured validation for LITHOS screening workflows.

Ships a small SYNTHETIC benchmark (textbook geotechnical topic) with ground-truth
relevance labels so that screening quality can be MEASURED, not asserted:
precision, recall and reviewer-work-saved for rule screening, BM25 top-k
auto-inclusion, and a combined pass. All records and labels are synthetic and
hand-authored deterministically in data/benchmark_soil_consolidation.json.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from lithos.models import Record, ScreenState
from lithos.screen import ScreeningRules, TFIDFRanker

logger = logging.getLogger(__name__)

BENCHMARK_FILE = Path(__file__).resolve().parent / "data" / "benchmark_soil_consolidation.json"


def load_benchmark(path: Optional[Path] = None) -> dict:
    """Load the synthetic benchmark (or a user-provided benchmark file)."""
    p = Path(path) if path else BENCHMARK_FILE
    return json.loads(p.read_text(encoding="utf-8"))


@dataclass
class MethodMetrics:
    """Standard binary-relevance metrics for a screening method."""
    method: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    auto_screened: int = 0
    total: int = 0

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def work_saved(self) -> float:
        """Fraction of all records auto-decided with no reviewer effort."""
        d = self.total or (self.tp + self.fp + self.fn + self.tn)
        return self.auto_screened / d if d else 0.0

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "auto_screened": self.auto_screened,
            "work_saved": round(self.work_saved, 4),
        }


def default_benchmark_rules(benchmark: dict) -> ScreeningRules:
    """Rules derived from the benchmark itself (include terms / exclude terms)."""
    rules = ScreeningRules()
    for term in benchmark.get("include_terms", []):
        rules.add_include("any", term)
    for term in benchmark.get("exclude_terms", []):
        rules.add_exclude("any", term)
    return rules


def evaluate_rules(benchmark: dict) -> MethodMetrics:
    """Evaluate rule-based screening against benchmark ground truth."""
    records = [Record.from_dict(r) for r in benchmark["records"]]
    relevant = set(benchmark["relevant_ids"])
    rules = default_benchmark_rules(benchmark)

    m = MethodMetrics("rules")
    m.total = len(records)
    for r in records:
        state, _ = rules.evaluate(r)
        truth = r.id in relevant
        if state == ScreenState.INCLUDE:
            m.tp += truth
            m.fp += not truth
            m.auto_screened += 1
        elif state == ScreenState.EXCLUDE:
            m.fn += truth
            m.tn += not truth
            m.auto_screened += 1
    return m


def evaluate_bm25(benchmark: dict, top_k: Optional[int] = None) -> MethodMetrics:
    """Evaluate BM25 top-k auto-include against benchmark ground truth."""
    records = [Record.from_dict(r) for r in benchmark["records"]]
    relevant = set(benchmark["relevant_ids"])
    query = " ".join(benchmark.get("queries", [benchmark["topic"]]))
    if top_k is None:
        top_k = len(relevant)

    ranker = TFIDFRanker()
    ranker.fit(records)
    ranked = ranker.rank(query, records)
    top_ids = {r.id for r, _ in ranked[:top_k]}

    m = MethodMetrics("bm25_top_k")
    m.total = len(records)
    for r in records:
        pred = r.id in top_ids
        truth = r.id in relevant
        if pred and truth:
            m.tp += 1
        elif pred and not truth:
            m.fp += 1
        elif not pred and truth:
            m.fn += 1
        else:
            m.tn += 1
    m.auto_screened = m.tp + m.tn
    return m


def evaluate_combined(benchmark: dict) -> MethodMetrics:
    """Rules decide first; BM25 top-k covers the unscreened remainder."""
    records = [Record.from_dict(r) for r in benchmark["records"]]
    relevant = set(benchmark["relevant_ids"])
    rules = default_benchmark_rules(benchmark)

    m = MethodMetrics("rules_then_bm25")
    m.total = len(records)
    unscreened = []
    for r in records:
        state, _ = rules.evaluate(r)
        truth = r.id in relevant
        if state == ScreenState.INCLUDE:
            m.tp += truth
            m.fp += not truth
            m.auto_screened += 1
        elif state == ScreenState.EXCLUDE:
            m.fn += truth
            m.tn += not truth
            m.auto_screened += 1
        else:
            unscreened.append(r)

    if unscreened:
        query = " ".join(benchmark.get("queries", [benchmark["topic"]]))
        ranker = TFIDFRanker()
        ranker.fit(unscreened)
        still_relevant = len([rid for rid in relevant if rid in {u.id for u in unscreened}])
        ranked = ranker.rank(query, unscreened)
        rescue = {r.id for r, _ in ranked[: max(still_relevant, 1)]}
        for r in unscreened:
            truth = r.id in relevant
            pred = r.id in rescue
            if pred and truth:
                m.tp += 1
                m.auto_screened += 1
            elif pred and not truth:
                m.fp += 1
                m.auto_screened += 1
            elif not pred and truth:
                m.fn += 1
            else:
                m.tn += 1
    return m


def run_benchmark(benchmark: Optional[dict] = None, bm25_top_k: Optional[int] = None) -> dict:
    """Run all evaluated methods and return the metrics bundle."""
    benchmark = benchmark or load_benchmark()
    return {
        "benchmark": benchmark.get("name", "synthetic_soil_consolidation"),
        "n_records": len(benchmark["records"]),
        "n_relevant": len(benchmark["relevant_ids"]),
        "note": "Fully synthetic, hand-labeled benchmark; measures screening, not live retrieval.",
        "methods": [
            evaluate_rules(benchmark).to_dict(),
            evaluate_bm25(benchmark, bm25_top_k).to_dict(),
            evaluate_combined(benchmark).to_dict(),
        ],
    }


def metrics_markdown(results: dict) -> str:
    lines = [
        f"# LITHOS screening benchmark: {results['benchmark']}",
        "",
        f"- Records: {results['n_records']}  Relevant (ground truth): {results['n_relevant']}",
        f"- {results['note']}",
        "",
        "| Method | TP | FP | FN | TN | Precision | Recall | F1 | Auto-screened | Work saved |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in results["methods"]:
        lines.append(
            f"| {m['method']} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | "
            f"{m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | "
            f"{m['auto_screened']} | {m['work_saved']:.1%} |"
        )
    return "\n".join(lines) + "\n"
