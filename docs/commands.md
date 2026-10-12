# Commands Reference

## Global Flags

All subcommands accept:
- `--config PATH` - Configuration file (YAML/JSON)
- `--verbose`, `-v` - Verbose output
- `--json` - JSON-formatted logging output
- `--dry-run` - Show what would be done without executing
- `--version` - Show version and exit
- `--about` - Show author and license information

## `lithos search`

Multi-source literature search.

```
lithos search [OPTIONS]
```

**Options:**
- `--query`, `-q TEXT` - Search query (repeatable)
- `--queries-file PATH` - File with one query per line
- `--profile PATH` - Search profile JSON file
- `--limit INT` - Max records per source per query (default: 100)
- `--from-year INT` - Filter from year (inclusive)
- `--to-year INT` - Filter to year (inclusive)
- `--type TEXT` - Publication type filter
- `--open-access` - Open access only
- `--sources TEXT...` - Specific sources to search
- `--validate` / `--no-validate` - Crossref validation (default: on)
- `--predatory-list PATH` - Path to predatory venue list
- `--analytics` - Generate analytics
- `--out`, `-o PATH` - Output directory (default: results/)

## `lithos snowball`

Citation chasing (forward/backward).

```
lithos snowball [OPTIONS]
```

**Options:**
- `--input`, `-i PATH` - Input records JSON file (required)
- `--backward` / `--no-backward` - Backward snowballing (references; on by default)
- `--forward` / `--no-forward` - Forward snowballing (citations; on by default)
- `--max-refs INT` - Max references per record (default: 50)
- `--max-citations INT` - Max citations per record (default: 50)
- `--levels INT` - Citation-chasing depth (default: 1)
- `--out`, `-o PATH` - Output directory (default: snowball_results/)

## `lithos dedupe`

Deduplicate records.

```
lithos dedupe [OPTIONS]
```

**Options:**
- `--input`, `-i PATH` - Input records JSON file (required)
- `--out`, `-o PATH` - Output directory (default: dedupe_results/)

## `lithos validate`

Validate records against Crossref.

```
lithos validate [OPTIONS]
```

**Options:**
- `--input`, `-i PATH` - Input records JSON file (required)
- `--predatory-list PATH` - Path to predatory venue list
- `--out`, `-o PATH` - Output directory (default: validated_results/)

## `lithos screen`

Apply screening rules.

```
lithos screen [OPTIONS]
```

**Options:**
- `--input`, `-i PATH` - Input records JSON file (required)
- `--rules PATH` - Screening rules JSON file
- `--include-keywords TEXT...` - Include keywords
- `--exclude-keywords TEXT...` - Exclude keywords
- `--threshold FLOAT` - Keyword score threshold (default: 0.5)
- `--tfidf-query TEXT` - TF-IDF query for relevance ranking
- `--tfidf-top-k INT` - Top K for TF-IDF auto-include (default: 50)
- `--ranker CHOICE` - `tfidf` (default) or `semantic` (needs `lithos[semantic]`)
- `--model TEXT` - Sentence-transformers model for `--ranker semantic`
- `--full-text-dir PATH` - Directory from `lithos fetch-text` to screen on full text
- `--two-reviewer-export` - Export two-reviewer format
- `--reviewers TEXT...` - Reviewer names (two for agreement stats)
- `--export-forms` - Write per-reviewer CSV screening forms
- `--import-decisions NAME=PATH` - Import filled reviewer decisions (repeatable)
- `--agreement` - Compute Cohen's kappa + conflict list
- `--out`, `-o PATH` - Output directory (default: screened_results/)

## `lithos fetch-text`

Fetch open-access full texts (Europe PMC / Unpaywall).

```
lithos fetch-text [OPTIONS]
```

**Options:**
- `--input`, `-i PATH` - Input records JSON file (required)
- `--out`, `-o PATH` - Output directory (cache + texts + index) (default: fulltext/)
- `--limit INT` - Max records to attempt
- `--force` - Ignore cache and refetch
- `--no-unpaywall` - Do not query Unpaywall (Europe PMC only)

## `lithos dashboard`

Generate a self-contained offline HTML screening dashboard.

```
lithos dashboard [OPTIONS]
```

**Options:**
- `--input`, `-i PATH` - Input records JSON file (required)
- `--rules PATH` - Screening rules JSON (used for suggested reasons)
- `--reviewer TEXT` - Default reviewer name
- `--out`, `-o PATH` - Output HTML file (default: screening_dashboard.html)
- `--dataset-id TEXT` - Stable id for browser-local decisions

## `lithos benchmark`

Run measured screening validation on the synthetic benchmark.

```
lithos benchmark [OPTIONS]
```

**Options:**
- `--input PATH` - Optional benchmark JSON file (default: built-in soil consolidation)
- `--top-k INT` - BM25 top-k for auto-include
- `--out`, `-o PATH` - Output directory (default: benchmark/)

## `lithos export`

Export records to various formats.

```
lithos export [OPTIONS]
```

**Options:**
- `--input`, `-i PATH` - Input records JSON file (required)
- `--format`, `-f CHOICE` - Export format: csv, xlsx, json, ris, bibtex, csl-json (required)
- `--out`, `-o PATH` - Output file path (required)
- `--screened-only` - Only export screened records

## `lithos report`

Generate reports.

```
lithos report [OPTIONS]
```

**Options:**
- `--input`, `-i PATH` - Input records JSON file (required)
- `--manifest PATH` - Run manifest JSON file
- `--prisma` - Generate PRISMA flow diagram (SVG)
- `--png` - Also generate PNG (requires matplotlib)
- `--search-report` - Generate search report (Markdown)
- `--docx` - Also generate DOCX (requires python-docx)
- `--evidence-maps` - Generate evidence maps
- `--analytics` - Generate analytics
- `--out`, `-o PATH` - Output directory (default: reports/)

## `lithos presets`

List domain presets or emit one as a profile JSON.

```
lithos presets [OPTIONS]
```

**Options:**
- `--domain TEXT` - Domain (civil, geotechnical, structural, environmental, science)
- `--name TEXT` - Preset name within the domain
- `--out`, `-o PATH` - Write the profile JSON to this path
- `--json` - Output as JSON

## `lithos config`

Show current adapter configuration.

```
lithos config [OPTIONS]
```