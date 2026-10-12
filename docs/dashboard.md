# Offline HTML Screening Dashboard

LITHOS can generate a **self-contained, single-file HTML dashboard** for screening
records. The dashboard works entirely offline in any modern browser, with no
server, no CDN dependencies, and no network access required.

## Generating the Dashboard

```bash
lithos dashboard --input records.json --out dashboard.html
```

**Options:**
- `--rules PATH` - Screening rules JSON (used for suggested exclusion reasons)
- `--reviewer TEXT` - Default reviewer name
- `--dataset-id TEXT` - Stable identifier for browser-local decisions

## Features

- **Embedded data**: All records embedded as JSON in the HTML
- **Offline decisions**: Decisions persist in browser `localStorage` (per dataset)
- **Include/Exclude/Conflict buttons**: One-click screening
- **Suggested reasons**: Dropdown with reasons from screening rules
- **Custom tags**: Add arbitrary tags to records
- **Abstract toggle**: Show/hide abstracts
- **Live PRISMA counts**: Identified, Screened, Included, Excluded, Conflicts
- **Filtering**: By state (All/Unscreened/Include/Exclude/Conflict) and text search
- **Sorting**: By rank, year, title
- **Export**: CSV and JSON formats importable by `lithos screen --import-decisions`

## Using the Dashboard

1. Open `dashboard.html` in any browser
2. Enter your reviewer name
3. Click **Include**, **Exclude**, or **Conflict** for each record
4. Optionally select a reason and add tags
5. Watch PRISMA counts update live
6. Click **Export decisions CSV** or **Export decisions JSON** when done

## Importing Decisions

The exported CSV/JSON can be imported back into LITHOS:

```bash
# Import from CSV
lithos screen --input records.json \
  --import-decisions Reviewer1=decisions.csv \
  --out results/

# Import from JSON (contains reviewer name)
lithos screen --input records.json \
  --import-decisions Reviewer1=decisions.json \
  --out results/
```

## LocalStorage Persistence

- Decisions stored under key: `lithos_dash_{dataset_id}`
- Survives browser restarts
- Per-dataset isolation (different datasets don't interfere)
- Clear with **Reset decisions** button

## Dashboard Data Structure

The embedded payload includes:
```json
{
  "dataset_id": "lithos:records.json",
  "version": "0.3.0",
  "reviewer": "default_reviewer",
  "rules": { "rules": [...], "reasons": [...] },
  "records": [
    {
      "id": "doi:10.1234/example",
      "title": "Record title",
      "authors": ["Author A", "Author B"],
      "year": 2023,
      "venue": "Journal Name",
      "doi": "10.1234/example",
      "abstract": "Abstract text...",
      "source": "openalex",
      "keywords": ["keyword1", "keyword2"],
      "screen_state": "UNSCREENED"
    }
  ]
}
```

## Python API

```python
from lithos.dashboard import build_dashboard
from lithos.models import Record

records = [Record.from_dict(r) for r in json.load(open("records.json"))]
build_dashboard(
    records,
    Path("dashboard.html"),
    rules=rules_dict,  # optional
    dataset_id="my_project:v1",
    reviewer="default_reviewer"
)
```

## Integration with Dual-Reviewer Workflow

1. Generate dashboard for each reviewer:
   ```bash
   lithos dashboard --input records.json --out dash_Alice.html --reviewer Alice
   lithos dashboard --input records.json --out dash_Bob.html --reviewer Bob
   ```

2. Reviewers screen independently in their browsers

3. Export CSV from each dashboard

4. Import and compute agreement:
   ```bash
   lithos screen --input records.json \
     --import-decisions Alice=decisions_Alice.csv \
     --import-decisions Bob=decisions_Bob.csv \
     --agreement \
     --out results/
   ```

## Limitations

- Single-user (localStorage per browser)
- No concurrent editing
- Decisions not synced across machines
- For team workflows, use the file round-trip (CSV export/import)