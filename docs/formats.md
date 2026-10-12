# Output Formats

LITHOS supports multiple export formats for records and reports.

## Record Export Formats

### CSV (Default)
```bash
lithos export --input records.json --format csv --out records.csv
```
- Spreadsheet-compatible
- All fields included
- UTF-8 encoded
- Standard library writer (no dependencies)

### XLSX (Excel)
```bash
lithos export --input records.json --format xlsx --out records.xlsx
```
- Requires: `pip install "lithos[excel]"` (openpyxl)
- Falls back to stdlib CSV writer if openpyxl not available
- Formatted columns, frozen header row

### JSON
```bash
lithos export --input records.json --format json --out records.json
```
- Complete record data
- Nested objects preserved
- UTF-8, pretty-printed

### RIS (Reference Manager)
```bash
lithos export --input records.json --format ris --out records.ris
```
- Compatible with Zotero, Mendeley, EndNote
- Standard RIS tags (TY, AU, TI, JO, PY, VL, IS, SP, EP, DO, AB, KW, UR)

### BibTeX
```bash
lithos export --input records.json --format bibtex --out records.bib
```
- LaTeX bibliography format
- Entry type: `@article`, `@inproceedings`, etc.
- Keys: `authorYEARfirstword` format

### CSL-JSON
```bash
lithos export --input records.json --format csl-json --out records.csl.json
```
- Citation Style Language JSON
- Compatible with Pandoc, Zotero, citeproc
- Rich metadata support

## Screened-Only Export

```bash
lithos export --input records.json --format csv --screened-only --out screened.csv
```
Exports only records with `screen_state != UNSCREENED`.

## Report Formats

### PRISMA Flow Diagram
```bash
# SVG (default, no dependencies)
lithos report --input records.json --prisma --out reports/

# PNG (requires matplotlib)
lithos report --input records.json --prisma --png --out reports/
```
- PRISMA 2020 / PRISMA-ScR compliant
- Counts from search, dedup, screening
- SVG: vector, scalable, editable

### Search Report
```bash
# Markdown (default)
lithos report --input records.json --search-report --out reports/

# DOCX (requires python-docx)
lithos report --input records.json --search-report --docx --out reports/
```
- Run parameters
- Source breakdown
- Validation summary
- Screening summary
- Top records table

### Evidence Maps
```bash
lithos report --input records.json --evidence-maps --out reports/
```
Generates:
- `by_year.md` - Records per year
- `by_venue.md` - Records per venue
- `by_keyword.md` - Records per keyword
- `by_type.md` - Records per publication type
- `by_source.md` - Records per source adapter

### Analytics
```bash
lithos report --input records.json --analytics --out reports/
```
Generates:
- `analytics/trends.json` - Publication trends
- `analytics/top_venues.json` - Top venues
- `analytics/top_authors.json` - Top authors
- `analytics/top_keywords.json` - Top keywords
- `analytics/keyword_cooccurrence.json` - Co-occurrence matrix
- `analytics/topic_clusters.json` - Keyword-based clusters
- `analytics/trends.png` - Plot (requires matplotlib)
- `analytics/top_venues.png` - Plot (requires matplotlib)

## Screening Output Formats

### Two-Reviewer Table
```bash
lithos screen --input records.json --two-reviewer-export --out results/
```
Creates: `screening_two_reviewer.md` with agreement column.

### Per-Reviewer Forms
```bash
lithos screen --input records.json --reviewers Alice Bob --export-forms --out results/
```
Creates: `screen_form_Alice.csv`, `screen_form_Bob.csv`

### Agreement Reports
```bash
lithos screen --input records.json --import-decisions Alice=form_A.csv --import-decisions Bob=form_B.csv --agreement --out results/
```
Creates:
- `agreement_summary.md` - Cohen's kappa, confusion matrix
- `conflicts.csv` - Disagreement details
- `agreement.json` - Machine-readable

## Dashboard Export

```bash
lithos dashboard --input records.json --out dashboard.html
```
Exports a self-contained HTML file with embedded data and localStorage persistence.
Dashboard exports CSV/JSON importable by `lithos screen --import-decisions`.

## Benchmark Reports

```bash
lithos benchmark --out benchmark_results/
```
Creates:
- `benchmark_metrics.json` - Machine-readable metrics
- `benchmark_report.md` - Human-readable table with precision, recall, F1, work saved

## Full-Text Output

```bash
lithos fetch-text --input records.json --out fulltext/
```
Creates:
- `fulltext/cache/` - Cached HTTP responses
- `fulltext/texts/` - Extracted plain text files
- `fulltext/fulltext_index.json` - Record ID to text file mapping
- `fulltext/fulltext_summary.json` - Per-record fetch results

## Programmatic Access

All formats available via Python API:

```python
from lithos import export_records, ExportFormat
from lithos.report import generate_prisma_flow, generate_search_report
from lithos.analytics import export_analytics

export_records(records, Path("out.csv"), ExportFormat.CSV)
export_records(records, Path("out.xlsx"), ExportFormat.XLSX)
export_records(records, Path("out.ris"), ExportFormat.RIS)
export_records(records, Path("out.bib"), ExportFormat.BIBTEX)
export_records(records, Path("out.csl.json"), ExportFormat.CSL_JSON)

generate_prisma_flow(records, counts, Path("prisma.svg"))
generate_search_report(records, manifest, Path("report.md"))
export_analytics(analytics, Path("analytics/"))
```