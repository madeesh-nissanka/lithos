# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
DOAJ adapter for LITHOS.
"""
from __future__ import annotations
import logging
import urllib.parse
from typing import Any, Optional

from lithos.adapters import BaseAdapter, AdapterConfig
from lithos.models import Record, SearchQuery, SearchResult

logger = logging.getLogger(__name__)

DOAJ_BASE = "https://doaj.org/api/v2"
DOAJ_SEARCH = f"{DOAJ_BASE}/search/articles"


class DOAJAdapter(BaseAdapter):
    """DOAJ (Directory of Open Access Journals) adapter."""

    name = "doaj"
    display_name = "DOAJ"
    requires_api_key = False
    supports_boolean = True
    supports_year_filter = True

    def translate_query(self, query: SearchQuery) -> str:
        if query.source_translations.get(self.name):
            return query.source_translations[self.name]
        if query.boolean_query:
            return query.boolean_query
        return query.original

    def search(self, query: SearchQuery, limit: int = 100) -> SearchResult:
        import time
        start_time = time.time()

        translated = self.translate_query(query)
        if not translated:
            return SearchResult(query=query, source=self.name, errors=["Empty query"])

        params = {
            "q": translated,
            "page": 1,
            "pageSize": min(limit, 100),
        }

        if query.filters.get("from_year"):
            params["fromYear"] = query.filters["from_year"]
        if query.filters.get("to_year"):
            params["toYear"] = query.filters["to_year"]

        url = f"{DOAJ_SEARCH}?" + urllib.parse.urlencode(params)

        try:
            data = self.http.get_json(url)
            results = []
            for article in data.get("results", []):
                record = self._parse_article(article, [translated])
                if record:
                    results.append(record)

            return SearchResult(
                query=query,
                records=results,
                total_hits=data.get("total", len(results)),
                source=self.name,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"DOAJ search failed: {e}")
            return SearchResult(query=query, source=self.name, errors=[str(e)], duration_seconds=time.time() - start_time)

    def fetch_by_id(self, identifier: str, id_type: str = "doi") -> Optional[Record]:
        """Fetch an article by DOI."""
        if id_type != "doi":
            return None

        url = f"{DOAJ_BASE}/search/articles/doi:{urllib.parse.quote(identifier)}"
        try:
            data = self.http.get_json(url)
            results = data.get("results", [])
            if results:
                return self._parse_article(results[0], [])
        except Exception as e:
            logger.error(f"DOAJ fetch_by_id failed: {e}")
        return None

    def _parse_article(self, article: dict, query_hits: list[str]) -> Optional[Record]:
        """Parse DOAJ article into Record."""
        try:
            bibjson = article.get("bibjson", {})
            doi = bibjson.get("doi")
            title = bibjson.get("title", "") or ""
            year = bibjson.get("year")
            if year is not None:
                try:
                    year = int(year)
                except (TypeError, ValueError):
                    year = None
            abstract = bibjson.get("abstract", "") or ""

            authors = []
            for a in bibjson.get("author", []):
                name = a.get("name")
                if name:
                    authors.append(name)

            venue = bibjson.get("journal", {}).get("title")
            volume = bibjson.get("journal", {}).get("volume")
            issue = bibjson.get("journal", {}).get("number")
            pages = bibjson.get("start_page")
            if bibjson.get("end_page"):
                pages = f"{pages}-{bibjson['end_page']}" if pages else bibjson["end_page"]

            keywords = []
            for kw in bibjson.get("keywords", []):
                if isinstance(kw, str):
                    keywords.append(kw)
                elif isinstance(kw, dict) and kw.get("name"):
                    keywords.append(kw["name"])

            record = Record(
                doi=doi,
                title=title,
                year=year,
                authors=authors,
                venue=venue,
                volume=volume,
                issue=issue,
                pages=pages,
                abstract=abstract,
                keywords=keywords,
                publication_type="journal-article",
                source=self.name,
                query_hits=query_hits,
                retrieved_by=self.name,
            )
            return record
        except Exception as e:
            logger.warning(f"Failed to parse DOAJ article: {e}")
            return None