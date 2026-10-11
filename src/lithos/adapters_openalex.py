# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
OpenAlex adapter for LITHOS.
"""
from __future__ import annotations
import logging
import urllib.parse
from typing import Any, Optional

from lithos.adapters import BaseAdapter, AdapterConfig
from lithos.models import Record, SearchQuery, SearchResult

logger = logging.getLogger(__name__)

OPEN_ALEX_BASE = "https://api.openalex.org/works"
DOI_URL_PREFIX = "https://doi.org/"


def rebuild_abstract(inverted_index: Optional[dict]) -> str:
    """Rebuild abstract from OpenAlex inverted index."""
    if not inverted_index:
        return ""
    pos = {}
    for word, idxs in inverted_index.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[k] for k in sorted(pos))


def extract_authors(authorships: list[dict]) -> list[str]:
    """Extract author names from authorships."""
    return [a["author"]["display_name"] for a in authorships if a.get("author", {}).get("display_name")]


def extract_venue(primary_location: Optional[dict]) -> Optional[str]:
    """Extract venue name from primary location."""
    if not primary_location:
        return None
    source = primary_location.get("source")
    if source and source.get("display_name"):
        return source["display_name"]
    return None


def extract_publication_type(work_type: Optional[str]) -> Optional[str]:
    """Map OpenAlex type to publication type."""
    if not work_type:
        return None
    type_map = {
        "journal-article": "journal-article",
        "preprint": "preprint",
        "conference": "conference-paper",
        "book": "book",
        "book-chapter": "book-chapter",
        "dissertation": "dissertation",
        "report": "report",
        "dataset": "dataset",
        "other": "other",
    }
    return type_map.get(work_type, work_type)


class OpenAlexAdapter(BaseAdapter):
    """OpenAlex API adapter."""

    name = "openalex"
    display_name = "OpenAlex"
    requires_api_key = False
    supports_boolean = True
    supports_year_filter = True

    def __init__(self, config: Optional[AdapterConfig] = None):
        super().__init__(config)

    def translate_query(self, query: SearchQuery) -> str:
        """Translate structured query to OpenAlex search syntax."""
        if query.boolean_query:
            return query.boolean_query
        return query.original

    def search(self, query: SearchQuery, limit: int = 100) -> SearchResult:
        """Search OpenAlex for works matching the query."""
        import time
        start_time = time.time()

        translated = self.translate_query(query)
        if not translated:
            return SearchResult(query=query, source=self.name, errors=["Empty query"])

        params = {
            "search": translated,
            "per-page": min(limit, 200),
            "select": "id,doi,title,publication_year,authorships,primary_location,cited_by_count,type,abstract_inverted_index,referenced_works,keywords",
        }

        filters = []
        if query.filters.get("from_year"):
            filters.append(f"from_publication_date:{query.filters['from_year']}-01-01")
        if query.filters.get("to_year"):
            filters.append(f"to_publication_date:{query.filters['to_year']}-12-31")
        if query.filters.get("type"):
            filters.append(f"type:{query.filters['type']}")
        if query.filters.get("open_access"):
            filters.append("open_access.is_oa:true")

        if filters:
            params["filter"] = ",".join(filters)

        if self.config.polite_email:
            params["mailto"] = self.config.polite_email

        url = f"{OPEN_ALEX_BASE}?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

        try:
            data = self.http.get_json(url)
            results = []
            for w in data.get("results", []):
                record = self._parse_work(w, [translated])
                if record:
                    results.append(record)

            return SearchResult(
                query=query,
                records=results,
                total_hits=data.get("meta", {}).get("count", len(results)),
                source=self.name,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"OpenAlex search failed: {e}")
            return SearchResult(query=query, source=self.name, errors=[str(e)], duration_seconds=time.time() - start_time)

    def fetch_by_id(self, identifier: str, id_type: str = "doi") -> Optional[Record]:
        """Fetch a single work by DOI or OpenAlex ID."""
        if id_type == "doi":
            identifier = self.normalize_doi(identifier)
            url = f"{OPEN_ALEX_BASE}/doi:{identifier}"
        elif id_type == "openalex":
            url = f"{OPEN_ALEX_BASE}/{identifier}"
        else:
            logger.warning(f"Unsupported ID type for OpenAlex: {id_type}")
            return None

        try:
            data = self.http.get_json(url)
            return self._parse_work(data, [])
        except Exception as e:
            logger.error(f"OpenAlex fetch_by_id failed: {e}")
            return None

    def _parse_work(self, w: dict, query_hits: list[str]) -> Optional[Record]:
        """Parse OpenAlex work into Record."""
        doi = w.get("doi")
        if doi and doi.startswith(DOI_URL_PREFIX):
            doi = doi[len(DOI_URL_PREFIX):]

        authors = extract_authors(w.get("authorships", []))
        venue = extract_venue(w.get("primary_location"))
        pub_type = extract_publication_type(w.get("type"))

        # Extract keywords
        keywords = []
        for kw in w.get("keywords", []):
            if kw.get("display_name"):
                keywords.append(kw["display_name"])

        # Extract referenced works (DOIs)
        referenced = []
        for ref in w.get("referenced_works", []):
            if ref.startswith(DOI_URL_PREFIX):
                referenced.append(ref[len(DOI_URL_PREFIX):])

        record = Record(
            openalex_id=w.get("id"),
            doi=doi,
            title=w.get("title", "") or "",
            year=w.get("publication_year"),
            authors=authors,
            venue=venue,
            abstract=rebuild_abstract(w.get("abstract_inverted_index")),
            keywords=keywords,
            publication_type=pub_type,
            cited_by=w.get("cited_by_count"),
            referenced_works=referenced,
            source=self.name,
            query_hits=query_hits,
            retrieved_by=self.name,
        )
        return record