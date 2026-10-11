# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Shared test helpers for the LITHOS offline test suite (stdlib only).

Tests never touch the network: adapters are exercised by monkeypatching
``lithos.http.HTTPClient.get_json`` / ``get_text`` with synthetic payloads.
All fixture data is synthetic; DOIs use the reserved ``10.9999/`` prefix and
topics are textbook-level engineering/science examples.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def add_src_path() -> None:
    """Ensure ``src`` is importable when tests run from the repo root."""
    src = Path(__file__).resolve().parents[1] / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def make_record(**overrides):
    """Build a synthetic :class:`lithos.models.Record` for tests."""
    from lithos.models import Record

    data = {
        "id": "",
        "doi": "10.9999/aaa",
        "title": "Soil consolidation settlement of soft clay",
        "year": 2018,
        "authors": ["Alpha, A."],
        "venue": "Geotechnical Engineering Journal",
        "abstract": "Settlement of soft clay foundations under embankment loading " * 3,
        "keywords": ["consolidation", "settlement", "clay"],
        "publication_type": "journal-article",
        "source": "openalex",
        "cited_by": 5,
    }
    data.update(overrides)
    return Record(**data)


OPENALEX_PAYLOAD = {
    "meta": {"count": 2},
    "results": [
        {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.9999/aaa",
            "title": "Soil consolidation settlement of soft clay",
            "publication_year": 2018,
            "authorships": [{"author": {"display_name": "A. Alpha"}}],
            "primary_location": {"source": {"display_name": "Geotechnical Engineering Journal"}},
            "cited_by_count": 5,
            "type": "journal-article",
            "abstract_inverted_index": {"settlement": [0], "of": [1], "clay": [2]},
            "referenced_works": ["https://doi.org/10.9999/ref1"],
            "keywords": [{"display_name": "consolidation"}],
        },
        {
            "id": "https://openalex.org/W2",
            "doi": None,
            "title": "Slope stability analysis methods",
            "publication_year": 2020,
            "authorships": [{"author": {"display_name": "B. Beta"}}],
            "primary_location": None,
            "cited_by_count": 2,
            "type": "journal-article",
            "abstract_inverted_index": None,
            "referenced_works": [],
            "keywords": [],
        },
    ],
}

CROSSREF_ITEM = {
    "DOI": "10.9999/aaa",
    "title": ["Soil consolidation settlement of soft clay"],
    "issued": {"date-parts": [[2018]]},
    "author": [{"family": "Alpha", "given": "A."}],
    "container-title": ["Geotechnical Engineering Journal"],
    "type": "journal-article",
}

CROSSREF_PAYLOAD = {"message": {"total-results": 1, "items": [CROSSREF_ITEM]}}

# Payload for validate_doi (direct DOI lookup returns message directly)
CROSSREF_VALIDATE_PAYLOAD = {"message": CROSSREF_ITEM}

SEMANTICSCHOLAR_PAYLOAD = {
    "data": [
        {
            "paperId": "s2abc",
            "title": "Pavement fatigue cracking models",
            "year": 2019,
            "abstract": "Fatigue cracking of flexible pavements under traffic loading.",
            "authors": [{"name": "C. Gamma"}],
            "externalIds": {"DOI": "10.9999/ddd"},
            "venue": "Road Materials Journal",
            "publicationTypes": ["JournalArticle"],
            "citationCount": 3,
        }
    ]
}

ARXIV_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2001.00001v1</id>
    <title>Bearing capacity of shallow foundations</title>
    <published>2020-01-01T00:00:00Z</published>
    <summary>Bearing capacity of shallow foundations on sand.</summary>
    <author><name>D. Delta</name></author>
    <link href="http://arxiv.org/abs/2001.00001v1" rel="alternate"/>
  </entry>
</feed>
"""

EUROPEPMC_PAYLOAD = {
    "hitCount": 1,
    "resultList": {
        "result": [
            {
                "id": "12345678",
                "pmid": "12345678",
                "pmcid": "PMC123456",
                "doi": "10.9999/eee",
                "title": "Chloride ingress in reinforced concrete",
                "authorString": "E. Epsilon",
                "journalTitle": "Concrete Durability",
                "pubYear": "2017",
                "abstractText": "Chloride ingress modelling in concrete.",
                "isOpenAccess": "Y",
            }
        ]
    },
}

DOAJ_PAYLOAD = {
    "results": [
        {
            "bibjson": {
                "title": "Machine learning for image segmentation",
                "abstract": "Segmentation of engineering imagery.",
                "year": "2021",
                "author": [{"name": "F. Zeta"}],
                "journal": {"title": "Applied Computing"},
                "doi": "10.9999/fff",
            }
        }
    ]
}


@contextmanager
def fake_http(json_payload=None, text_payload=None):
    """Context manager patching ``HTTPClient.get_json`` / ``get_text`` offline."""
    from unittest import mock

    from lithos import http

    patchers = []
    if json_payload is not None:
        patchers.append(mock.patch.object(http.HTTPClient, "get_json", return_value=json_payload))
    if text_payload is not None:
        patchers.append(mock.patch.object(http.HTTPClient, "get_text", return_value=text_payload))
    for p in patchers:
        p.start()
    try:
        yield
    finally:
        for p in patchers:
            p.stop()
