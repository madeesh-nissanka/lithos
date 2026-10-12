# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Open-access full-text retrieval for LITHOS.

Finds legally open-access copies of records (Europe PMC fullTextXML for
PMC-indexed articles, Unpaywall OA locations elsewhere), fetches them politely
through the shared HTTP client, extracts plain text with the standard library
only (XML/HTML always; PDF best-effort), caches everything on disk, and writes
a full-text index that the screen command can consume.

No scraping of paywalled content: a record is fetched only when an OA copy is
declared open by Unpaywall metadata or hosted by Europe PMC.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import zlib
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

from lithos.http import HTTPClient, RateLimiter, RetryPolicy
from lithos._version import VERSION

logger = logging.getLogger(__name__)

EUROPE_PMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC/{pmcid}/fullTextXML"
NCBI_PMC_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={pmcid_num}&retmode=xml"


@dataclass
class OAlocation:
    """An open-access location for a record."""
    url: str
    kind: str = "html"  # html | pdf | xml
    license: str = ""
    source: str = ""  # europe_pmc | unpaywall


@dataclass
class FullTextDoc:
    """Extracted full text for one record."""
    record_id: str
    url: str
    kind: str
    license: str
    source: str
    text: str
    chars: int
    ok: bool
    error: str = ""
    fetched_at: str = ""

    def to_meta_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "url": self.url,
            "kind": self.kind,
            "license": self.license,
            "source": self.source,
            "chars": self.chars,
            "ok": self.ok,
            "error": self.error,
            "fetched_at": self.fetched_at,
        }


class _TextExtractor(HTMLParser):
    """Standard-library HTML to plain-text extraction (skips script/style)."""

    SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """Extract readable plain text from HTML using the standard library."""
    extractor = _TextExtractor()
    extractor.feed(html)
    return _collapse(" ".join(extractor.parts))


def xml_to_text(xml: str) -> str:
    """Extract text nodes from fullTextXML / JATS-style XML."""
    try:
        root = ElementTree.fromstring(xml.encode("utf-8", errors="replace"))
    except ElementTree.ParseError as e:
        logger.debug(f"XML parse failed: {e}")
        return ""
    chunks: list[str] = []
    for elem in root.iter():
        if elem.tag.endswith(("title", "abstract", "sec")):
            chunks.append("\n")
        if elem.text and elem.text.strip():
            chunks.append(elem.text.strip())
    return _collapse(" ".join(chunks))


