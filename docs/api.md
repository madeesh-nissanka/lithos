# Python API Reference

LITHOS provides a clean Python API for programmatic use.

## Core Imports

```python
import lithos
from lithos import (
    Record,
    SearchQuery,
    SearchProfile,
    SearchResult,
    ValidationResult,
    ScreenState,
    ScreenDecision,
    RecordStatus,
    ExportFormat,
    BaseAdapter,
    AdapterRegistry,
    init_adapters,
    get_adapter,
    get_enabled_adapters,
    QueryBuilder,
    deduplicate,
    validate_record,
    ScreeningRules,
    ScreeningSession,
    export_records,
    generate_prisma_flow,
    generate_search_report,
    compute_analytics,
    RunManifest,
    RunLedger,
    get_preset,
    list_presets,
)
```

## Initialization

```python
# Initialize adapters with optional config
config = {
    "polite_email": "<your-email>",
    "semantic_scholar": {"api_key": "your_key"},
}
lithos.init_adapters(config)
```

## Search

```python
# Get a specific adapter
openalex = lithos.get_adapter("openalex")
crossref = lithos.get_adapter("crossref")

# Or use all enabled adapters
for adapter in lithos.get_enabled_adapters():
    result = adapter.search(query, limit=100)
    records.extend(result.records)

# Using a preset
profile = lithos.get_preset("civil", "soil_consolidation")
for query in profile.queries:
    for adapter in lithos.get_enabled_adapters():
        result = adapter.search(query, limit=100)
        records.extend(result.records)
```

## Deduplication

```python
from lithos import deduplicate, DedupCluster

records, clusters = deduplicate(records)

# Access clusters
for cluster in clusters:
    print(f"Cluster {cluster.cluster_id}: {cluster.master_record.id}")
    for dup in cluster.duplicates:
        print(f"  Duplicate: {dup.id} ({cluster.match_reasons})")
```

## Validation

```python
from lithos import validate_record, ValidationConfig

config = ValidationConfig(
    check_crossref=True,
    check_retraction=True,
    check_predatory=True,
)

for record in records:
    result = validate_record(record, config)
    print(f"{record.doi}: {result.status.value} {result.flags}")
```

## Screening

```python
from lithos import ScreeningRules, ScreeningSession, TFIDFRanker, KeywordScorer

# Create session
session = ScreeningSession(records=records)
session.add_reviewer("Alice")
session.add_reviewer("Bob")

# Rule-based screening
session.rules = ScreeningRules.load(Path("rules.json"))
session.apply_rules()

# Keyword scoring
scorer = KeywordScorer()
scorer.include_keywords = {"consolidation": 1.0, "settlement": 1.0}
scorer.exclude_keywords = {"pavement": 1.0}
session.keyword_scorer = scorer
session.apply_keyword_scoring(threshold=0.5)

# TF-IDF/BM25 ranking
session.tfidf_ranker = TFIDFRanker()
session.apply_tfidf_ranking("soil consolidation", top_k=50)

# Semantic ranking (requires lithos[semantic])
try:
    from lithos.semantic import SemanticRanker
    session.semantic_ranker = SemanticRanker()
    session.apply_semantic_ranking("soil consolidation", top_k=50)
except ImportError:
    pass  # semantic extra not installed

# Record reviewer decisions
session.record_decision("record_id", "Alice", ScreenState.INCLUDE, "Relevant")
session.record_decision("record_id", "Bob", ScreenState.EXCLUDE, "Wrong population")

# Get consensus
state, conflict = session.get_consensus("record_id")

# Agreement statistics
report = session.agreement_report("Alice", "Bob")
print(f"Kappa: {report.kappa:.4f}, Conflicts: {len(report.conflicts)}")

# Export
session.export_reviewer_form(Path("form_Alice.csv"), "Alice")
session.import_reviewer_decisions(Path("form_Alice.csv"), "Alice")
session.export_agreement(report, Path("agreement_out/"))
session.export_two_reviewer(Path("two_reviewer.md"))
```

## Full-Text Retrieval

```python
from lithos.fulltext import fetch_full_texts, load_full_text

index, results = fetch_full_texts(
    records,
    Path("fulltext"),
    email="<your-email>",
    unpaywall_adapter=lithos.get_adapter("unpaywall"),
)

# Screen on full text
full_texts = {}
for record in records:
    text = load_full_text(record.id, Path("fulltext"), index)
    if text:
        full_texts[record.id] = text

session.apply_rules(full_texts=full_texts)
```

## Export

```python
from lithos import export_records, ExportFormat

export_records(records, Path("records.csv"), ExportFormat.CSV)
export_records(records, Path("records.xlsx"), ExportFormat.XLSX)
export_records(records, Path("records.json"), ExportFormat.JSON)
export_records(records, Path("records.ris"), ExportFormat.RIS)
export_records(records, Path("records.bib"), ExportFormat.BIBTEX)
export_records(records, Path("records.csl.json"), ExportFormat.CSL_JSON)
```

## Reports

```python
from lithos import generate_prisma_flow, generate_search_report, PrismaCounts
from lithos.reproducibility import ReproducibilityManager

# PRISMA flow
counts = PrismaCounts(
    records_before_dedup=100,
    duplicates_removed=10,
    records_after_dedup=90,
    records_screened=90,
    records_included=45,
)
generate_prisma_flow(records, counts, Path("prisma.svg"), "svg")

# Search report (requires manifest)
generate_search_report(records, manifest, Path("report.md"), "md")
generate_search_report(records, manifest, Path("report.docx"), "docx")  # needs python-docx
```

## Analytics

```python
from lithos import compute_analytics, export_analytics, plot_trends, plot_top_venues

analytics = compute_analytics(records)
export_analytics(analytics, Path("analytics/"))

try:
    plot_trends(analytics, Path("analytics/trends.png"))
    plot_top_venues(analytics, Path("analytics/top_venues.png"))
except ImportError:
    pass  # matplotlib not installed
```

## Reproducibility

```python
from lithos.reproducibility import ReproducibilityManager, compute_records_hash

# Run manifest
repo = ReproducibilityManager(Path("runs"), "run_001")
repo.start_run(parameters, queries, sources)

# Cache
repo.set_cached("openalex", query, 100, records)
cached = repo.get_cached("openalex", query, 100)

# Finalize
repo.finalize(records, validation_summary, output_files)

# Ledger between runs
ledger = RunLedger(run_id="run_002", previous_run_id="run_001")
# ... compute NEW/UNCHANGED/CHANGED/REMOVED
```

## Presets

```python
from lithos import list_presets, get_preset

print(lithos.list_presets())
# {'civil': ['soil_consolidation', ...], ...}

profile = lithos.get_preset("civil", "soil_consolidation")
# Use profile.queries in search
```

## Benchmark

```python
from lithos.benchmark import load_benchmark, run_benchmark, metrics_markdown

benchmark = load_benchmark()  # or load_benchmark(Path("custom.json"))
results = run_benchmark(benchmark)
print(metrics_markdown(results))
```

## Dashboard

```python
from lithos.dashboard import build_dashboard

build_dashboard(records, Path("dashboard.html"))
```