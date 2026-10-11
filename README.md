[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23274728.svg)](https://doi.org/10.5281/zenodo.23274728)

# LITHOS v0.2.0

**Literature Retrieval and Source Validation for Scoping Reviews**

LITHOS is a dependency-light, open-source command line tool and Python library
for systematic and scoping review literature retrieval. It searches multiple
scholarly databases, deduplicates and validates records, supports screening
workflows, and produces PRISMA-compliant reports. The core runs on the Python
standard library alone.

## Features

- **Multi-source retrieval**: OpenAlex, Crossref, Semantic Scholar, arXiv,
  Europe PMC, DOAJ, Unpaywall, and CORE (key required). Per-source rate limits,
  retries, polite pool, and enable/disable flags.
- **Query tooling**: Boolean query builder, synonym expansion, per-source query
  translation, saved search profiles, and PRISMA-S style search logs.
- **Citation chasing**: Forward and backward snowballing to a configurable depth
  with deduplication at each level.
- **Deduplication**: DOI matching, normalized-title matching, and fuzzy
  title + year + first-author matching, with a merged-cluster report.
- **Validation**: Crossref DOI check, retraction/correction flags,
  preprint-to-published matching, predatory-venue detection, and metadata
  completeness scoring.
- **Screening**: Inclusion/exclusion rule files, keyword scoring, offline
  TF-IDF ranking, two-reviewer export with disagreement tracking, and persisted
  screen states.
- **Outputs**: CSV, XLSX, JSON, RIS, BibTeX, CSL-JSON; PRISMA flow diagram
  (SVG, optional PNG); evidence maps; search report (Markdown).
- **Analytics**: Publication trends, top venues/authors, keyword
  co-occurrence, and lightweight keyword-based topic clusters.
- **Reproducibility**: Run manifests, response caching/resume, deterministic
  ordering, `--dry-run`, and a NEW/UNCHANGED/CHANGED/REMOVED ledger between runs.
- **Agent-friendly**: Clean CLI subcommands with `--json`, predictable exit
  codes, a Python API (`import lithos`), and `SKILL.md`.
- **Domain presets**: Civil, geotechnical, structural, environmental
  engineering, and general science.

## Installation

```bash
# Core: Python standard library only
pip install lithos

# Optional extras (not required by the core)
pip install "lithos[excel]"   # XLSX via openpyxl (otherwise stdlib writer is used)
pip install "lithos[plots]"   # PNG PRISMA diagrams via matplotlib
pip install "lithos[docx]"    # DOCX reports via python-docx
pip install "lithos[yaml]"    # YAML configuration files
pip install "lithos[all]"
```

## Quick start

```bash
# Simple search across the default sources
lithos search --query "soil consolidation settlement" --limit 50 --out results/

# Search from a saved profile (write one from a preset)
lithos presets --domain civil --name soil_consolidation -o profile.json
lithos search --profile profile.json --out results/

# Deduplicate, then screen
lithos dedupe --input results/records.json --out results/
lithos screen --input results/records.json --rules my_rules.json --out results/

# Reports
lithos report --input results/records.json --prisma --search-report --evidence-maps --out reports/
```

## Configuration

Create `lithos.yaml` and pass `--config lithos.yaml`:

```yaml
polite_email: "reviewer@example.org"   # used in OpenAlex/Crossref polite pool
openalex:
  enabled: true
  rate_limit: 10
semantic_scholar:
  enabled: true
  rate_limit: 1
  api_key: "optional_key"
core:
  enabled: false          # requires an API key
  api_key: "your_key"
```

## Domain presets

```bash
# List all presets
lithos presets

# Emit one preset as a profile JSON
lithos presets --domain geotechnical --name foundation_design -o profile.json
```

Presets are also available from Python:

```python
import lithos
lithos.list_presets()                      # {'civil': [...], ...}
profile = lithos.get_preset("civil", "slope_stability")
```

## Python API

```python
import lithos
from lithos import SearchQuery

lithos.init_adapters({})                   # register adapters
profile = lithos.get_preset("civil", "slope_stability")

records = []
for query in profile.queries:
    for adapter in lithos.get_enabled_adapters():
        result = adapter.search(query, limit=100)
        records.extend(result.records)

records, clusters = lithos.deduplicate(records)

for record in records:
    lithos.validate_record(record)

lithos.export_records(records, "records.csv", lithos.ExportFormat.CSV)
lithos.export_records(records, "records.ris", lithos.ExportFormat.RIS)
```

## CLI reference

```
lithos search     Multi-source literature search
lithos snowball   Citation chasing (forward/backward, --levels N)
lithos dedupe     Deduplicate records
lithos validate   Crossref validation
lithos screen     Apply screening rules
lithos export     Export to CSV/XLSX/JSON/RIS/BibTeX/CSL-JSON
lithos report     PRISMA flow, search report, evidence maps, analytics
lithos presets    List/emit domain search presets
lithos config     Show configuration
```

Global flags: `--config`, `--verbose`, `--json`, `--dry-run`, `--about`,
`--version`.

## Reproducibility

A run directory contains:

- `.lithos_runs/<run_id>/manifest_<run_id>.json` - run parameters and versions
- `.lithos_runs/<run_id>/ledger_<run_id>.json` - NEW/UNCHANGED/CHANGED/REMOVED records
- `.lithos_runs/<run_id>/cache/` - cached source responses for resume
- `search_log.json` / `search_log.md` - PRISMA-S style search log

## Testing

Offline unit tests use the standard library only and never touch the network:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Author and license

Copyright (c) 2026 Madeesh P. Nissanka. Released under the [MIT License](LICENSE).

## Citation

See [CITATION.cff](CITATION.cff).

## Status

**v0.2.0** - Alpha. Core features implemented and covered by offline tests.
Live API behaviour depends on external service availability and rate limits.
CORE requires an API key and is disabled by default.

## Known limitations

- Semantic Scholar is rate limited to about 1 request/second without an API key.
- The bundled predatory-venue list is a small illustrative example; supply a
  curated list with `--predatory-list` for real reviews.
- No PDF download or full-text retrieval.
- Topic clustering is keyword-based; there are no ML embeddings in the core.
- PNG PRISMA diagrams require matplotlib, and DOCX reports require python-docx.