def _collapse(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


_PDF_STREAM = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
_PDF_SHOW = re.compile(rb"\((?:\\.|[^\\()])*\)|\bTJ\b|\bTj\b")
_PDF_STR = re.compile(rb"\((?:\\.|[^\\()])*\)")


def _pdf_unescape(raw: bytes) -> str:
    out = bytearray()
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == 0x5C and i + 1 < len(raw):
            n = raw[i + 1:i + 2]
            if n in (rb"n",):
                out += b"\n"
            elif n in (rb"r",):
                out += b"\r"
            elif n in (rb"t",):
                out += b"\t"
            elif n in (rb"b",):
                out += b"\b"
            elif n in (rb"f",):
                out += b"\f"
            elif n in (rb"\(", rb"\)", rb"\\"):
                out += n
            elif 0x30 <= n[0] <= 0x37:
                oct_digits = n
                j = i + 2
                while j < len(raw) and len(oct_digits) < 3 and 0x30 <= raw[j] <= 0x37:
                    oct_digits += raw[j:j + 1]
                    j += 1
                out += bytes([int(oct_digits, 8) & 0xFF])
                i = j
                continue
            else:
                out += n
            i += 2
        else:
            out.append(c)
            i += 1
    return out.decode("latin-1", errors="replace")


def pdf_to_text(data: bytes) -> str:
    """Best-effort standard-library PDF text extraction.

    Decompresses FlateDecode streams and pulls literal strings from Tj/TJ
    show-text operators. Handles simple text PDFs only; scanned images or
    exotic encodings return '' and are reported as unextractable.
    """
    if not data.startswith(b"%PDF"):
        return ""
    pieces: list[str] = []
    for m in _PDF_STREAM.finditer(data):
        stream = m.group(1)
        try:
            stream = zlib.decompress(stream)
        except zlib.error:
            pass
        if b"BT" not in stream and b"Tj" not in stream and b"TJ" not in stream:
            continue
        for tm in re.finditer(rb"BT(.*?)ET", stream, re.DOTALL):
            block = tm.group(1)
            for sm in _PDF_STR.finditer(block):
                pieces.append(_pdf_unescape(sm.group(0)[1:-1]))
            pieces.append("\n")
    text = _collapse(" ".join(p for p in pieces if p))
    return text if len(text) >= 50 else ""


def find_oa_locations(
    record,
    unpaywall_adapter=None,
) -> list[OAlocation]:
    """Collect declared open-access locations for a record (Europe PMC first)."""
    locations: list[OAlocation] = []
    seen: set[str] = set()

    def add(loc: OAlocation) -> None:
        if loc.url and loc.url not in seen:
            seen.add(loc.url)
            locations.append(loc)

    if getattr(record, "pmcid", None):
        add(OAlocation(
            url=EUROPE_PMC_FULLTEXT.format(pmcid=record.pmcid),
            kind="xml", source="europe_pmc", license="PMC-OA",
        ))
        add(OAlocation(
            url=NCBI_PMC_EFETCH.format(pmcid_num=record.pmcid.upper().replace("PMC", "")),
            kind="xml", source="ncbi_pmc", license="PMC-OA",
        ))
    unpay = (record.crossref_data or {}).get("unpaywall", {}) if isinstance(record.crossref_data, dict) else {}
    best = unpay.get("best_oa_url")
    if best:
        add(OAlocation(url=best, kind="pdf" if best.endswith(".pdf") else "html",
                       license=unpay.get("best_oa_license") or "", source="unpaywall"))
    for url in unpay.get("all_oa_urls", [])[:3]:
        add(OAlocation(url=url, kind="pdf" if url.endswith(".pdf") else "html", source="unpaywall"))
    if not unpay.get("best_oa_url") and unpaywall_adapter is not None and record.doi:
        status = unpaywall_adapter.check_oa_status(record.doi)
        if status.get("is_oa"):
            best_oa = status.get("best_oa_location") or {}
            url = best_oa.get("url_for_pdf") or best_oa.get("url")
            if url:
                add(OAlocation(url=url, kind="pdf" if url.endswith(".pdf") else "html",
                               license=best_oa.get("license") or "", source="unpaywall"))
    return locations


class FullTextFetcher:
    """Polite, cached OA full-text fetcher."""

    def __init__(
        self,
        cache_dir: Path,
        email: Optional[str] = None,
        requests_per_second: float = 1.0,
        timeout: int = 30,
        force: bool = False,
        client: Optional[HTTPClient] = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.force = force
        self.email = email
        if client is not None:
            self.client = client
        else:
            self.client = HTTPClient(
                RateLimiter(requests_per_second=requests_per_second, burst=1),
                RetryPolicy(max_attempts=3, base_delay=1.0),
                None,
                "lithos-fulltext",
                VERSION,
                timeout,
            )

    def _cache_path(self, url: str) -> Path:
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.json"

    def _load_cache(self, url: str) -> Optional[dict]:
        path = self._cache_path(url)
        if path.exists() and not self.force:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _store_cache(self, url: str, doc: dict) -> None:
        self._cache_path(url).write_text(json.dumps(doc, indent=2), encoding="utf-8")

    @staticmethod
    def _extract(content: bytes, url: str) -> tuple[str, str]:
        """Return (kind, text) from raw content bytes."""
        head = content[:800].lstrip().lower()
        if content[:5] == b"%PDF-" or url.lower().endswith(".pdf"):
            return "pdf", pdf_to_text(content)
        if head.startswith((b"<?xml", b"<article", b"<oax", b"<pmc-articleset")) or b"fulltext" in content[:2000].lower():
            try:
                return "xml", xml_to_text(content.decode("utf-8", errors="replace"))
            except Exception:
                pass
        return "html", html_to_text(content.decode("utf-8", errors="replace"))

    def fetch(self, record) -> Optional[FullTextDoc]:
        """Fetch the first working OA full text for a record. None if no OA copy."""
        from datetime import datetime, timezone

        for loc in find_oa_locations(record):
            cached = self._load_cache(loc.url)
            if cached is not None and cached.get("ok"):
                return FullTextDoc(
                    record_id=record.id, url=loc.url, kind=cached.get("kind", loc.kind),
                    license=cached.get("license", loc.license), source=loc.source,
                    text=cached.get("text", ""), chars=cached.get("chars", 0),
                    ok=cached.get("ok", True), error=cached.get("error", ""),
                    fetched_at=cached.get("fetched_at", "") + " (cache)",
                )
            try:
                content = self.client.get_bytes(loc.url)
            except Exception as e:
                logger.debug(f"fulltext fetch failed {loc.url}: {e}")
                continue
            kind, text = self._extract(content, loc.url)
            ok = len(text) >= 200
            doc = FullTextDoc(
                record_id=record.id, url=loc.url, kind=kind, license=loc.license,
                source=loc.source, text=text, chars=len(text), ok=ok,
                error="" if ok else "no_extractable_text",
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )
            self._store_cache(loc.url, {**doc.to_meta_dict(), "text": doc.text})
            if doc.ok:
                return doc
        return None


def fetch_full_texts(
    records: list,
    out_dir: Path,
    email: Optional[str] = None,
    unpaywall_adapter=None,
    force: bool = False,
    client: Optional[HTTPClient] = None,
) -> tuple[dict, list[dict]]:
    """Fetch and write OA full texts for records.

    Returns (index, results) where index maps record_id -> text file path and
    results are per-record metadata dicts. Writes <out_dir>/texts/*.txt and
    <out_dir>/fulltext_index.json.
    """
    out_dir = Path(out_dir)
    texts_dir = out_dir / "texts"
    texts_dir.mkdir(parents=True, exist_ok=True)
    fetcher = FullTextFetcher(out_dir / "cache", email=email, force=force, client=client)

    index: dict[str, str] = {}
    results: list[dict] = []
    for record in records:
        doc = fetcher.fetch(record)
        if doc is None:
            results.append({"record_id": record.id, "ok": False, "error": "no_oa_location"})
            continue
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", record.id)[:80]
        fname = texts_dir / f"{safe_id}.txt"
        fname.write_text(doc.text, encoding="utf-8")
        index[record.id] = str(fname.relative_to(out_dir))
        results.append(doc.to_meta_dict())

    (out_dir / "fulltext_index.json").write_text(
        json.dumps({"entries": index, "results": results}, indent=2), encoding="utf-8"
    )
    return index, results


def load_full_text(record_id: str, out_dir: Path, index: Optional[dict] = None) -> str:
    """Load cached full text for a record from a fetch-text output dir."""
    out_dir = Path(out_dir)
    if index is None:
        idx_path = out_dir / "fulltext_index.json"
        if not idx_path.exists():
            return ""
        index = json.loads(idx_path.read_text(encoding="utf-8")).get("entries", {})
    rel = index.get(record_id)
    if not rel:
        return ""
    path = out_dir / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")
