---
name: lithos
description: Retrieve candidate literature from OpenAlex, validate against Crossref, and produce a screening table for scoping reviews.
---

# LITHOS: Literature Retrieval and Source Validation for Scoping Reviews

LITHOS retrieves candidate records from OpenAlex for a set of search strings, deduplicates them, validates each record that has a DOI against Crossref, and writes a screening table for human review. It does not generate citations.

## When to use
- Starting a scoping review and need a structured, auditable set of candidate records.
- You have 3 to 6 search strings that capture the review scope.
- You need a PRISMA-ScR style flow diagram with real counts.

## Workflow
1. State the review questions clearly.
2. Write 3 to 6 search strings that capture the concepts and their synonyms.
3. Run the script with the search strings, a from-year, and a record limit per query.
4. Screen titles and abstracts from `screening.md` and record include/exclude decisions with reasons.
5. Never cite a record whose status is not VALIDATED or VALIDATED_WITH_WARNINGS without telling the user.
6. Never invent a reference.

## Command-line interface
```bash
python3 scripts/lithos.py --query "scoping review methodology" --query "automated citation screening" --from-year 2005 --limit 40 --out results/
```
Accept repeated `--query` or `--queries-file` (one per line).

## Outputs
- `records.json`: all fields for every record.
- `records.csv`: id, doi, year, first_author, title, venue, cited_by, status, flags, query_hits.
- `screening.md`: markdown table with an empty "include? (Y/N)" column.
- `counts.json`: PRISMA-ScR style flow counts.

## Validation statuses
- VALIDATED: DOI resolves, title similarity >= 0.90, first-author surname present, year within +/-1.
- VALIDATED_WITH_WARNINGS: author_order_differs, year_off_by_one, DOI case/formatting fixed.
- NO_DOI: record has no DOI.
- NOT_FOUND_IN_CROSSREF: DOI returns 404.
- MISMATCH: DOI resolves but title similarity < 0.90 or first author absent or year off by >1.
- RETRACTED: Crossref update-to indicates retraction or withdrawal.
- CROSSREF_UNREACHABLE: Crossref returned 429/503 after backoff.

## Design decisions
- Google Scholar is not used (no API, scraping breaks terms). OpenAlex and Crossref only.
- Crossref author order sometimes differs from the printed paper; author-order difference is a WARNING only.
- Abstracts reconstructed from OpenAlex inverted index.
- Sleep 0.1 s between Crossref calls; exponential backoff on 429/503.

## Limitations
- OpenAlex coverage varies by field; conference proceedings and theses may be missed.
- Paywalled full texts are not retrieved.
- Abstract reconstruction may lose formatting.
- Crossref bibliographic search not used here; exact DOI lookup only.