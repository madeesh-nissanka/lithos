# LITHOS v0.3.0 - Skill for LLM Agents

## Overview
LITHOS is a literature retrieval and source validation tool for scoping and systematic reviews. It provides multi-source search, deduplication, validation, screening, and reporting capabilities.

## Installation
```bash
pip install "lithos[all]"       # with optional extras (excel, plots, docx, yaml, semantic)
# or
pip install lithos              # core only (Python standard library)
```

## Quick Start (CLI)
```bash
# Basic search
lithos search --query "soil consolidation settlement" --limit 50 --out results/

# Search with multiple queries and validation
lithos search --query "slope stability" --query "factor of safety slope" --from-year 2015 --validate --out results/

# Emit a domain preset, then search from it
lithos presets --domain civil --name soil_consolidation -o profile.json
lithos search --profile profile.json --out results/

# Two-reviewer screening with agreement stats
lithos screen --input results/records.json --reviewers Alice Bob --export-forms --out results/
# ... fill forms: screen_form_Alice.csv, screen_form_Bob.csv ...
lithos screen --input results/records.json --import-decisions Alice=screen_form_Alice.csv --import-decisions Bob=screen_form_Bob.csv --agreement --out results/

# Fetch open-access full texts for full-text screening
lithos fetch-text --input results/records.json --out fulltext/
lithos screen --input results/records.json --full-text-dir fulltext/ --rules my_rules.json --out results/

# Generate offline HTML screening dashboard
lithos dashboard --input results/records.json --out dashboard.html

# Run measured validation benchmark
lithos benchmark --out benchmark_results/

# Generate reports from existing results
lithos report --input results/records.json --prisma --search-report --evidence-maps --out reports/
```

## Python API
```python
import lithos
from lithos import SearchQuery, SearchProfile, get_preset

# Load a preset
profile = get_preset("civil", "soil_consolidation")

# Search
records = []
for query in profile.queries:
    for adapter in lithos.get_enabled_adapters():
        result = adapter.search(query, limit=100)
        records.extend(result.records)

# Deduplicate
records, clusters = lithos.deduplicate(records)

# Validate
for record in records:
    lithos.validate_record(record)

# Export
lithos.export_records(records, "results.csv", lithos.ExportFormat.CSV)
lithos.export_records(records, "records.ris", lithos.ExportFormat.RIS)

# Generate PRISMA flow
from lithos.report import PrismaCounts, generate_prisma_flow
counts = PrismaCounts(records_before_dedup=len(records), records_after_dedup=len(records))
generate_prisma_flow(records, counts, "prisma.svg")
```

## Subcommands

### `lithos search`
Search across multiple sources.
- `--query`, `-q`: Search query (repeatable)
- `--queries-file`: File with one query per line
- `--profile`: Search profile JSON file
- `--limit`: Max records per source per query (default: 100)
- `--from-year` / `--to-year`: Publication year filters
- `--type`: Publication type filter
- `--open-access`: Open access only
- `--sources`: Specific sources to search
- `--validate` / `--no-validate`: Crossref validation (default: on)
- `--predatory-list`: Path to predatory venue list
- `--analytics`: Generate analytics
- `--out`, `-o`: Output directory (default: results/)

### `lithos snowball`
Citation chasing (forward/backward). Both directions are on by default; use
`--levels N` to chase more than one hop.
- `--input`, `-i`: Input records JSON file
- `--backward`: Backward snowballing (references; on by default)
- `--forward`: Forward snowballing (citations; on by default)
- `--max-refs`: Max references per record (default: 50)
- `--max-citations`: Max citations per record (default: 50)
- `--levels`: Citation-chasing depth (default: 1)
- `--out`, `-o`: Output directory

### `lithos dedupe`
Deduplicate records.
- `--input`, `-i`: Input records JSON file
- `--out`, `-o`: Output directory

### `lithos validate`
Validate records against Crossref.
- `--input`, `-i`: Input records JSON file
- `--predatory-list`: Path to predatory venue list
- `--out`, `-o`: Output directory

### `lithos screen`
Apply screening rules.
- `--input`, `-i`: Input records JSON file
- `--rules`: Screening rules JSON file
- `--include-keywords`: Include keywords
- `--exclude-keywords`: Exclude keywords
- `--threshold`: Keyword score threshold (default: 0.5)
- `--tfidf-query`: TF-IDF query for relevance ranking
- `--tfidf-top-k`: Top K for TF-IDF auto-include (default: 50)
- `--ranker`: `tfidf` (default) or `semantic` (needs `lithos[semantic]`)
- `--model`: Sentence-transformers model name for `--ranker semantic`
- `--full-text-dir`: Directory from `lithos fetch-text` to screen on full text
- `--two-reviewer-export`: Export two-reviewer format
- `--reviewers`: Reviewer names (two for agreement stats)
- `--export-forms`: Write per-reviewer CSV screening forms
- `--import-decisions`: Import filled reviewer decisions (NAME=file.csv, repeatable)
- `--agreement`: Compute Cohen's kappa + conflict list
- `--out`, `-o`: Output directory

