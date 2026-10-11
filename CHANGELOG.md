# Changelog

All notable changes to LITHOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-11

### Added
- **Multi-source retrieval**: OpenAlex, Crossref, Semantic Scholar, arXiv, Europe PMC/PubMed, CORE, DOAJ, Unpaywall adapters
- **Adapter framework**: Pluggable adapters with rate limiting, retries, polite pool email, per-source on/off flags
- **Query tooling**: Boolean query builder, synonym expansion, per-source query translation, saved search profiles (JSON), PRISMA-S compliant search logging
- **Citation chasing**: Forward (citations) and backward (references) snowballing to N levels with deduplication
- **Deduplication**: Three-tier matching (exact DOI, normalized title, fuzzy title+year+first-author) with cluster reports
- **Validation**: Crossref DOI validation, retraction/correction detection, preprint-to-published matching, configurable predatory venue flagging, metadata completeness scoring
- **Screening support**: Inclusion/exclusion rules (JSON), keyword scoring, offline TF-IDF/BM25 relevance ranking, two-reviewer export with disagreement columns, persisted screening states
- **Outputs**: CSV, XLSX, JSON, RIS, BibTeX, CSL-JSON; PRISMA 2020/PRISMA-ScR flow diagrams (SVG/PNG); evidence maps (by year, venue, keyword, type, source); search reports (Markdown/DOCX)
- **Analytics**: Publication trends, top venues/authors, keyword co-occurrence matrix, simple topic clusters (connected components)
- **Reproducibility**: Run manifests (versions, parameters, timestamps, hashes), file-based cache with TTL for resume, deterministic ordering, `--dry-run`, change ledgers (UNCHANGED/NEW/CHANGED/REMOVED)
- **CLI**: Subcommands (search, snowball, dedupe, validate, screen, export, report, config), `--json` machine output, exit codes, `--dry-run`
- **Python API**: `import lithos` with all core functions exposed
- **SKILL.md**: Instructions for LLM agents
- **Domain presets**: 19 generic query templates across civil, geotechnical, structural, environmental engineering, and general science, listed/exported via `lithos presets`
- **Engineering**: Package structure (src/lithos), pyproject.toml, type hints, logging, YAML/JSON config, 40+ unit tests with offline fixtures, optional live smoke tests, GitHub Actions CI workflow

### Changed
- Refactored from single script (v0.1.1) to modular package
- Backward-compatible CLI flags maintained where applicable
- MIT license retained

### Fixed
- N/A (new major version)

## [0.1.1] - 2026-01-15

### Added
- Initial single-script release
- OpenAlex search with query and year filter
- Crossref validation with retraction checking
- Basic deduplication (DOI + normalized title)
- CSV, JSON, Markdown screening table output
- PRISMA-style counts

---

## Upgrade Guide: 0.1.x → 0.2.0

### CLI Changes
| Old Flag | New Command |
|----------|-------------|
| `--query` | `lithos search --query` |
| `--queries-file` | `lithos search --queries-file` |
| `--from-year` | `lithos search --from-year` |
| `--limit` | `lithos search --limit` |
| `--out` | `lithos search --out` |

### Python API
```python
# Old (v0.1.1)
from lithos_v0_1_1 import openalex_search, validate_record

# New (v0.2.0)
import lithos
from lithos.adapters import get_adapter
openalex = get_adapter("openalex")
result = openalex.search(query, limit=100)
for record in result.records:
    lithos.validate_record(record)
```

### Output Structure
- Single `results/` directory now contains: `records.json`, `records.csv`, `search_log.md`, `prisma_flow.svg`, `dedup_report.md`, `evidence_maps/`, `analytics/`
- Run metadata in `.lithos_runs/<run_id>/` (manifest, ledger, cache)