# LITHOS Architecture Contracts

This document describes the internal contracts of the `lithos` package
(v0.2.0). It is the reference for contributors and for anyone extending the
tool. The core package is **standard-library only**.

## Package layout

```
src/lithos/
  __init__.py            Public API + __version__/__author__/__license__
  __main__.py            python -m lithos entry point
  models.py              Dataclasses: Record, SearchQuery, SearchResult, ...
  http.py                HTTPClient, RateLimiter, RetryPolicy, PolitePool
  adapters.py            BaseAdapter, AdapterConfig, AdapterRegistry,
                         init_adapters(), get_adapter(), get_enabled_adapters()
  adapters_<source>.py   One module per scholarly source
  query.py               QueryBuilder, SynonymExpander, SearchProfile, SearchLogger
  presets.py             ALL_PRESETS + get_preset()/list_presets()/get_all_profiles()
  dedupe.py              deduplicate(), DedupCluster, generate_dedup_report()
  validate.py            validate_record(), ValidationConfig, retraction checks
  screen.py              ScreeningRules/Session, KeywordScorer, TFIDFRanker
  export.py              export_records() (CSV/JSON/RIS/BibTeX/CSL-JSON/XLSX)
  report.py              PRISMA flow (SVG/PNG), search report, evidence maps
  analytics.py           compute_analytics() + table exporters
  reproducibility.py     RunManifest, RunLedger, RunCache, content hashing
  cli.py                 argparse CLI (search/snowball/dedupe/validate/screen/
                         export/report/config/presets) with --json/--dry-run
```

## Data model (`models.py`)

- `Record` is the single unit of currency across the pipeline. Identity is the
  `id` field, generated in `__post_init__` from, in order of preference:
  DOI, PMID, arXiv ID, OpenAlex ID, Semantic Scholar ID, CORE ID, else a
  truncated MD5 of the title. `content_hash` hashes the bibliographic payload and
  is the basis for the reproducibility ledger.
- `SearchQuery` carries `original` and `boolean_query` text plus a `filters`
  dict (e.g. `from_year`, `to_year`, `type`).
- `SearchResult` wraps a query with `records`, `total_hits`, `source`,
  `duration_seconds`, and `errors`.
- `RecordStatus` (validation) and `ScreenState` (screening) are enums; the
  screening vocabulary additionally has `ScreenDecision`.

Invariant: records flow through stages (search → dedupe → validate → screen →
export/report) without changing type; every stage must tolerate records missing
any optional field.

## Adapters (`adapters.py`, `adapters_<source>.py`)

- `BaseAdapter` is abstract: subclasses implement `search()`,
  `translate_query()`, and `fetch_by_id()`.
- Every adapter owns an `HTTPClient` built from an `AdapterConfig`
  (`rate_limit`, `burst`, `max_retries`, `timeout`, `polite_email`, `api_key`).
  All network access goes through `HTTPClient` so retries, rate limiting, and the
  polite pool are consistent; tests patch this one object.
- `init_adapters(config)` lazily imports each concrete adapter, applies per-source
  config, and (re)populates the module-level `registry`. `core` is registered but
  disabled by default because it requires an API key.
- `get_enabled_adapters()` returns adapters whose `enabled` flag is true, in
  registration order.

## Reproducibility

- A run writes a `RunManifest` (parameters + versions) and may write a
  `RunLedger` classifying records as NEW / UNCHANGED / CHANGED / REMOVED versus a
  previous run, keyed by `content_hash`.
- `RunCache` persists raw source responses so a run can resume without refetching.
- Ordering must be deterministic; do not rely on `set` iteration order in output.

## Testing contract

- Tests live in `tests/` and use `unittest` (no third-party test runner needed).
- `tests/testhelpers.py` provides `add_src_path()`, `make_record()`, synthetic
  payloads, and `fake_http()`. No test may perform real network I/O.
- Fixtures are synthetic: textbook-level topics and reserved DOIs `10.9999/...`.
