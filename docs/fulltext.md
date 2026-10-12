# Full-Text Retrieval

LITHOS can fetch legally open-access full texts from two sources:
- **Europe PMC** - Full-text XML (JATS) for PMC-indexed articles
- **Unpaywall** - Open-access locations (HTML, PDF) declared by publishers

All retrieval is polite (rate-limited), cached on disk, and extracts plain text
using the Python standard library only.

## Fetching Full Texts

```bash
# Fetch open-access full texts
lithos fetch-text --input records.json --out fulltext/
```

**Options:**
- `--limit N` - Maximum records to attempt
- `--force` - Ignore cache and refetch
- `--no-unpaywall` - Use Europe PMC only (skip Unpaywall)

## Output Structure

```
fulltext/
├── cache/                    # Cached HTTP responses (JSON)
├── texts/                    # Extracted plain text files
│   ├── record_id_1.txt
│   └── record_id_2.txt
├── fulltext_index.json       # Index mapping record_id -> text file
└── fulltext_summary.json     # Per-record fetch results
```

## Using Full Texts for Screening

```bash
lithos screen --input records.json \
  --full-text-dir fulltext/ \
  --rules rules.json \
  --out results/
```

The `--full-text-dir` argument points to the output directory from `fetch-text`.
Screening rules with `field: "fulltext"` will search the extracted full text.

## Full-Text Extraction Details

### HTML
Standard library `HTMLParser` extracts visible text, skipping `<script>`, `<style>`, etc.

### XML (Europe PMC / JATS)
`xml.etree.ElementTree` extracts text from `<title>`, `<abstract>`, `<sec>` elements.

### PDF
Best-effort extraction from FlateDecode streams using `zlib` decompression.
Pulls literal strings from `Tj`/`TJ` show-text operators.
**Limitations:** Only works for simple text-based PDFs. Scanned images, complex
encodings, and non-FlateDecode streams return empty text.

## Caching

Responses are cached in `fulltext/cache/` as JSON files keyed by URL hash.
The cache includes:
- Extracted text
- Source URL
- Content type (html/xml/pdf)
- License information
- Fetch timestamp
- OK/error status

Use `--force` to bypass cache and refetch.

## Python API

```python
from lithos.fulltext import fetch_full_texts, load_full_text

# Fetch
index, results = fetch_full_texts(
    records,
    Path("fulltext"),
    email="<your-email>",
    unpaywall_adapter=unpaywall_adapter,  # optional
    force=False
)

# Load full text for a record
text = load_full_text(record_id, Path("fulltext"), index)
```

## Screening on Full Text

```python
from lithos.screen import ScreeningSession, ScreeningRules

session = ScreeningSession(records=records)
session.rules = ScreeningRules.load(Path("rules.json"))

# Load full texts
full_texts = {}
for record in records:
    text = load_full_text(record.id, Path("fulltext"))
    if text:
        full_texts[record.id] = text

# Apply rules with full text
session.apply_rules(full_texts=full_texts)
```

## Rate Limits and Politeness

- **Europe PMC**: ~10 req/s default (configurable)
- **Unpaywall**: ~10 req/s default (configurable)
- Cache reduces repeat requests
- Always respects `Retry-After` headers
- Use `polite_email` in config for identification

## Limitations

- No scraping of paywalled content
- PDF extraction is best-effort (stdlib only)
- Complex/scanned PDFs not supported
- Full text only fetched when OA copy declared by Unpaywall or hosted by Europe PMC
- License information included when available; user responsible for compliance