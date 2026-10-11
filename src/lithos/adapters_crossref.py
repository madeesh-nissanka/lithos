# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Crossref adapter for DOI validation and metadata retrieval.
"""
from __future__ import annotations
import logging
import urllib.parse
from typing import Any, Optional

from lithos.adapters import BaseAdapter, AdapterConfig
from lithos.models import Record, SearchQuery, SearchResult

logger = logging.getLogger(__name__)

CROSSREF_BASE = "https://api.crossref.org/works"
DOI_URL_PREFIX = "https://doi.org/"


class CrossrefAdapter(BaseAdapter):
    """Crossref API adapter for validation and metadata."""

    name = "crossref"
    display_name = "Crossref"
    requires_api_key = False
    supports_boolean = True
    supports_year_filter = True

    def __init__(self, config: Optional[AdapterConfig] = None):
        super().__init__(config)

    def translate_query(self, query: SearchQuery) -> str:
        return query.original

    def search(self, query: SearchQuery, limit: int = 100) -> SearchResult:
        """Search Crossref works by bibliographic query string."""
        import time
        start_time = time.time()
        translated = self.translate_query(query)
        if not translated:
            return SearchResult(query=query, source=self.name, errors=["Empty query"])

        params = {
            "query": translated,
            "rows": min(limit, 1000),
            "select": "DOI,title,issued,author,container-title,type,abstract,reference,volume,issue,page",
        }
        filters = []
        if query.filters.get("from_year"):
            filters.append(f"from-pub-date:{query.filters['from_year']}-01-01")
        if query.filters.get("to_year"):
            filters.append(f"until-pub-date:{query.filters['to_year']}-12-31")
        if query.filters.get("type"):
            filters.append(f"type:{query.filters['type']}")
        if filters:
            params["filter"] = ",".join(filters)
        if self.config.polite_email:
            params["mailto"] = self.config.polite_email

        url = f"{CROSSREF_BASE}?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        try:
            data = self.http.get_json(url)
            message = data.get("message", {})
            results = []
            for item in message.get("items", []):
                rec = self._parse_crossref(item)
                rec.query_hits.append(translated)
                results.append(rec)
            return SearchResult(
                query=query,
                records=results,
                total_hits=message.get("total-results", len(results)),
                source=self.name,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"Crossref search failed: {e}")
            return SearchResult(query=query, source=self.name, errors=[str(e)], duration_seconds=time.time() - start_time)

    def fetch_by_id(self, identifier: str, id_type: str = "doi") -> Optional[Record]:
        """Fetch metadata for a DOI."""
        if id_type != "doi":
            return None

        doi = self.normalize_doi(identifier)
        if not doi:
            return None

        url = f"{CROSSREF_BASE}/{urllib.parse.quote(doi)}"
        try:
            data = self.http.get_json(url)
            msg = data.get("message", {})
            return self._parse_crossref(msg)
        except Exception as e:
            logger.error(f"Crossref fetch_by_id failed for {doi}: {e}")
            return None

    def validate_doi(self, doi: str) -> dict:
        """Validate a DOI and return Crossref metadata."""
        doi = self.normalize_doi(doi)
        if not doi:
            return {"ok": False, "error": "invalid_doi"}

        url = f"{CROSSREF_BASE}/{urllib.parse.quote(doi)}"
        try:
            data = self.http.get_json(url)
            msg = data.get("message", {})
            return {"ok": True, "data": msg}
        except Exception as e:
            logger.error(f"Crossref validation failed for {doi}: {e}")
            return {"ok": False, "error": str(e)}

    def check_retraction(self, msg: dict) -> bool:
        """Check if a work has been retracted."""
        for item in msg.get("update-to", []):
            if item.get("type") in ("retraction", "withdrawal"):
                return True
        return False

    def check_correction(self, msg: dict) -> bool:
        """Check if a work has a correction."""
        for item in msg.get("update-to", []):
            if item.get("type") == "correction":
                return True
        return False

    def get_preprint_relation(self, msg: dict) -> Optional[str]:
        """Find published version DOI if this is a preprint."""
        for rel in msg.get("relation", {}).get("has-preprint", []):
            return rel.get("id", "").replace(DOI_URL_PREFIX, "")
        for rel in msg.get("relation", {}).get("is-preprint-of", []):
            return rel.get("id", "").replace(DOI_URL_PREFIX, "")
        return None

    def _parse_crossref(self, msg: dict) -> Record:
        """Parse Crossref message into Record."""
        doi = msg.get("DOI", "").lower()
        title = (msg.get("title") or [""])[0]

        authors = []
        for a in msg.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            if given and family:
                authors.append(f"{given} {family}")
            elif family:
                authors.append(family)
            elif given:
                authors.append(given)

        year = None
        issued = msg.get("issued", {})
        dp = issued.get("date-parts", [])
        if dp and dp[0]:
            year = dp[0][0]

        venue = None
        container = msg.get("container-title", [])
        if container:
            venue = container[0]

        volume = msg.get("volume")
        issue = msg.get("issue")
        pages = msg.get("page")
        pub_type = msg.get("type")

        abstract = msg.get("abstract", "")

        referenced = []
        for ref in msg.get("reference", []):
            if ref.get("DOI"):
                referenced.append(ref["DOI"].lower())

        return Record(
            doi=doi,
            title=title,
            year=year,
            authors=authors,
            venue=venue,
            volume=volume,
            issue=issue,
            pages=pages,
            publication_type=pub_type,
            abstract=abstract,
            crossref_data=msg,
            source=self.name,
            retrieved_by=self.name,
        )