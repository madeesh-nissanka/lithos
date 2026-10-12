# Screening Workflow

LITHOS provides a comprehensive screening workflow for systematic and scoping reviews,
supporting rule-based screening, keyword scoring, TF-IDF/BM25 ranking, optional
semantic embeddings, dual-reviewer workflows, and full-text screening.

## Screening Methods

### 1. Rule-Based Screening

Define inclusion/exclusion rules in a JSON file:

```json
{
  "rules": [
    {
      "id": "inc_1",
      "type": "include",
      "field": "any",
      "pattern": "consolidation settlement",
      "is_regex": false,
      "case_sensitive": false,
      "description": "Include consolidation settlement studies"
    },
    {
      "id": "exc_1",
      "type": "exclude",
      "field": "venue",
      "pattern": "asphalt|pavement",
      "is_regex": true,
      "case_sensitive": false,
      "description": "Exclude pavement studies"
    }
  ]
}
```

Apply rules:
```bash
lithos screen --input records.json --rules rules.json --out results/
```

### 2. Keyword Scoring

```bash
lithos screen --input records.json \
  --include-keywords "consolidation" "settlement" "oedometer" \
  --exclude-keywords "pavement" "asphalt" "traffic" \
  --threshold 0.5 \
  --out results/
```

### 3. TF-IDF/BM25 Ranking (Default)

```bash
lithos screen --input records.json \
  --tfidf-query "soil consolidation settlement" \
  --tfidf-top-k 50 \
  --out results/
```

### 4. Semantic Embeddings (Optional Extra)

Requires: `pip install "lithos[semantic]"`

```bash
lithos screen --input records.json \
  --ranker semantic \
  --tfidf-query "soil consolidation settlement" \
  --tfidf-top-k 50 \
  --model paraphrase-MiniLM-L6-v2 \
  --out results/
```

### 5. Full-Text Screening

First fetch open-access full texts:
```bash
lithos fetch-text --input records.json --out fulltext/
```

Then screen on full text:
```bash
lithos screen --input records.json \
  --full-text-dir fulltext/ \
  --rules rules.json \
  --out results/
```

## Dual-Reviewer Workflow

### Step 1: Export Reviewer Forms

```bash
lithos screen --input records.json --reviewers Alice Bob --export-forms --out results/
```
Creates: `screen_form_Alice.csv`, `screen_form_Bob.csv`

### Step 2: Fill Forms

Each reviewer fills their CSV with decisions (INCLUDE/EXCLUDE) and reasons.

### Step 3: Import and Compute Agreement

```bash
lithos screen --input records.json \
  --import-decisions Alice=screen_form_Alice.csv \
  --import-decisions Bob=screen_form_Bob.csv \
  --agreement \
  --out results/
```

Outputs:
- `agreement_summary.md` - Cohen's kappa, percent agreement, confusion matrix
- `conflicts.csv` - Records with disagreements
- `agreement.json` - Machine-readable agreement report

### Step 4: Export Two-Reviewer Format

```bash
lithos screen --input records.json \
  --import-decisions Alice=screen_form_Alice.csv \
  --import-decisions Bob=screen_form_Bob.csv \
  --two-reviewer-export \
  --out results/
```
Creates: `screening_two_reviewer.md` with agreement column.

## Screening Rules Format

```json
{
  "rules": [
    {
      "id": "unique_id",
      "type": "include|exclude",
      "field": "title|abstract|keywords|venue|year|any|fulltext",
      "pattern": "search pattern",
      "is_regex": true|false,
      "case_sensitive": true|false,
      "description": "Human-readable description"
    }
  ]
}
```

**Fields:**
- `title` - Record title
- `abstract` - Record abstract
- `keywords` - Keywords joined as string
- `venue` - Journal/venue name
- `year` - Publication year
- `any` - All text fields combined
- `fulltext` - Full text (when using `--full-text-dir`)

**Rule Logic:**
- Exclude rules take precedence over include rules
- A record is INCLUDED if any include rule matches AND no exclude rule matches
- A record is EXCLUDED if any exclude rule matches
- Otherwise UNSCREENED

## Python API

```python
import lithos
from lithos import ScreeningRules, ScreeningSession, TFIDFRanker, KeywordScorer

# Load records
records = [Record.from_dict(r) for r in json.load(open("records.json"))]

# Create session
session = ScreeningSession(records=records)
session.add_reviewer("Alice")
session.add_reviewer("Bob")

# Apply rules
session.rules = ScreeningRules.load(Path("rules.json"))
session.apply_rules()

# Apply keyword scoring
scorer = KeywordScorer()
scorer.include_keywords = {"consolidation": 1.0, "settlement": 1.0}
scorer.exclude_keywords = {"pavement": 1.0}
session.keyword_scorer = scorer
session.apply_keyword_scoring(threshold=0.5)

# Apply TF-IDF ranking
session.tfidf_ranker = TFIDFRanker()
session.apply_tfidf_ranking("soil consolidation", top_k=50)

# Get results
for record in session.records:
    print(record.id, record.screen_state, record.screen_notes)
```

## Output Formats

- `records.json` / `records.csv` - Updated records with screen_state and screen_notes
- `screening_two_reviewer.md` - Two-reviewer table with agreement column
- `screen_form_{REVIEWER}.csv` - Per-reviewer screening forms
- `agreement_summary.md` - Cohen's kappa, confusion matrix, conflict list
- `conflicts.csv` - Disagreement details