# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Export module for LITHOS - CSV, XLSX, JSON, RIS, BibTeX, CSL-JSON.
"""
from __future__ import annotations
import csv
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from lithos.models import Record

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"
    RIS = "ris"
    BIBTEX = "bibtex"
    CSL_JSON = "csl-json"


def export_records(
    records: list[Record],
    path: Path,
    format: ExportFormat,
    include_screened_only: bool = False,
) -> None:
    """Export records to specified format."""
    if include_screened_only:
        records = [r for r in records if r.screen_state != r.screen_state.UNSCREENED]

    if format == ExportFormat.CSV:
        _export_csv(records, path)
    elif format == ExportFormat.XLSX:
        _export_xlsx(records, path)
    elif format == ExportFormat.JSON:
        _export_json(records, path)
    elif format == ExportFormat.RIS:
        _export_ris(records, path)
    elif format == ExportFormat.BIBTEX:
        _export_bibtex(records, path)
    elif format == ExportFormat.CSL_JSON:
        _export_csl_json(records, path)
    else:
        raise ValueError(f"Unknown export format: {format}")


def _export_csv(records: list[Record], path: Path):
    """Export to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "doi", "pmid", "arxiv_id", "semantic_scholar_id", "core_id",
            "title", "year", "authors", "venue", "volume", "issue", "pages",
            "abstract", "keywords", "publication_type", "cited_by",
            "source", "query_hits", "status", "flags", "completeness_score",
            "screen_state", "screen_notes", "reviewer_decisions",
            "dedup_cluster_id", "dedup_master",
        ])
        for r in records:
            writer.writerow([
                r.id,
                r.doi or "",
                r.pmid or "",
                r.arxiv_id or "",
                r.semantic_scholar_id or "",
                r.core_id or "",
                r.title,
                r.year or "",
                "; ".join(r.authors),
                r.venue or "",
                r.volume or "",
                r.issue or "",
                r.pages or "",
                r.abstract,
                "; ".join(r.keywords),
                r.publication_type or "",
                r.cited_by or "",
                r.source,
                "; ".join(r.query_hits),
                r.status.value,
                "; ".join(r.flags),
                r.completeness_score,
                r.screen_state.value,
                r.screen_notes,
                json.dumps({k: v.value for k, v in r.reviewer_decisions.items()}),
                r.dedup_cluster_id or "",
                r.dedup_master,
            ])


_XLSX_HEADERS = [
    "id", "doi", "pmid", "arxiv_id", "semantic_scholar_id", "core_id",
    "title", "year", "authors", "venue", "volume", "issue", "pages",
    "abstract", "keywords", "publication_type", "cited_by",
    "source", "query_hits", "status", "flags", "completeness_score",
    "screen_state", "screen_notes", "reviewer_decisions",
    "dedup_cluster_id", "dedup_master",
]


def _xlsx_cell_text(value: Any) -> str:
    """Coerce a value to a control-char-free string for OOXML inline strings."""
    text = "" if value is None else str(value)
    return "".join(ch for ch in text if ch >= " " or ch in "\t\n\r")


def _xlsx_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _xlsx_col_ref(index: int) -> str:
    """0-based column index -> spreadsheet column letters (A, B, ..., AA)."""
    ref = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        ref = chr(65 + rem) + ref
    return ref


def _xlsx_row_xml(row_number: int, values: list[str]) -> str:
    cells = []
    for col, value in enumerate(values):
        ref = f"{_xlsx_col_ref(col)}{row_number}"
        cells.append(
            f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">'
            f"{_xlsx_escape(value)}</t></is></c>"
        )
    return f'<row r="{row_number}">{"".join(cells)}</row>'


def _export_xlsx(records: list[Record], path: Path):
    """Export to XLSX using a dependency-free OOXML (zipfile) writer."""
    import zipfile

    path.parent.mkdir(parents=True, exist_ok=True)

    rows = [_xlsx_row_xml(1, [str(h) for h in _XLSX_HEADERS])]
    for r in records:
        values = [
            r.id,
            r.doi or "",
            r.pmid or "",
            r.arxiv_id or "",
            r.semantic_scholar_id or "",
            r.core_id or "",
            r.title,
            r.year if r.year is not None else "",
            "; ".join(r.authors),
            r.venue or "",
            r.volume or "",
            r.issue or "",
            r.pages or "",
            r.abstract,
            "; ".join(r.keywords),
            r.publication_type or "",
            r.cited_by if r.cited_by is not None else "",
            r.source,
            "; ".join(r.query_hits),
            r.status.value,
            "; ".join(r.flags),
            r.completeness_score,
            r.screen_state.value,
            r.screen_notes,
            json.dumps({k: v.value for k, v in r.reviewer_decisions.items()}),
            r.dedup_cluster_id or "",
            r.dedup_master,
        ]
        rows.append(_xlsx_row_xml(len(rows) + 1, [_xlsx_cell_text(v) for v in values]))

    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(rows) + "</sheetData></worksheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Records" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)


