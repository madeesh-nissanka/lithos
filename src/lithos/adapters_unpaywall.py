# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Unpaywall adapter for LITHOS - finds open access versions of papers.
"""
from __future__ import annotations
import logging
import urllib.parse
from typing import Any, Optional

from lithos.adapters import BaseAdapter, AdapterConfig
from lithos.models import Record, SearchQuery, SearchResult

logger = logging.getLogger(__name__)

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"


class UnpaywallAdapter(BaseAdapter):
    """Unpaywall API adapter for finding open access versions."""

    name = "unpaywall"
    display_name = "Unpaywall"
    requires_api_key = False  # Email required for polite pool
    supports_boolean = False
    supports_year_filter = False

    def __init__(self, config: Optional[AdapterConfig] = None):
        super().__init__(config)
        self.email = config.polite_email if config else None

    def translate_query(self, query: SearchQuery) -> str:
        return ""

    def search(self, query: SearchQuery, limit: int = 100) -> SearchResult:
        """Unpaywall doesn't support search, only DOI lookup."""
        return SearchResult(query=query, source=self.name, errors=["Unpaywall does not support search"])

    def fetch_by_id(self, identifier: str, id_type: str = "doi") -> Optional[Record]:
        """Fetch open access info for a DOI."""
        if id_type != "doi":
            return None

        doi = self.normalize_doi(identifier)
        if not doi:
            return None

        params = {}
        if self.email:
            params["email"] = self.email

        url = f"{UNPAYWALL_BASE}/{urllib.parse.quote(doi)}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        try:
            data = self.http.get_json(url)
            return self._parse_unpaywall(data, doi)
        except Exception as e:
            logger.error(f"Unpaywall fetch_by_id failed for {doi}: {e}")
            return None

    def check_oa_status(self, doi: str) -> dict:
        """Check open access status for a DOI."""
        doi = self.normalize_doi(doi)
        if not doi:
            return {"is_oa": False, "error": "invalid_doi"}

        params = {}
        if self.email:
            params["email"] = self.email

        url = f"{UNPAYWALL_BASE}/{urllib.parse.quote(doi)}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        try:
            data = self.http.get_json(url)
            return {
                "is_oa": data.get("is_oa", False),
                "oa_status": data.get("oa_status"),
                "best_oa_location": data.get("best_oa_location"),
                "oa_locations": data.get("oa_locations", []),
            }
        except Exception as e:
            logger.error(f"Unpaywall check_oa_status failed for {doi}: {e}")
            return {"is_oa": False, "error": str(e)}

    def _parse_unpaywall(self, data: dict, doi: str) -> Record:
        """Parse Unpaywall response into Record with OA info."""
        best_oa = data.get("best_oa_location")
        oa_locations = data.get("oa_locations", [])

        oa_url = None
        oa_version = None
        oa_license = None
        if best_oa:
            oa_url = best_oa.get("url")
            oa_version = best_oa.get("version")
            oa_license = best_oa.get("license")

        all_oa_urls = []
        for loc in oa_locations:
            url = loc.get("url")
            if url:
                all_oa_urls.append(url)

        record = Record(
            doi=doi,
            title=data.get("title", "") or "",
            year=data.get("year"),
            abstract="",  # Unpaywall doesn't provide abstracts
            source=self.name,
            query_hits=[],
            retrieved_by=self.name,
        )

        # Store OA info in crossref_data for later use
        record.crossref_data = {
            "unpaywall": {
                "is_oa": data.get("is_oa", False),
                "oa_status": data.get("oa_status"),
                "best_oa_url": oa_url,
                "best_oa_version": oa_version,
                "best_oa_license": oa_license,
                "all_oa_urls": all_oa_urls,
            }
        }

        return record