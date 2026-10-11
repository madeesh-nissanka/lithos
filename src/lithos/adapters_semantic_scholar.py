# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Semantic Scholar adapter for LITHOS.
"""
from __future__ import annotations
import logging
import urllib.parse
from typing import Any, Optional

from lithos.adapters import BaseAdapter, AdapterConfig
from lithos.models import Record, SearchQuery, SearchResult

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_SEARCH = f"{SEMANTIC_SCHOLAR_BASE}/paper/search"
SEMANTIC_SCHOLAR_PAPER = f"{SEMANTIC_SCHOLAR_BASE}/paper"


class SemanticScholarAdapter(BaseAdapter):
    """Semantic Scholar API adapter."""

    name = "semantic_scholar"
    display_name = "Semantic Scholar"
    requires_api_key = False  # Optional API key for higher rate limits
    supports_boolean = True
    supports_year_filter = True

    def __init__(self, config: Optional[AdapterConfig] = None):
        super().__init__(config)
        self.api_key = config.api_key if config else None

    def _get_headers(self) -> dict:
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
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

        translated = self.translate_query(query)
        if not translated:
            return SearchResult(query=query, source=self.name, errors=["Empty query"])

        params = {
            "query": translated,
            "limit": min(limit, 100),
            "fields": "paperId,title,year,authors,venue,abstract,citationCount,influentialCitationCount,fieldsOfStudy,publicationTypes,externalIds,references,citations",
        }

        if query.filters.get("from_year"):
            params["year"] = f"{query.filters['from_year']}-"
        if query.filters.get("to_year"):
            if "year" in params:
                params["year"] += str(query.filters["to_year"])
            else:
                params["year"] = f"-{query.filters['to_year']}"

        url = f"{SEMANTIC_SCHOLAR_SEARCH}?" + urllib.parse.urlencode(params)

        try:
            headers = self._get_headers()
            data = self.http.get_json(url)
            results = []
            for paper in data.get("data", []):
                record = self._parse_paper(paper, [translated])
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
            logger.error(f"Semantic Scholar search failed: {e}")
            return SearchResult(query=query, source=self.name, errors=[str(e)], duration_seconds=time.time() - start_time)

    def fetch_by_id(self, identifier: str, id_type: str = "doi") -> Optional[Record]:
        """Fetch a paper by DOI, Semantic Scholar ID, or other external ID."""
        if id_type == "doi":
            url = f"{SEMANTIC_SCHOLAR_PAPER}/DOI:{identifier}"
        elif id_type == "semantic_scholar":
            url = f"{SEMANTIC_SCHOLAR_PAPER}/{identifier}"
        elif id_type == "arxiv":
            url = f"{SEMANTIC_SCHOLAR_PAPER}/ARXIV:{identifier}"
        elif id_type == "pmid":
            url = f"{SEMANTIC_SCHOLAR_PAPER}/PMID:{identifier}"
        elif id_type == "corpus_id":
            url = f"{SEMANTIC_SCHOLAR_PAPER}/CorpusId:{identifier}"
        else:
            logger.warning(f"Unsupported ID type for Semantic Scholar: {id_type}")
            return None

        params = {
            "fields": "paperId,title,year,authors,venue,abstract,citationCount,influentialCitationCount,fieldsOfStudy,publicationTypes,externalIds,references,citations",
        }
        url += "?" + urllib.parse.urlencode(params)

        try:
            headers = self._get_headers()
            data = self.http.get_json(url, headers=headers)
            return self._parse_paper(data, [])
        except Exception as e:
            logger.error(f"Semantic Scholar fetch_by_id failed: {e}")
            return None

    def _parse_paper(self, paper: dict, query_hits: list[str]) -> Optional[Record]:
        """Parse Semantic Scholar paper into Record."""
        paper_id = paper.get("paperId")
        title = paper.get("title", "") or ""
        year = paper.get("year")

        authors = []
        for a in paper.get("authors", []):
            name = a.get("name")
            if name:
                authors.append(name)

        venue = paper.get("venue")
        abstract = paper.get("abstract", "") or ""
        cited_by = paper.get("citationCount")
        pub_types = paper.get("publicationTypes", [])
        pub_type = pub_types[0] if pub_types else None

        keywords = paper.get("fieldsOfStudy", [])

        external_ids = paper.get("externalIds", {})
        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")
        pmid = external_ids.get("PubMed")
        corpus_id = external_ids.get("CorpusId")

        referenced = []
        for ref in paper.get("references", []):
            ref_doi = ref.get("externalIds", {}).get("DOI")
            if ref_doi:
                referenced.append(ref_doi.lower())

        citing = []
        for cit in paper.get("citations", []):
            cit_doi = cit.get("externalIds", {}).get("DOI")
            if cit_doi:
                citing.append(cit_doi.lower())

        record = Record(
            semantic_scholar_id=paper_id,
            doi=doi,
            arxiv_id=arxiv_id,
            pmid=pmid,
            title=title,
            year=year,
            authors=authors,
            venue=venue,
            abstract=abstract,
            keywords=keywords,
            publication_type=pub_type,
            cited_by=cited_by,
            referenced_works=referenced,
            citing_works=citing,
            source=self.name,
            query_hits=query_hits,
            retrieved_by=self.name,
        )
        return record