def _export_json(records: list[Record], path: Path):
    """Export to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [r.to_dict() for r in records]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _export_ris(records: list[Record], path: Path):
    """Export to RIS format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in records:
        lines.append("TY  - JOUR")
        if r.doi:
            lines.append(f"DO  - {r.doi}")
        if r.title:
            lines.append(f"TI  - {r.title}")
        if r.authors:
            for a in r.authors:
                lines.append(f"AU  - {a}")
        if r.year:
            lines.append(f"PY  - {r.year}")
        if r.venue:
            lines.append(f"JO  - {r.venue}")
        if r.volume:
            lines.append(f"VL  - {r.volume}")
        if r.issue:
            lines.append(f"IS  - {r.issue}")
        if r.pages:
            lines.append(f"SP  - {r.pages.split('-')[0] if '-' in r.pages else r.pages}")
            if '-' in r.pages:
                lines.append(f"EP  - {r.pages.split('-')[1]}")
        if r.abstract:
            # RIS abstract can be multi-line
            for line in r.abstract.split('\n'):
                lines.append(f"AB  - {line}")
        if r.keywords:
            for kw in r.keywords:
                lines.append(f"KW  - {kw}")
        lines.append("ER  - ")
        lines.append("")

    path.write_text("\n".join(lines))


def _export_bibtex(records: list[Record], path: Path):
    """Export to BibTeX format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in records:
        # Generate citation key
        first_author = first_author_surname(r.authors) or "Anon"
        year = r.year or "XXXX"
        title_word = r.title.split()[0] if r.title else "Untitled"
        key = f"{first_author}{year}{title_word}".replace(" ", "").replace(":", "").replace(",", "")[:50]

        lines.append(f"@article{{{key},")
        if r.doi:
            lines.append(f"  doi = {{{r.doi}}},")
        if r.title:
            lines.append(f"  title = {{{r.title}}},")
        if r.authors:
            lines.append(f"  author = {{{' and '.join(r.authors)}}},")
        if r.year:
            lines.append(f"  year = {{{r.year}}},")
        if r.venue:
            lines.append(f"  journal = {{{r.venue}}},")
        if r.volume:
            lines.append(f"  volume = {{{r.volume}}},")
        if r.issue:
            lines.append(f"  number = {{{r.issue}}},")
        if r.pages:
            lines.append(f"  pages = {{{r.pages}}},")
        if r.abstract:
            lines.append(f"  abstract = {{{r.abstract}}},")
        if r.keywords:
            lines.append(f"  keywords = {{{', '.join(r.keywords)}}},")
        lines.append("}")
        lines.append("")

    path.write_text("\n".join(lines))


def _export_csl_json(records: list[Record], path: Path):
    """Export to CSL-JSON format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    csl_items = []
    for r in records:
        authors = []
        for a in r.authors:
            if "," in a:
                family, given = a.split(",", 1)
                authors.append({"family": family.strip(), "given": given.strip()})
            else:
                parts = a.split()
                if len(parts) >= 2:
                    authors.append({"family": parts[-1], "given": " ".join(parts[:-1])})
                else:
                    authors.append({"family": a})

        item = {
            "type": _map_pub_type(r.publication_type),
            "title": r.title,
            "author": authors,
            "issued": {"date-parts": [[r.year]]} if r.year else None,
            "container-title": r.venue,
            "volume": r.volume,
            "issue": r.issue,
            "page": r.pages,
            "DOI": r.doi,
            "PMID": r.pmid,
            "arXiv": r.arxiv_id,
            "abstract": r.abstract,
            "keyword": r.keywords,
            "citation-count": r.cited_by,
        }
        # Remove None values
        item = {k: v for k, v in item.items() if v is not None}
        csl_items.append(item)

    path.write_text(json.dumps(csl_items, indent=2, ensure_ascii=False))


def _map_pub_type(pub_type: Optional[str]) -> str:
    """Map publication type to CSL type."""
    if not pub_type:
        return "article-journal"
    mapping = {
        "journal-article": "article-journal",
        "preprint": "preprint",
        "conference-paper": "paper-conference",
        "conference": "paper-conference",
        "book": "book",
        "book-chapter": "chapter",
        "dissertation": "thesis",
        "report": "report",
        "dataset": "dataset",
    }
    return mapping.get(pub_type, "article-journal")


def first_author_surname(authors: list[str]) -> Optional[str]:
    if not authors:
        return None
    name = authors[0].strip()
    if "," in name:
        return name.split(",")[0].strip()
    parts = name.split()
    return parts[-1] if parts else None