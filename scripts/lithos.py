#!/usr/bin/env python3
"""
LITHOS: Literature Retrieval and Source Validation for Scoping Reviews

Retrieves candidate literature from OpenAlex, validates against Crossref,
and produces screening tables for scoping reviews.
"""
import argparse
import csv
import difflib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


SCHOLAR_MAILTO = os.environ.get("SCHOLAR_MAILTO", "")
UA = f"lithos/0.1" + (f" (mailto:{SCHOLAR_MAILTO})" if SCHOLAR_MAILTO else "")

DOI_URL_PREFIX = "https://doi.org/"

OPEN_ALEX_BASE = "https://api.openalex.org/works"
CROSSREF_BASE = "https://api.crossref.org/works"


def fetch_json(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rebuild_abstract(inverted_index):
    if not inverted_index:
        return ""
    pos = {}
    for word, idxs in inverted_index.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[k] for k in sorted(pos))


def normalize_title(title):
    if not title:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def strip_doi_prefix(doi):
    if not doi:
        return None
    if doi.startswith(DOI_URL_PREFIX):
        return doi[len(DOI_URL_PREFIX):]
    return doi


def title_similarity(a, b):
    return difflib.SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def openalex_search(query, limit, from_year):
    filters = []
    if from_year:
        filters.append(f"from_publication_date:{from_year}-01-01")
    url = (
        f"{OPEN_ALEX_BASE}?"
        f"search={urllib.parse.quote(query)}"
        f"&per-page={min(limit, 200)}"
        f"&select=id,doi,title,publication_year,authorships,primary_location,cited_by_count,type,abstract_inverted_index"
    )
    if filters:
        url += "&filter=" + ",".join(filters)
    if SCHOLAR_MAILTO:
        url += f"&mailto={urllib.parse.quote(SCHOLAR_MAILTO)}"

    data = fetch_json(url)
    results = []
    for w in data.get("results", []):
        doi = strip_doi_prefix(w.get("doi"))
        authors = [a["author"]["display_name"] for a in w.get("authorships", [])]
        venue = None
        pl = w.get("primary_location")
        if pl and pl.get("source"):
            venue = pl["source"].get("display_name")
        results.append({
            "openalex_id": w.get("id"),
            "doi": doi,
            "title": w.get("title"),
            "year": w.get("publication_year"),
            "authors": authors,
            "venue": venue,
            "cited_by": w.get("cited_by_count"),
            "type": w.get("type"),
            "abstract": rebuild_abstract(w.get("abstract_inverted_index")),
            "query_hits": [query],
        })
    return results, len(data.get("results", []))


def crossref_validate(doi, sleep_between=0.1):
    url = f"{CROSSREF_BASE}/{urllib.parse.quote(doi)}"
    backoffs = [2, 4, 8]
    for attempt, backoff in enumerate([0] + backoffs):
        if backoff:
            time.sleep(backoff)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                msg = json.loads(r.read())["message"]
            time.sleep(sleep_between)
            return {"ok": True, "data": msg}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"ok": False, "error": "not_found", "http_status": 404}
            if e.code in (429, 503):
                continue
            return {"ok": False, "error": f"http_{e.code}", "http_status": e.code}
        except Exception as e:
            return {"ok": False, "error": f"unreachable: {e}", "http_status": 0}
    return {"ok": False, "error": "crossref_unreachable", "http_status": 0}


def check_retraction(msg):
    for item in msg.get("update-to", []):
        if item.get("type") in ("retraction", "withdrawal"):
            return True
    return False


def first_author_surname(authors):
    if not authors:
        return None
    name = authors[0]
    # Handle "Surname, Given" format
    if "," in name:
        return name.split(",")[0].strip()
    # Handle "Given Surname" format
    parts = name.split()
    return parts[-1] if parts else None


def validate_record(record):
    doi = record.get("doi")
    if not doi:
        return "NO_DOI", ["no_doi"]

    cr = crossref_validate(doi)
    if not cr["ok"]:
        if cr["error"] == "not_found":
            return "NOT_FOUND_IN_CROSSREF", ["not_found_in_crossref"]
        return "CROSSREF_UNREACHABLE", ["crossref_unreachable"]

    msg = cr["data"]
    flags = []

    if check_retraction(msg):
        return "RETRACTED", ["retracted"]

    cr_title = (msg.get("title") or [""])[0]
    sim = title_similarity(record.get("title", ""), cr_title)
    if sim >= 0.90:
        pass
    else:
        flags.append("title_mismatch")

    cr_year = None
    issued = msg.get("issued", {})
    dp = issued.get("date-parts", [])
    if dp and dp[0]:
        cr_year = dp[0][0]
    rec_year = record.get("year")
    if cr_year and rec_year:
        if cr_year == rec_year:
            pass
        elif abs(cr_year - rec_year) == 1:
            flags.append("year_off_by_one")
        else:
            flags.append("year_mismatch")

    cr_authors = msg.get("author", [])
    cr_surnames = [a.get("family", "") for a in cr_authors if a.get("family")]
    rec_first_surname = first_author_surname(record.get("authors", []))
    if rec_first_surname:
        if rec_first_surname in cr_surnames:
            if cr_surnames and cr_surnames[0] != rec_first_surname:
                flags.append("author_order_differs")
        else:
            flags.append("author_mismatch")

    if flags:
        return "VALIDATED_WITH_WARNINGS", flags
    return "VALIDATED", []


