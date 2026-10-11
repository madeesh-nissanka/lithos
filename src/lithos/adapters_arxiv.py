# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
arXiv adapter for LITHOS.
"""
from __future__ import annotations
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Optional

from lithos.adapters import BaseAdapter, AdapterConfig
from lithos.models import Record, SearchQuery, SearchResult

logger = logging.getLogger(__name__)

ARXIV_BASE = "http://export.arxiv.org/api/query"
ARXIV_NAMESPACE = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivAdapter(BaseAdapter):
    """arXiv API adapter."""

    name = "arxiv"
    display_name = "arXiv"
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
            "search_query": translated,
            "start": 0,
            "max_results": min(limit, 200),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        if query.filters.get("from_year"):
            params["search_query"] += f" AND submittedDate:[{query.filters['from_year']}0101 TO *]"
        if query.filters.get("to_year"):
            params["search_query"] += f" AND submittedDate:[* TO {query.filters['to_year']}1231]"

        url = f"{ARXIV_BASE}?" + urllib.parse.urlencode(params)

        try:
            xml_text = self.http.get_text(url)
            results = self._parse_xml(xml_text, [translated])
            return SearchResult(
                query=query,
                records=results,
                total_hits=len(results),
                source=self.name,
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"arXiv search failed: {e}")
            return SearchResult(query=query, source=self.name, errors=[str(e)], duration_seconds=time.time() - start_time)

    def fetch_by_id(self, identifier: str, id_type: str = "arxiv") -> Optional[Record]:
        """Fetch a paper by arXiv ID."""
        if id_type != "arxiv":
            return None

        url = f"{ARXIV_BASE}?id_list={identifier}"
        try:
            xml_text = self.http.get_text(url)
            results = self._parse_xml(xml_text, [])
            return results[0] if results else None
        except Exception as e:
            logger.error(f"arXiv fetch_by_id failed: {e}")
            return None

    def _parse_xml(self, xml_text: str, query_hits: list[str]) -> list[Record]:
        """Parse arXiv Atom XML into Records."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error(f"Failed to parse arXiv XML: {e}")
            return []

        entries = root.findall(".//atom:entry", ARXIV_NS)
        results = []

        for entry in entries:
            try:
                # Get arXiv ID
                arxiv_id = None
                id_elem = entry.find("atom:id", ARXIV_NS)
                if id_elem is not None and id_elem.text:
                    arxiv_url = id_elem.text.strip()
                    if "arxiv.org/abs/" in arxiv_url:
                        arxiv_id = arxiv_url.split("arxiv.org/abs/")[-1]

                # Get title
                title_elem = entry.find("atom:title", ARXIV_NS)
                title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

                # Get abstract
                summary_elem = entry.find("atom:summary", ARXIV_NS)
                abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else ""

                # Get authors
                authors = []
                for author in entry.findall("atom:author", ARXIV_NS):
                    name_elem = author.find("atom:name", ARXIV_NS)
                    if name_elem is not None and name_elem.text:
                        authors.append(name_elem.text.strip())

                # Get published date
                published_elem = entry.find("atom:published", ARXIV_NS)
                year = None
                if published_elem is not None and published_elem.text:
                    try:
                        year = int(published_elem.text[:4])
                    except (ValueError, IndexError):
                        pass

                # Get categories
                categories = []
                for cat in entry.findall("atom:category", ARXIV_NS):
                    term = cat.get("term")
                    if term:
                        categories.append(term)

                # Get DOI if available
                doi = None
                for link in entry.findall("atom:link", ARXIV_NS):
                    if link.get("title") == "doi" and link.get("href"):
                        doi = link.get("href")
                        if doi.startswith("http://dx.doi.org/"):
                            doi = doi[len("http://dx.doi.org/"):]
                        elif doi.startswith("https://doi.org/"):
                            doi = doi[len("https://doi.org/"):]

                # Get journal reference (for published versions)
                journal_ref = None
                jr_elem = entry.find("arxiv:journal_reference", ARXIV_NS)
                if jr_elem is not None and jr_elem.text:
                    journal_ref = jr_elem.text.strip()

                record = Record(
                    arxiv_id=arxiv_id,
                    doi=doi,
                    title=title,
                    year=year,
                    authors=authors,
                    venue=journal_ref,
                    abstract=abstract,
                    keywords=categories,
                    publication_type="preprint",
                    source=self.name,
                    query_hits=query_hits,
                    retrieved_by=self.name,
                )
                results.append(record)
            except Exception as e:
                logger.warning(f"Failed to parse arXiv entry: {e}")
                continue

        return results