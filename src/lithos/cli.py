# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
CLI module for LITHOS - subcommands for search, snowball, dedupe, validate, screen, export, report.
"""
from __future__ import annotations
from lithos._version import VERSION
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from lithos.adapters import init_adapters, get_enabled_adapters, get_adapter, registry
from lithos.models import Record, SearchQuery, RecordStatus, ScreenState
from lithos.query import QueryBuilder, SearchProfile, SearchLogger
from lithos.dedupe import deduplicate, generate_dedup_report
from lithos.validate import validate_record, ValidationConfig, load_predatory_list
from lithos.screen import ScreeningRules, ScreeningSession, KeywordScorer, TFIDFRanker
from lithos.export import export_records, ExportFormat
from lithos.report import generate_prisma_flow, generate_search_report, PrismaCounts, generate_evidence_maps
from lithos.analytics import compute_analytics, export_analytics, plot_trends, plot_top_venues
from lithos.reproducibility import ReproducibilityManager, compute_records_hash

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool, json_output: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    if json_output:
        # JSON formatter for machine output
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                return json.dumps({
                    "timestamp": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                })
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logging.root.handlers = [handler]
    logging.root.setLevel(level)


def load_config(config_path: Optional[Path]) -> dict:
    """Load configuration from YAML/JSON file."""
    if not config_path or not config_path.exists():
        return {}
    if config_path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            return yaml.safe_load(config_path.read_text()) or {}
        except ImportError:
            logger.warning("PyYAML not installed, cannot load YAML config")
            return {}
    elif config_path.suffix == ".json":
        return json.loads(config_path.read_text())
    return {}


def parse_queries(args) -> list[SearchQuery]:
    """Parse queries from command line arguments."""
    queries = []
    if args.query:
        for q in args.query:
            queries.append(SearchQuery(original=q, boolean_query=q))
    if args.queries_file:
        content = Path(args.queries_file).read_text()
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                queries.append(SearchQuery(original=line, boolean_query=line))
    if args.profile:
        profile = SearchProfile.load(Path(args.profile))
        queries.extend(profile.queries)
    return queries


def cmd_search(args) -> int:
    """Search command - retrieve records from multiple sources."""
    config = load_config(args.config)
    init_adapters(config)

    queries = parse_queries(args)
    if not queries:
        logger.error("No queries provided")
        return 1

    # Setup reproducibility
    run_id = f"run_{int(time.time())}"
    run_dir = Path(args.out) / ".lithos_runs" / run_id
    repo = ReproducibilityManager(run_dir, run_id)

    parameters = {
        "queries": [q.original for q in queries],
        "limit": args.limit,
        "from_year": args.from_year,
        "to_year": args.to_year,
        "sources": [a.name for a in get_enabled_adapters()],
    }
    repo.start_run(parameters, queries, parameters["sources"])

    all_records = []
    search_logger = SearchLogger()

    for query in queries:
        # Apply filters to query
        if args.from_year:
            query.filters["from_year"] = args.from_year
        if args.to_year:
            query.filters["to_year"] = args.to_year
        if args.open_access:
            query.filters["open_access"] = True
        if args.type:
            query.filters["type"] = args.type

        for adapter in get_enabled_adapters():
            if args.sources and adapter.name not in args.sources:
                continue

            # Check cache
            cached = repo.get_cached(adapter.name, query, args.limit)
            if cached is not None:
                logger.info(f"Using cached results for {adapter.name}")
                records = cached
            else:
                logger.info(f"Searching {adapter.display_name}: {query.boolean_query[:80]}")
                result = adapter.search(query, args.limit)
                if result.errors:
                    for err in result.errors:
                        logger.error(f"  Error: {err}")
                records = result.records
                search_logger.log_search(adapter.name, query, result)
                repo.set_cached(adapter.name, query, args.limit, records)

            for r in records:
                r.query_hits.append(query.boolean_query)
            all_records.extend(records)
            time.sleep(0.1)  # Be polite between sources

    # Deduplication
    logger.info(f"Deduplicating {len(all_records)} records...")
    before_dedup = len(all_records)
    records, clusters = deduplicate(all_records)
    after_dedup = len(records)
    logger.info(f"After deduplication: {after_dedup} records ({before_dedup - after_dedup} duplicates removed)")

    search_logger.log_deduplication(before_dedup, after_dedup, "doi+title+fuzzy", len([c for c in clusters if c.duplicates]))

    # Validation
    if args.validate:
        logger.info("Validating records...")
        val_config = ValidationConfig()
        if args.predatory_list:
            val_config.predatory_venue_list = load_predatory_list(Path(args.predatory_list))

        validation_summary = {s.value: 0 for s in RecordStatus}
        for i, record in enumerate(records):
            result = validate_record(record, val_config)
            validation_summary[result.status.value] += 1
            if args.verbose:
                logger.info(f"  [{i+1}/{len(records)}] {record.doi or 'NO_DOI'} -> {result.status.value}")

        search_logger.log_validation(
            validation_summary.get("VALIDATED", 0),
            validation_summary.get("VALIDATED_WITH_WARNINGS", 0),
            validation_summary.get("CROSSREF_UNREACHABLE", 0) + validation_summary.get("NOT_FOUND_IN_CROSSREF", 0),
            validation_summary.get("RETRACTED", 0),
        )
    else:
        validation_summary = {}

    # Save outputs
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save records
    export_records(records, out_dir / "records.json", ExportFormat.JSON)
    export_records(records, out_dir / "records.csv", ExportFormat.CSV)

    # Save search log
    search_logger.export_prisma_s(out_dir / "search_log.md")
    search_logger.export_json(out_dir / "search_log.json")

    # Save dedup report
    if clusters:
        (out_dir / "dedup_report.md").write_text(generate_dedup_report(clusters))

    # PRISMA counts
    prisma_counts = PrismaCounts(
        records_identified={},
        records_before_dedup=before_dedup,
        duplicates_removed=before_dedup - after_dedup,
        records_after_dedup=after_dedup,
        records_screened=after_dedup,
        records_included=sum(1 for r in records if r.screen_state == ScreenState.INCLUDE),
    )

    # Generate PRISMA flow
    generate_prisma_flow(records, prisma_counts, out_dir / "prisma_flow.svg", "svg")

    # Generate search report
    manifest = repo.manifest
    if manifest:
        manifest.total_records_found = before_dedup
        manifest.total_records_after_dedup = after_dedup
        manifest.validation_summary = validation_summary
        final_files = [
            out_dir / "records.json",
            out_dir / "records.csv",
            out_dir / "search_log.md",
            out_dir / "prisma_flow.svg",
        ]
        repo.finalize(records, validation_summary, final_files)
        generate_search_report(records, manifest, out_dir / "search_report.md", "md")

    # Evidence maps
    generate_evidence_maps(records, out_dir / "evidence_maps")

    # Analytics
    if args.analytics:
        analytics = compute_analytics(records)
        export_analytics(analytics, out_dir / "analytics")
        try:
            plot_trends(analytics, out_dir / "analytics" / "trends.png")
            plot_top_venues(analytics, out_dir / "analytics" / "top_venues.png")
        except ImportError:
            logger.warning("matplotlib not available, skipping plots")

    logger.info(f"Search complete. Outputs in {out_dir}")
    return 0


def cmd_snowball(args) -> int:
    """Snowball command - multi-level forward/backward citation chasing."""
    config = load_config(args.config)
    init_adapters(config)

    # Load records from previous search
    records_path = Path(args.input)
    if not records_path.exists():
        logger.error(f"Input file not found: {records_path}")
        return 1

    records = [Record.from_dict(r) for r in json.loads(records_path.read_text())]

    crossref = get_adapter("crossref")
    semantic_scholar = get_adapter("semantic_scholar")
    levels = max(1, int(getattr(args, "levels", 1)))

    seen: set[str] = {r.id for r in records}
    new_records: list[Record] = []
    frontier: list[Record] = list(records)

    for level in range(1, levels + 1):
        next_frontier: list[Record] = []

        def _collect(rec: Record, kind: str, depth: int) -> None:
            if rec is None or rec.id in seen:
                return
            if kind == "backward":
                rec.query_hits = [f"backward-L{level}:{rec.id}"]
            else:
                rec.query_hits = [f"forward-L{level}:{rec.id}"]
            seen.add(rec.id)
            new_records.append(rec)
            next_frontier.append(rec)

        for record in frontier:
            # Backward snowballing (references)
            if args.backward:
                ref_dois = list(record.referenced_works)
                if not ref_dois and semantic_scholar and record.doi:
                    fetched = semantic_scholar.fetch_by_id(record.doi, "doi")
                    if fetched:
                        ref_dois = fetched.referenced_works
                for ref_doi in ref_dois[: args.max_refs]:
                    if ref_doi in seen:
                        continue
                    rec = crossref.fetch_by_id(ref_doi, "doi") if crossref else None
                    if rec is None and semantic_scholar:
                        rec = semantic_scholar.fetch_by_id(ref_doi, "doi")
                    _collect(rec, "backward", level)

            # Forward snowballing (citations)
            if args.forward:
                cit_dois = list(record.citing_works)
                if not cit_dois and semantic_scholar and record.doi:
                    fetched = semantic_scholar.fetch_by_id(record.doi, "doi")
                    if fetched:
                        cit_dois = fetched.citing_works
                for cit_doi in cit_dois[: args.max_citations]:
                    if cit_doi in seen:
                        continue
                    rec = semantic_scholar.fetch_by_id(cit_doi, "doi") if semantic_scholar else None
                    _collect(rec, "forward", level)

        logger.info(f"Snowballing level {level}: +{len(next_frontier)} records")
        frontier = next_frontier
        if not frontier:
            break

    # Combine and deduplicate
    all_records = records + new_records
    before = len(all_records)
    records, clusters = deduplicate(all_records)
    logger.info(
        f"Snowballing: {len(new_records)} new records found, {before - len(records)} duplicates removed"
    )

    # Save
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    export_records(records, out_dir / "records.json", ExportFormat.JSON)
    export_records(records, out_dir / "records.csv", ExportFormat.CSV)
    (out_dir / "dedup_report.md").write_text(generate_dedup_report(clusters))

    return 0


def cmd_dedupe(args) -> int:
    """Dedupe command - deduplicate records."""
    records_path = Path(args.input)
    records = [Record.from_dict(r) for r in json.loads(records_path.read_text())]

    records, clusters = deduplicate(records)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    export_records(records, out_dir / "records.json", ExportFormat.JSON)
    export_records(records, out_dir / "records.csv", ExportFormat.CSV)
    (out_dir / "dedup_report.md").write_text(generate_dedup_report(clusters))

    logger.info(f"Deduplication complete: {len(records)} unique records")
    return 0


def cmd_validate(args) -> int:
    """Validate command - validate records against Crossref."""
    config = load_config(args.config)
    init_adapters(config)

    records_path = Path(args.input)
    records = [Record.from_dict(r) for r in json.loads(records_path.read_text())]

    val_config = ValidationConfig()
    if args.predatory_list:
        val_config.predatory_venue_list = load_predatory_list(Path(args.predatory_list))

    validation_summary = {s.value: 0 for s in RecordStatus}
    for i, record in enumerate(records):
        result = validate_record(record, val_config)
        validation_summary[result.status.value] += 1
        if args.verbose:
            logger.info(f"  [{i+1}/{len(records)}] {record.doi or 'NO_DOI'} -> {result.status.value} {result.flags}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    export_records(records, out_dir / "records.json", ExportFormat.JSON)
    export_records(records, out_dir / "records.csv", ExportFormat.CSV)

    (out_dir / "validation_summary.json").write_text(json.dumps(validation_summary, indent=2))
    logger.info(f"Validation complete: {validation_summary}")
    return 0


def cmd_screen(args) -> int:
    """Screen command - apply screening rules."""
    records_path = Path(args.input)
    records = [Record.from_dict(r) for r in json.loads(records_path.read_text())]

    session = ScreeningSession(records=records)

    full_texts: dict[str, str] = {}
    if getattr(args, "full_text_dir", None):
        from lithos.fulltext import load_full_text

        ft_dir = Path(args.full_text_dir)
        entries: dict[str, str] = {}
        idx_path = ft_dir / "fulltext_index.json"
        if idx_path.exists():
            entries = json.loads(idx_path.read_text(encoding="utf-8")).get("entries", {})
        for record in records:
            text = load_full_text(record.id, ft_dir, entries)
            if text:
                full_texts[record.id] = text
        logger.info(f"Loaded {len(full_texts)} cached full texts from {ft_dir}")

    reviewer_names = list(getattr(args, "reviewers", None) or [])
    for name in reviewer_names:
        session.add_reviewer(name)

    for spec in getattr(args, "import_decisions", None) or []:
        if "=" not in spec:
            logger.error(f"--import-decisions expects NAME=file.csv, got: {spec}")
            return 2
        name, _, file = spec.partition("=")
        session.add_reviewer(name)
        n = session.import_reviewer_decisions(Path(file), name)
        logger.info(f"Imported {n} decisions for reviewer {name}")
        reviewer_names = session.reviewers

    if args.rules:
        session.rules = ScreeningRules.load(Path(args.rules))
        session.apply_rules(full_texts)

    if args.include_keywords or args.exclude_keywords:
        scorer = KeywordScorer()
        if args.include_keywords:
            for kw in args.include_keywords:
                scorer.include_keywords[kw] = 1.0
        if args.exclude_keywords:
            for kw in args.exclude_keywords:
                scorer.exclude_keywords[kw] = 1.0
        session.keyword_scorer = scorer
        session.apply_keyword_scoring(args.threshold or 0.5, full_texts)

    if args.tfidf_query:
        session.tfidf_ranker = TFIDFRanker()
        session.apply_tfidf_ranking(args.tfidf_query, args.tfidf_top_k or 50, full_texts)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if session.decisions:
        applied = 0
        for record in records:
            state, conflict = session.get_consensus(record.id)
            if state != ScreenState.UNSCREENED:
                record.screen_state = state
                applied += 1
        logger.info(f"Applied {applied} reviewer consensus decisions")

    export_records(records, out_dir / "records.json", ExportFormat.JSON)
    export_records(records, out_dir / "records.csv", ExportFormat.CSV)

    if args.two_reviewer_export:
        session.export_two_reviewer(out_dir / "screening_two_reviewer.md")

    if getattr(args, "export_forms", False):
        form_names = reviewer_names if len(reviewer_names) >= 2 else ["Reviewer1", "Reviewer2"]
        for name in form_names:
            session.export_reviewer_form(out_dir / f"screen_form_{name}.csv", name)
        logger.info(f"Exported reviewer forms: {form_names}")

    if getattr(args, "agreement", False):
        if len(session.reviewers) < 2:
            logger.error("Agreement requires two reviewers (--reviewers A B or --import-decisions twice)")
            return 2
        report = session.agreement_report(session.reviewers[0], session.reviewers[1])
        session.export_agreement(report, out_dir)
        (out_dir / "agreement.json").write_text(json.dumps(report.to_dict(), indent=2))
        logger.info(
            f"Agreement: {report.percent_agreement:.1f}% absolute, kappa={report.kappa:.4f}, "
            f"conflicts={len(report.conflicts)}"
        )

    logger.info(f"Screening complete. Included: {sum(1 for r in records if r.screen_state == ScreenState.INCLUDE)}")
    return 0


def cmd_fetch_text(args) -> int:
    """Fetch open-access full texts (Europe PMC / Unpaywall), cached and polite."""
    config = load_config(args.config)
    init_adapters(config)

    records_path = Path(args.input)
    records = [Record.from_dict(r) for r in json.loads(records_path.read_text())]
    if args.limit:
        records = records[: args.limit]

    unpaywall = None
    if not args.no_unpaywall:
        try:
            unpaywall = get_adapter("unpaywall")
        except Exception:
            unpaywall = None

    from lithos.fulltext import fetch_full_texts

    out_dir = Path(args.out)
    index, results = fetch_full_texts(
        records, out_dir,
        email=config.get("polite_email"),
        unpaywall_adapter=unpaywall,
        force=args.force,
    )
    summary = {
        "requested": len(records),
        "with_full_text": len(index),
        "results": results,
    }
    (out_dir / "fulltext_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info(f"Full text retrieved for {len(index)}/{len(records)} records (index: {out_dir / 'fulltext_index.json'})")
    return 0


def cmd_dashboard(args) -> int:
    """Generate a self-contained offline HTML screening dashboard."""
    records_path = Path(args.input)
    records = [Record.from_dict(r) for r in json.loads(records_path.read_text())]

    rules_data = None
    if args.rules:
        rules_data = json.loads(Path(args.rules).read_text(encoding="utf-8"))

    from lithos.dashboard import build_dashboard

    out_path = Path(args.out)
    if out_path.is_dir() or out_path.suffix.lower() not in (".html", ".htm"):
        out_path = out_path / "screening_dashboard.html"
    dataset_id = args.dataset_id or f"lithos:{records_path.name}"
    build_dashboard(records, out_path, rules=rules_data, dataset_id=dataset_id, reviewer=args.reviewer)
    print(f"Dashboard: {out_path} (open in any browser, works offline)")
    return 0


def cmd_benchmark(args) -> int:
    """Run measured screening validation on the synthetic benchmark."""
    from lithos.benchmark import load_benchmark, run_benchmark, metrics_markdown

    bench = load_benchmark(Path(args.input) if args.input else None)
    results = run_benchmark(bench, args.top_k)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "benchmark_metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    md = metrics_markdown(results)
    (out_dir / "benchmark_report.md").write_text(md, encoding="utf-8")
    print(md)
    logger.info(f"Benchmark outputs: {out_dir}/benchmark_metrics.json, {out_dir}/benchmark_report.md")
    return 0


def cmd_export(args) -> int:
    """Export command - export records to various formats."""
    records_path = Path(args.input)
    records = [Record.from_dict(r) for r in json.loads(records_path.read_text())]

    fmt = ExportFormat(args.format.lower())
    out_path = Path(args.out)
    export_records(records, out_path, fmt, args.screened_only)
    logger.info(f"Exported {len(records)} records to {out_path}")
    return 0


def cmd_report(args) -> int:
    """Report command - generate reports."""
    records_path = Path(args.input)
    records = [Record.from_dict(r) for r in json.loads(records_path.read_text())]

    manifest_path = Path(args.manifest) if args.manifest else None
    manifest = load_run_manifest(manifest_path) if manifest_path else None

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.prisma:
        # Compute PRISMA counts
        prisma_counts = PrismaCounts(
            records_identified={},
            records_before_dedup=len(records),
            duplicates_removed=0,
            records_after_dedup=len(records),
            records_screened=len(records),
            records_included=sum(1 for r in records if r.screen_state == ScreenState.INCLUDE),
        )
        generate_prisma_flow(records, prisma_counts, out_dir / "prisma_flow.svg", "svg")
        if args.png:
            generate_prisma_flow(records, prisma_counts, out_dir / "prisma_flow.png", "png")

    if args.search_report:
        if not manifest:
            # Create minimal manifest
            from lithos.reproducibility import create_run_manifest
            manifest = create_run_manifest("report_only", {}, [], [])
        generate_search_report(records, manifest, out_dir / "search_report.md", "md")
        if args.docx:
            generate_search_report(records, manifest, out_dir / "search_report.docx", "docx")

    if args.evidence_maps:
        generate_evidence_maps(records, out_dir / "evidence_maps")

    if args.analytics:
        analytics = compute_analytics(records)
        export_analytics(analytics, out_dir / "analytics")
        try:
            plot_trends(analytics, out_dir / "analytics" / "trends.png")
            plot_top_venues(analytics, out_dir / "analytics" / "top_venues.png")
        except ImportError:
            logger.warning("matplotlib not available, skipping plots")

    logger.info(f"Reports generated in {out_dir}")
    return 0


def cmd_config(args) -> int:
    """Config command - show current configuration."""
    config = load_config(args.config)
    init_adapters(config)

    print(json.dumps({
        "adapters": {
            name: {
                "enabled": adapter.enabled,
                "rate_limit": adapter.config.rate_limit,
                "burst": adapter.config.burst,
            }
            for name, adapter in registry._adapters.items()
        }
    }, indent=2))
    return 0


def cmd_presets(args) -> int:
    """List available domain presets or emit one as a profile JSON."""
    from lithos.presets import get_preset, list_presets

    if args.domain and args.name:
        profile = get_preset(args.domain, args.name)
        if profile is None:
            logger.error(f"Unknown preset: {args.domain}/{args.name}")
            return 1
        payload = profile.to_dict()
        if args.out:
            Path(args.out).write_text(json.dumps(payload, indent=2))
            logger.info(f"Wrote preset to {args.out}")
        else:
            print(json.dumps(payload, indent=2))
        return 0

    listing = list_presets()
    if args.json:
        print(json.dumps(listing, indent=2))
    else:
        for domain, names in sorted(listing.items()):
            print(f"{domain}: {', '.join(names)}")
    return 0


def load_run_manifest(path: Path):
    from lithos.reproducibility import load_run_manifest
    return load_run_manifest(path)


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="lithos",
        description=f"LITHOS v{VERSION} - Literature Retrieval and Source Validation for Scoping Reviews",
    )
    parser.add_argument("--version", action="version", version=f"LITHOS {VERSION}")
    parser.add_argument("--about", action="store_true", help="Show author and license information")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="JSON output for machine parsing")
    parser.add_argument("--config", type=Path, help="Configuration file (YAML/JSON)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")

    subparsers = parser.add_subparsers(dest="command", required=False)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for literature across multiple sources")
    search_parser.add_argument("--query", "-q", action="append", help="Search query (repeatable)")
    search_parser.add_argument("--queries-file", help="File with one query per line")
    search_parser.add_argument("--profile", help="Search profile file (JSON)")
    search_parser.add_argument("--limit", type=int, default=100, help="Max records per source per query")
    search_parser.add_argument("--from-year", type=int, help="Filter from year (inclusive)")
    search_parser.add_argument("--to-year", type=int, help="Filter to year (inclusive)")
    search_parser.add_argument("--type", help="Publication type filter")
    search_parser.add_argument("--open-access", action="store_true", help="Open access only")
    search_parser.add_argument("--sources", nargs="+", help="Specific sources to search")
    search_parser.add_argument("--validate", action="store_true", default=True, help="Validate against Crossref")
    search_parser.add_argument("--no-validate", dest="validate", action="store_false", help="Skip validation")
    search_parser.add_argument("--predatory-list", help="Path to predatory venue list")
    search_parser.add_argument("--analytics", action="store_true", help="Generate analytics")
    search_parser.add_argument("--out", "-o", default="results", help="Output directory")

    # Snowball command
    snowball_parser = subparsers.add_parser("snowball", help="Citation chasing (forward/backward)")
    snowball_parser.add_argument("--input", "-i", required=True, help="Input records JSON file")
    snowball_parser.add_argument("--backward", action="store_true", default=True, help="Backward snowballing (references)")
    snowball_parser.add_argument("--forward", action="store_true", default=True, help="Forward snowballing (citations)")
    snowball_parser.add_argument("--max-refs", type=int, default=50, help="Max references per record")
    snowball_parser.add_argument("--max-citations", type=int, default=50, help="Max citations per record")
    snowball_parser.add_argument("--levels", type=int, default=1, help="Citation-chasing depth (levels)")
    snowball_parser.add_argument("--out", "-o", default="snowball_results", help="Output directory")

    # Dedupe command
    dedupe_parser = subparsers.add_parser("dedupe", help="Deduplicate records")
    dedupe_parser.add_argument("--input", "-i", required=True, help="Input records JSON file")
    dedupe_parser.add_argument("--out", "-o", default="dedupe_results", help="Output directory")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate records against Crossref")
    validate_parser.add_argument("--input", "-i", required=True, help="Input records JSON file")
    validate_parser.add_argument("--predatory-list", help="Path to predatory venue list")
    validate_parser.add_argument("--out", "-o", default="validated_results", help="Output directory")

    # Screen command
    screen_parser = subparsers.add_parser("screen", help="Apply screening rules")
    screen_parser.add_argument("--input", "-i", required=True, help="Input records JSON file")
    screen_parser.add_argument("--rules", help="Screening rules JSON file")
    screen_parser.add_argument("--include-keywords", nargs="+", help="Include keywords")
    screen_parser.add_argument("--exclude-keywords", nargs="+", help="Exclude keywords")
    screen_parser.add_argument("--threshold", type=float, default=0.5, help="Keyword score threshold")
    screen_parser.add_argument("--tfidf-query", help="TF-IDF query for relevance ranking")
    screen_parser.add_argument("--tfidf-top-k", type=int, default=50, help="Top K for TF-IDF auto-include")
    screen_parser.add_argument("--ranker", choices=["tfidf", "semantic"], default="tfidf", help="Ranker for --tfidf-query (TF-IDF/BM25 default; semantic needs lithos[semantic])")
    screen_parser.add_argument("--model", help="Sentence-transformers model name for --ranker semantic")
    screen_parser.add_argument("--full-text-dir", help="Directory from 'lithos fetch-text' to screen on full text")
    screen_parser.add_argument("--two-reviewer-export", action="store_true", help="Export two-reviewer format")
    screen_parser.add_argument("--reviewers", nargs="+", help="Reviewer names (two for agreement stats)")
    screen_parser.add_argument("--export-forms", action="store_true", help="Write per-reviewer CSV screening forms")
    screen_parser.add_argument("--import-decisions", action="append", metavar="NAME=file.csv", help="Import filled reviewer decisions (repeatable)")
    screen_parser.add_argument("--agreement", action="store_true", help="Compute Cohen's kappa + conflict list")
    screen_parser.add_argument("--out", "-o", default="screened_results", help="Output directory")

    # Fetch-text command
    ft_parser = subparsers.add_parser("fetch-text", help="Fetch open-access full texts (Europe PMC / Unpaywall)")
    ft_parser.add_argument("--input", "-i", required=True, help="Input records JSON file")
    ft_parser.add_argument("--out", "-o", default="fulltext", help="Output directory (cache + texts + index)")
    ft_parser.add_argument("--limit", type=int, help="Max records to attempt")
    ft_parser.add_argument("--force", action="store_true", help="Ignore cache and refetch")
    ft_parser.add_argument("--no-unpaywall", action="store_true", help="Do not query Unpaywall (Europe PMC only)")

    # Dashboard command
    dash_parser = subparsers.add_parser("dashboard", help="Generate a self-contained offline HTML screening dashboard")
    dash_parser.add_argument("--input", "-i", required=True, help="Input records JSON file")
    dash_parser.add_argument("--rules", help="Screening rules JSON (used for suggested reasons)")
    dash_parser.add_argument("--reviewer", default="", help="Default reviewer name")
    dash_parser.add_argument("--out", "-o", default="screening_dashboard.html", help="Output HTML file")
    dash_parser.add_argument("--dataset-id", default="", help="Stable id for browser-local decisions (default: from input path)")

    # Benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Run measured screening validation on the bundled synthetic benchmark")
    bench_parser.add_argument("--input", "-i", help="Benchmark JSON file (default: bundled synthetic benchmark)")
    bench_parser.add_argument("--top-k", type=int, help="Top-k for BM25 auto-include (default: number of relevant records)")
    bench_parser.add_argument("--out", "-o", default="benchmark", help="Output directory (metrics JSON + markdown report)")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export records to various formats")
    export_parser.add_argument("--input", "-i", required=True, help="Input records JSON file")
    export_parser.add_argument("--format", "-f", required=True, choices=[f.value for f in ExportFormat], help="Export format")
    export_parser.add_argument("--out", "-o", required=True, help="Output file path")
    export_parser.add_argument("--screened-only", action="store_true", help="Only export screened records")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate reports")
    report_parser.add_argument("--input", "-i", required=True, help="Input records JSON file")
    report_parser.add_argument("--manifest", help="Run manifest JSON file")
    report_parser.add_argument("--prisma", action="store_true", help="Generate PRISMA flow diagram")
    report_parser.add_argument("--png", action="store_true", help="Also generate PNG (requires matplotlib)")
    report_parser.add_argument("--search-report", action="store_true", help="Generate search report")
    report_parser.add_argument("--docx", action="store_true", help="Also generate DOCX (requires python-docx)")
    report_parser.add_argument("--evidence-maps", action="store_true", help="Generate evidence maps")
    report_parser.add_argument("--analytics", action="store_true", help="Generate analytics")
    report_parser.add_argument("--out", "-o", default="reports", help="Output directory")

    # Config command
    config_parser = subparsers.add_parser("config", help="Show current configuration")

    # Presets command
    presets_parser = subparsers.add_parser("presets", help="List or emit domain presets")
    presets_parser.add_argument("--domain", help="Domain (civil, geotechnical, structural, environmental, science)")
    presets_parser.add_argument("--name", help="Preset name within the domain")
    presets_parser.add_argument("--out", "-o", help="Write the preset profile JSON to this path")

    args = parser.parse_args()

    if getattr(args, "about", False):
        from lithos import __author__, __license__, __version__
        print(f"LITHOS {__version__}")
        print(f"Author: {__author__}")
        print(f"License: {__license__}")
        return 0

    if not args.command:
        parser.print_help()
        return 1

    setup_logging(args.verbose, args.json)

    if args.dry_run:
        logger.info(f"DRY RUN: Would execute '{args.command}' with args: {vars(args)}")
        return 0

    # Dispatch
    commands = {
        "search": cmd_search,
        "snowball": cmd_snowball,
        "dedupe": cmd_dedupe,
        "validate": cmd_validate,
        "screen": cmd_screen,
        "fetch-text": cmd_fetch_text,
        "dashboard": cmd_dashboard,
        "benchmark": cmd_benchmark,
        "export": cmd_export,
        "report": cmd_report,
        "config": cmd_config,
        "presets": cmd_presets,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())