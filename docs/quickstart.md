# Quick Start

## Basic Search

```bash
# Simple search across default sources
lithos search --query "soil consolidation settlement" --limit 50 --out results/

# Search with multiple queries and year filter
lithos search --query "slope stability" --query "factor of safety slope" --from-year 2015 --validate --out results/
```

## Using Domain Presets

```bash
# List available presets
lithos presets

# Emit a preset as a search profile
lithos presets --domain civil --name soil_consolidation -o profile.json

# Search using the profile
lithos search --profile profile.json --out results/
```

## Deduplication and Screening

```bash
# Deduplicate records
lithos dedupe --input results/records.json --out results/

# Screen with rules file
lithos screen --input results/records.json --rules my_rules.json --out results/

# Screen with keyword scoring
lithos screen --input results/records.json --include-keywords "consolidation" "settlement" --exclude-keywords "pavement" --out results/

# Screen with TF-IDF ranking
lithos screen --input results/records.json --tfidf-query "soil consolidation" --tfidf-top-k 50 --out results/
```

## Two-Reviewer Screening with Agreement

```bash
# Export per-reviewer CSV forms
lithos screen --input results/records.json --reviewers Alice Bob --export-forms --out results/
# ... fill forms: screen_form_Alice.csv, screen_form_Bob.csv ...

# Import decisions and compute Cohen's kappa
lithos screen --input results/records.json --import-decisions Alice=screen_form_Alice.csv --import-decisions Bob=screen_form_Bob.csv --agreement --out results/
```

## Full-Text Retrieval

```bash
# Fetch open-access full texts (cached, polite)
lithos fetch-text --input results/records.json --out fulltext/

# Screen on full text
lithos screen --input results/records.json --full-text-dir fulltext/ --rules my_rules.json --out results/
```

## Offline HTML Dashboard

```bash
# Generate self-contained HTML dashboard
lithos dashboard --input results/records.json --out dashboard.html
# Open dashboard.html in any browser (works offline)
```

## Measured Validation Benchmark

```bash
# Run synthetic benchmark
lithos benchmark --out benchmark_results/
```

## Reports

```bash
# Generate PRISMA flow, search report, evidence maps
lithos report --input results/records.json --prisma --search-report --evidence-maps --out reports/

# With plots (requires matplotlib)
lithos report --input results/records.json --prisma --png --out reports/

# With DOCX (requires python-docx)
lithos report --input results/records.json --search-report --docx --out reports/
```