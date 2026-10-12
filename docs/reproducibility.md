# Reproducibility

LITHOS is designed for reproducible literature reviews. Every run produces
detailed manifests, caches responses for resumption, and tracks changes
between runs.

## Run Manifests

Each search run creates a manifest in `.lithos_runs/<run_id>/`:

```
.lithos_runs/
└── run_1702345678/
    ├── manifest_run_1702345678.json    # Full run manifest
    ├── ledger_run_1702345678.json      # Change ledger (vs previous run)
    └── cache/                          # Cached API responses
        ├── openalex/
        ├── crossref/
        └── ...
```

### Manifest Contents

```json
{
  "run_id": "run_1702345678",
  "lithos_version": "0.3.0",
  "python_version": "3.11.9",
  "started_at": "2026-10-12T10:00:00Z",
  "completed_at": "2026-10-12T10:05:30Z",
  "config_hash": "sha256...",
  "parameters": {
    "queries": ["soil consolidation settlement"],
    "limit": 100,
    "from_year": 2015,
    "sources": ["openalex", "crossref", "semantic_scholar"]
  },
  "queries": [...],
  "sources_used": ["openalex", "crossref", "semantic_scholar"],
  "total_records_found": 234,
  "total_records_after_dedup": 198,
  "validation_summary": {
    "VALIDATED": 150,
    "VALIDATED_WITH_WARNINGS": 30,
    "NOT_FOUND_IN_CROSSREF": 10,
    "RETRACTED": 2,
    "PREDATORY_VENUE": 6
  },
  "output_hashes": {
    "records.json": "sha256...",
    "records.csv": "sha256...",
    "search_log.md": "sha256..."
  }
}
```

## Response Caching

API responses are cached to disk for:
- **Resumption**: Re-run without re-fetching
- **Speed**: Instant repeat searches
- **Cost**: Avoid rate limits and API costs

Cache location: `.lithos_runs/<run_id>/cache/<adapter>/`

### Cache Control

```bash
# Force re-fetch (ignore cache)
lithos search ... --config config.yaml  # Uses cache from run dir

# The cache is per-run; new run = fresh cache unless you point to existing run dir
```

### Python Cache API

```python
from lithos.reproducibility import ReproducibilityManager

repo = ReproducibilityManager(Path("results/.lithos_runs"), "run_001")
repo.start_run(parameters, queries, sources)

# Check cache
cached = repo.get_cached("openalex", query, limit=100)
if cached:
    records = cached
else:
    records = adapter.search(query, limit=100)
    repo.set_cached("openalex", query, limit=100, records=records)
```

## Change Ledger

Between runs, LITHOS computes a ledger of record changes:

```json
{
  "run_id": "run_002",
  "previous_run_id": "run_001",
  "unchanged": ["doi:10.1234/aaa", "doi:10.1234/bbb"],
  "new": ["doi:10.1234/ccc"],
  "changed": ["doi:10.1234/ddd"],
  "removed": ["doi:10.1234/eee"]
}
```

**Categories:**
- **UNCHANGED**: Same content hash
- **NEW**: Not in previous run
- **CHANGED**: Different content hash (metadata updated)
- **REMOVED**: In previous run but not current

### Python Ledger API

```python
from lithos.reproducibility import RunLedger, compute_records_hash

ledger = RunLedger(run_id="run_002", previous_run_id="run_001")
# Populate by comparing record hashes
```

## Deterministic Output

LITHOS ensures deterministic output:
- Records sorted by stable ID (DOI-based)
- Deduplication uses deterministic tie-breaking
- JSON output with sorted keys
- CSV columns in fixed order

## Dry Run

Preview what would happen without executing:

```bash
lithos search --query "test" --dry-run
```

Output:
```
2026-10-12 10:00:00 - INFO - DRY RUN: Would execute 'search' with args: {...}
```

## Version Pinning

Manifests include:
- `lithos_version` - LITHOS package version
- `python_version` - Python interpreter version
- `config_hash` - SHA256 of effective config

## Best Practices for Reproducible Reviews

1. **Commit the run directory**: Include `.lithos_runs/` in version control
2. **Pin config**: Use `--config lithos.yaml` with explicit settings
3. **Record parameters**: Manifest captures all search parameters
4. **Archive outputs**: `records.json`, `search_log.md`, `prisma_flow.svg`
5. **Document decisions**: Screening forms, agreement reports, conflict lists
6. **Re-run periodically**: Compare ledgers to detect new/changed records

## Example Workflow

```bash
# First run
lithos search --query "soil consolidation" --out results/ --config config.yaml

# Screen
lithos screen --input results/records.json --rules rules.json --out results/

# Report
lithos report --input results/records.json --prisma --search-report --out reports/

# Later: update search
lithos search --query "soil consolidation" --out results_v2/ --config config.yaml

# Compare runs (Python)
from lithos.reproducibility import RunLedger
ledger = RunLedger.load(Path("results_v2/.lithos_runs/run_002/ledger_run_002.json"))
print(f"New: {len(ledger.new)}, Changed: {len(ledger.changed)}")
```