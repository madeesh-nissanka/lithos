# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Europe PMC / PubMed adapter for LITHOS.
"""
from __future__ import annotations
import logging
import urllib.parse
import json
from typing import Any, Optional

from lithos.adapters import BaseAdapter, AdapterConfig
from lithos.models import Record, SearchQuery, SearchResult

logger = logging.getLogger(__name__)

EUROPE_PMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
EUROPE_PMC_SEARCH = f"{EUROPE_PMC_BASE}/search"
EUROPE_PMC_FETCH = f"{EUROPE_PMC_BASE}/"


class EuropePMCAdapter(BaseAdapter):
    """Europe PMC API adapter (covers PubMed, PMC, and more)."""

    name = "europe_pmc"
    display_name = "Europe PMC"
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
            "query": translated,
            "pageSize": min(limit, 1000),
            "format": "json",
            "resultType": "lite",
        }

        if query.filters.get("from_year"):
            params["query"] += f" FIRST_PDATE:[{query.filters['from_year']} TO *]"
        if query.filters.get("to_year"):
            params["query"] += f" FIRST_PDATE:[* TO {query.filters['to_year']}]"

        if query.filters.get("open_access"):
            params["query"] += " OPEN_ACCESS:Y"

        url = f"{EUROPE_PMC_SEARCH}?" + urllib.parse.urlencode(params)

        try:
            data = self.http.get_json(url)
            results = []
            # Europe PMC REST returns {"hitCount": N, "resultList": {"result": [...]}}
            hit_list = data.get("resultList") or data.get("hitList") or {}
            hits = hit_list.get("result") or hit_list.get("hit") or []
            total = data.get("hitCount", len(hits))

            for hit in hits:
                record = self._parse_hit(hit, [translated])
                if record:
                    results.append(record)

            return SearchResult(
                query=query,
                records=results,
                total_hits=total,
                source=self.name,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"Europe PMC search failed: {e}")
            return SearchResult(query=query, source=self.name, errors=[str(e)], duration_seconds=time.time() - start_time)

    def fetch_by_id(self, identifier: str, id_type: str = "pmid") -> Optional[Record]:
        """Fetch a paper by PMID, PMCID, or DOI."""
        if id_type == "pmid":
            url = f"{EUROPE_PMC_FETCH}{identifier}/fullTextXML"
        elif id_type == "pmcid":
            url = f"{EUROPE_PMC_FETCH}PMC{identifier}/fullTextXML"
        elif id_type == "doi":
            url = f"{EUROPE_PMC_FETCH}{urllib.parse.quote(identifier)}/fullTextXML"
        else:
            logger.warning(f"Unsupported ID type for Europe PMC: {id_type}")
            return None

        params = {"format": "json"}
        url += "?" + urllib.parse.urlencode(params)

        try:
            data = self.http.get_json(url)
            hit_list = data.get("resultList") or data.get("hitList") or {}
            hits = hit_list.get("result") or hit_list.get("hit") or []
            if hits:
                return self._parse_hit(hits[0], [])
        except Exception as e:
            logger.error(f"Europe PMC fetch_by_id failed: {e}")
        return None

    def _parse_hit(self, hit: dict, query_hits: list[str]) -> Optional[Record]:
        """Parse Europe PMC hit into Record."""
        try:
            pmid = hit.get("pmid")
            pmcid = hit.get("pmcid")
            doi = hit.get("doi")
            title = hit.get("title", "") or ""
            year = hit.get("pubYear")
            if year is not None:
                try:
                    year = int(year)
                except (TypeError, ValueError):
                    year = None
            abstract = hit.get("abstractText", "") or ""

            authors = []
            # Europe PMC can return authorList (structured) or authorString (single string)
            author_list = hit.get("authorList", {}).get("author", [])
            if author_list:
                if isinstance(author_list, dict):
                    author_list = [author_list]
                for a in author_list:
                    name = a.get("fullName") or f"{a.get('firstName', '')} {a.get('lastName', '')}".strip()
                    if name:
                        authors.append(name)
            else:
                author_string = hit.get("authorString")
                if author_string:
                    # Split by semicolon or comma for multiple authors
                    for name in author_string.replace(";", ",").split(","):
                        name = name.strip()
                        if name:
                            authors.append(name)

            venue = hit.get("journalTitle") or hit.get("journalInfo", {}).get("journal", {}).get("title")
            pub_type = hit.get("pubType")

            # Keywords from MeSH terms
            keywords = []
            mesh = hit.get("meshHeadingList", {}).get("meshHeading", [])
            if isinstance(mesh, dict):
                mesh = [mesh]
            for m in mesh:
                desc = m.get("descriptorName")
                if desc:
                    keywords.append(desc)

            record = Record(
                pmid=pmid,
                pmcid=pmcid,
                doi=doi,
                title=title,
                year=year,
                authors=authors,
                venue=venue,
                abstract=abstract,
                keywords=keywords,
                publication_type=pub_type,
                cited_by=hit.get("citedByCount"),
                source=self.name,
                query_hits=query_hits,
                retrieved_by=self.name,
            )
            return record
        except Exception as e:
            logger.warning(f"Failed to parse Europe PMC hit: {e}")
            return None