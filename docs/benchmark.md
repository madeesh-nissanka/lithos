# Measured Validation Benchmark

LITHOS includes a **synthetic benchmark** with hand-labeled ground truth to
measure screening performance. This allows you to evaluate screening methods
with real precision, recall, F1, and work-saved metrics - not assertions.

## Running the Benchmark

```bash
# Run built-in benchmark (soil consolidation settlement)
lithos benchmark --out benchmark_results/

# Run with custom BM25 top-k
lithos benchmark --top-k 30 --out benchmark_results/

# Use custom benchmark file
lithos benchmark --input my_benchmark.json --out benchmark_results/
```

## Built-in Benchmark

The built-in benchmark (`src/lithos/data/benchmark_soil_consolidation.json`) covers:
- **Topic**: Soil consolidation settlement (textbook geotechnical topic)
- **Records**: 72 synthetic records with deterministic content
- **Ground truth**: 42 relevant, 30 irrelevant (hand-labeled)
- **Queries**: 3 query variations
- **Include terms**: 9 terms (consolidation settlement, consolidation, settlement, compression of, volume change, pore pressure dissipation, degree of consolidation, secondary compression, creep)
- **Exclude terms**: 15 terms (asphalt, pavement, concrete, corrosion, liquefaction, scour, vibration, rockfill, market, accounting, psychology, ceramic, sintering, noise, traffic)

All records are **synthetic** with reserved-prefix DOIs (`10.99999/synthetic.bench.*`)
and ids `syn-bench-NNN`. No real bibliographic data is used.

## Methods Evaluated

| Method | Description |
|--------|-------------|
| `rules` | Rule-based screening using include/exclude terms |
| `bm25_top_k` | BM25 ranking, top-k auto-included |
| `rules_then_bm25` | Rules first, then BM25 on unscreened remainder |

## Output Files

```
benchmark_results/
├── benchmark_metrics.json   # Machine-readable metrics
└── benchmark_report.md      # Human-readable table
```

## Example Output

Real output of `lithos benchmark` on the bundled benchmark (v0.3.0):

```
# LITHOS screening benchmark: synthetic_soil_consolidation_v1

- Records: 72  Relevant (ground truth): 42
- Fully synthetic, hand-labeled benchmark; measures screening, not live retrieval.

| Method | TP | FP | FN | TN | Precision | Recall | F1 | Auto-screened | Work saved |
|---|---|---|---|---|---|---|---|---|---|
| rules | 34 | 2 | 2 | 15 | 0.944 | 0.944 | 0.944 | 53 | 73.6% |
| bm25_top_k | 36 | 6 | 6 | 24 | 0.857 | 0.857 | 0.857 | 60 | 83.3% |
| rules_then_bm25 | 40 | 2 | 2 | 28 | 0.952 | 0.952 | 0.952 | 59 | 81.9% |
```

Rules decide 53 of 72 records automatically (73.6% work saved) at 0.944
precision/recall; the combined pass reaches 0.952 precision/recall while still
auto-deciding 59 of 72 records. Reproduce with `lithos benchmark --out out/`.

## Metrics Definitions

- **TP** (True Positives): Relevant records correctly included
- **FP** (False Positives): Irrelevant records incorrectly included
- **FN** (False Negatives): Relevant records incorrectly excluded
- **TN** (True Negatives): Irrelevant records correctly excluded
- **Precision** = TP / (TP + FP)
- **Recall** = TP / (TP + FN)
- **F1** = 2 * Precision * Recall / (Precision + Recall)
- **Auto-screened** = records the method decides automatically (an INCLUDE or EXCLUDE decision, no reviewer input)
- **Work saved** = Auto-screened / Total records

## Creating Custom Benchmarks

Create a JSON file with this structure:

```json
{
  "name": "my_benchmark_v1",
  "topic": "my topic",
  "description": "Description of the benchmark",
  "queries": ["query 1", "query 2"],
  "include_terms": ["term1", "term2"],
  "exclude_terms": ["term3", "term4"],
  "records": [
    {
      "id": "rec_001",
      "title": "Record title",
      "abstract": "Abstract text",
      "year": 2020,
      "doi": "10.99999/custom.001",
      "venue": "Journal",
      "authors": ["Author A"],
      "source": "synthetic",
      "keywords": ["kw1"],
      "publication_type": "journal-article"
    }
  ],
  "relevant_ids": ["rec_001", "rec_002"]
}
```

## Python API

```python
from lithos.benchmark import load_benchmark, run_benchmark, metrics_markdown

# Load benchmark
benchmark = load_benchmark(Path("my_benchmark.json"))

# Run evaluation
results = run_benchmark(benchmark, bm25_top_k=25)

# Print markdown table
print(metrics_markdown(results))

# Access metrics programmatically
for method in results["methods"]:
    print(f"{method['method']}: P={method['precision']:.3f}, R={method['recall']:.3f}, F1={method['f1']:.3f}, Work saved={method['work_saved']:.1%}")
```

## Purpose

This benchmark is designed to:
- **Measure, not assert** screening quality
- Compare rule-based vs. ranking-based approaches
- Quantify reviewer work saved by auto-screening
- Provide a regression test for screening logic changes
- Remain fully offline and deterministic

It does **not** measure:
- Live retrieval quality (depends on external APIs)
- Real-world topic performance (topic-specific)
- Human reviewer performance