### `lithos fetch-text`
Fetch open-access full texts (Europe PMC / Unpaywall), cached and polite.
- `--input`, `-i`: Input records JSON file
- `--out`, `-o`: Output directory (cache + texts + index)
- `--limit`: Max records to attempt
- `--force`: Ignore cache and refetch
- `--no-unpaywall`: Do not query Unpaywall (Europe PMC only)

### `lithos dashboard`
Generate a self-contained offline HTML screening dashboard.
- `--input`, `-i`: Input records JSON file
- `--rules`: Screening rules JSON (used for suggested reasons)
- `--reviewer`: Default reviewer name
- `--out`, `-o`: Output HTML file
- `--dataset-id`: Stable id for browser-local decisions

### `lithos benchmark`
Run measured screening validation on the synthetic benchmark.
- `--input`: Optional benchmark JSON file (default: built-in soil consolidation)
- `--top-k`: BM25 top-k for auto-include
- `--out`, `-o`: Output directory

### `lithos export`
Export records to various formats.
- `--input`, `-i`: Input records JSON file
- `--format`, `-f`: Export format (csv, xlsx, json, ris, bibtex, csl-json)
- `--out`, `-o`: Output file path
- `--screened-only`: Only export screened records

### `lithos report`
Generate reports.
- `--input`, `-i`: Input records JSON file
- `--manifest`: Run manifest JSON file
- `--prisma`: Generate PRISMA flow diagram (SVG)
- `--png`: Also generate PNG (requires matplotlib)
- `--search-report`: Generate search report (Markdown)
- `--docx`: Also generate DOCX (requires python-docx)
- `--evidence-maps`: Generate evidence maps
- `--analytics`: Generate analytics
- `--out`, `-o`: Output directory

### `lithos presets`
List domain presets or emit one as a profile JSON.
- `--domain`: Domain (civil, geotechnical, structural, environmental, science)
- `--name`: Preset name within the domain
- `--out`, `-o`: Write the profile JSON to this path

### `lithos config`
Show current adapter configuration.

## Configuration
Create a `lithos.yaml` or `lithos.json` config file:
```yaml
polite_email: "<your-email>"
openalex:
  enabled: true
  rate_limit: 10
  burst: 10
crossref:
  enabled: true
  rate_limit: 50
  burst: 50
semantic_scholar:
  enabled: true
  rate_limit: 1
  burst: 5
  api_key: "your_api_key"  # Optional, for higher rate limits
arxiv:
  enabled: true
  rate_limit: 3
  burst: 5
europe_pmc:
  enabled: true
  rate_limit: 10
  burst: 10
core:
  enabled: false  # Requires API key
  api_key: "your_api_key"
doaj:
  enabled: true
  rate_limit: 5
  burst: 10
unpaywall:
  enabled: true
  rate_limit: 10
  burst: 20
```

## Domain Presets
Available presets by domain:
- **civil**: soil_consolidation, slope_stability, bearing_capacity, retaining_walls, ground_improvement
- **geotechnical**: foundation_design, soil_structure_interaction, geotechnical_earthquake
- **structural**: concrete_durability, reinforced_concrete, steel_structures, structural_dynamics, bridge_engineering
- **environmental**: water_treatment, contaminant_transport, air_quality, solid_waste
- **science**: machine_learning_science, systematic_review_methods

List presets: `python -c "import lithos; print(lithos.list_presets())"`

## Output Formats
- **CSV**: Spreadsheet-compatible, all fields
- **XLSX**: Excel file. Written with a built-in standard-library writer; install
  `lithos[excel]` for openpyxl-based formatting.
- **JSON**: Full record data
- **RIS**: Reference manager import
- **BibTeX**: LaTeX bibliography
- **CSL-JSON**: Citation Style Language JSON

## Reproducibility
Every run creates a manifest with:
- Parameters, queries, sources used
- Timestamps, versions, config hash
- Validation summary, output file hashes
- Cache for resume capability
- Ledger of UNCHANGED/NEW/CHANGED records between runs

## Exit Codes
- 0: Success
- 1: Error (missing files, unknown command/format, failed operation)
- 2: Argument parsing error (argparse usage error)

## Machine Output
Use `--json` for JSON-formatted logging output.

## Author and License
Copyright (c) 2026 Madeesh P. Nissanka. MIT License.