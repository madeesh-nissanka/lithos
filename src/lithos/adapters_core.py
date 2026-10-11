# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
CORE adapter for LITHOS.
"""
from __future__ import annotations
import logging
import urllib.parse
from typing import Any, Optional

from lithos.adapters import BaseAdapter, AdapterConfig
from lithos.models import Record, SearchQuery, SearchResult

logger = logging.getLogger(__name__)

CORE_BASE = "https://api.core.ac.uk/v3"
CORE_SEARCH = f"{CORE_BASE}/search/works"


class COREAdapter(BaseAdapter):
    """CORE API adapter."""

    name = "core"
    display_name = "CORE"
    requires_api_key = True
    supports_boolean = True
    supports_year_filter = True

    def __init__(self, config: Optional[AdapterConfig] = None):
        super().__init__(config)
        self.api_key = config.api_key if config else None

    def _get_headers(self) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        return headers

    def translate_query(self, query: SearchQuery) -> str:
        if query.source_translations.get(self.name):
            return query.source_translations[self.name]
        if query.boolean_query:
            return query.boolean_query
        return query.original

    def search(self, query: SearchQuery, limit: int = 100) -> SearchResult:
        import time
        start_time = time.time()

        if not self.api_key:
            return SearchResult(query=query, source=self.name, errors=["CORE API key required"])

        translated = self.translate_query(query)
        if not translated:
            return SearchResult(query=query, source=self.name, errors=["Empty query"])

        params = {
            "q": translated,
            "limit": min(limit, 100),
            "scroll": "false",
        }

        if query.filters.get("from_year"):
            params["yearPublishedMin"] = query.filters["from_year"]
        if query.filters.get("to_year"):
            params["yearPublishedMax"] = query.filters["to_year"]
        if query.filters.get("open_access"):
            params["openAccess"] = "true"

        url = f"{CORE_SEARCH}?" + urllib.parse.urlencode(params)

        try:
            headers = self._get_headers()
            data = self.http.get_json(url, headers=headers)
            results = []
            for work in data.get("results", []):
                record = self._parse_work(work, [translated])
                if record:
                    results.append(record)

            return SearchResult(
                query=query,
                records=results,
                total_hits=data.get("totalHits", len(results)),
                source=self.name,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"CORE search failed: {e}")
            return SearchResult(query=query, source=self.name, errors=[str(e)], duration_seconds=time.time() - start_time)

    def fetch_by_id(self, identifier: str, id_type: str = "core") -> Optional[Record]:
        """Fetch a work by CORE ID or DOI."""
        if not self.api_key:
            return None

        if id_type == "core":
            url = f"{CORE_BASE}/works/{identifier}"
        elif id_type == "doi":
            url = f"{CORE_BASE}/works/doi/{urllib.parse.quote(identifier)}"
        else:
            logger.warning(f"Unsupported ID type for CORE: {id_type}")
            return None

        try:
            headers = self._get_headers()
            data = self.http.get_json(url, headers=headers)
            return self._parse_work(data, [])
        except Exception as e:
            logger.error(f"CORE fetch_by_id failed: {e}")
            return None

    def _parse_work(self, work: dict, query_hits: list[str]) -> Optional[Record]:
        """Parse CORE work into Record."""
        try:
            core_id = str(work.get("id", ""))
            doi = work.get("doi")
            title = work.get("title", "") or ""
            year = work.get("yearPublished")
            abstract = work.get("abstract", "") or ""

            authors = []
            for a in work.get("authors", []):
                name = a.get("name")
                if name:
                    authors.append(name)

            venue = work.get("publisher") or work.get("journal", {}).get("title")
            pub_type = work.get("type")

            keywords = []
            for kw in work.get("keywords", []):
                if isinstance(kw, str):
                    keywords.append(kw)
                elif isinstance(kw, dict) and kw.get("name"):
                    keywords.append(kw["name"])

            record = Record(
                core_id=core_id,
                doi=doi,
                title=title,
                year=year,
                authors=authors,
                venue=venue,
                abstract=abstract,
                keywords=keywords,
                publication_type=pub_type,
                source=self.name,
                query_hits=query_hits,
                retrieved_by=self.name,
            )
            return record
        except Exception as e:
            logger.warning(f"Failed to parse CORE work: {e}")
            return None

COREADapter = COREAdapter  # backward-compatible alias