def dedupe_records(records):
    seen_doi = {}
    seen_title = {}
    out = []
    for r in records:
        doi = (r.get("doi") or "").lower()
        norm_title = normalize_title(r.get("title", ""))
        key = None
        if doi:
            if doi in seen_doi:
                seen_doi[doi]["query_hits"].extend(r["query_hits"])
                continue
            key = doi
            seen_doi[doi] = r
        elif norm_title:
            if norm_title in seen_title:
                seen_title[norm_title]["query_hits"].extend(r["query_hits"])
                continue
            key = norm_title
            seen_title[norm_title] = r
        else:
            key = r.get("openalex_id", "")
        r["query_hits"] = sorted(set(r["query_hits"]))
        out.append(r)
    return out


def write_outputs(records, out_dir, counts):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records_json = out_dir / "records.json"
    records_json.write_text(json.dumps(records, indent=2, ensure_ascii=False))

    csv_path = out_dir / "records.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "doi", "year", "first_author", "title", "venue", "cited_by", "status", "flags", "query_hits"])
        for r in records:
            writer.writerow([
                r.get("openalex_id", ""),
                r.get("doi", "") or "",
                r.get("year", "") or "",
                first_author_surname(r.get("authors", [])) or "",
                r.get("title", "") or "",
                r.get("venue", "") or "",
                r.get("cited_by", "") or "",
                r.get("status", ""),
                ";".join(r.get("flags", [])),
                ";".join(r.get("query_hits", [])),
            ])

    md_path = out_dir / "screening.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("| include? (Y/N) | id | doi | year | first_author | title | venue | cited_by | status | flags |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for r in records:
            doi_disp = r.get("doi", "") or ""
            title_disp = (r.get("title", "") or "").replace("|", "\\|")
            venue_disp = (r.get("venue", "") or "").replace("|", "\\|")
            f.write(f"| | {r.get('openalex_id','')} | {doi_disp} | {r.get('year','')} | {first_author_surname(r.get('authors',[])) or ''} | {title_disp} | {venue_disp} | {r.get('cited_by','')} | {r.get('status','')} | {';'.join(r.get('flags',[]))} |\n")

    for r in records:
        st = r.get("status", "")
        if st == "VALIDATED":
            counts["validated"] += 1
        elif st == "VALIDATED_WITH_WARNINGS":
            counts["with_warnings"] += 1
        elif st == "NO_DOI":
            counts["no_doi"] += 1
        elif st == "MISMATCH":
            counts["mismatch"] += 1
        elif st == "RETRACTED":
            counts["retracted"] += 1
        elif st == "CROSSREF_UNREACHABLE":
            counts["unreachable"] += 1

    counts_path = out_dir / "counts.json"
    counts_path.write_text(json.dumps(counts, indent=2))


def main():
    ap = argparse.ArgumentParser(description="LITHOS: Literature retrieval and validation for scoping reviews")
    ap.add_argument("--query", action="append", help="Search query (repeatable)")
    ap.add_argument("--queries-file", help="File with one query per line")
    ap.add_argument("--from-year", type=int, help="Filter from publication year (inclusive)")
    ap.add_argument("--limit", type=int, default=40, help="Max records per query from OpenAlex")
    ap.add_argument("--out", default="results", help="Output directory")
    args = ap.parse_args()

    queries = []
    if args.query:
        queries.extend(args.query)
    if args.queries_file:
        queries.extend(Path(args.queries_file).read_text().splitlines())
    queries = [q.strip() for q in queries if q.strip()]
    if not queries:
        ap.error("At least one --query or --queries-file is required")

    all_records = []
    counts = {
        "records_identified_per_query": {},
        "validated": 0,
        "with_warnings": 0,
        "no_doi": 0,
        "mismatch": 0,
        "retracted": 0,
        "unreachable": 0,
    }
    for q in queries:
        print(f"Querying OpenAlex: {q}", file=sys.stderr)
        recs, n = openalex_search(q, args.limit, args.from_year)
        counts["records_identified_per_query"][q] = n
        all_records.extend(recs)
        time.sleep(0.5)

    before_dedup = len(all_records)
    records = dedupe_records(all_records)
    after_dedup = len(records)

    counts["total_identified"] = before_dedup
    counts["duplicates_removed"] = before_dedup - after_dedup
    counts["records_after_dedup"] = after_dedup

    print(f"Identified {before_dedup} records, {before_dedup - after_dedup} duplicates removed", file=sys.stderr)

    for i, r in enumerate(records):
        status, flags = validate_record(r)
        r["status"] = status
        r["flags"] = flags
        print(f"  [{i+1}/{len(records)}] {r.get('doi') or 'NO_DOI'} -> {status}", file=sys.stderr)

    write_outputs(records, args.out, counts)
    print(f"Outputs written to {args.out}/", file=sys.stderr)


if __name__ == "__main__":
    main()