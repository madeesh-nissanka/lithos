# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""
Optional local semantic screening/clustering for LITHOS.

Uses a small sentence-transformers model when the ``semantic`` extra is
installed (``pip install "lithos[semantic]"``); the model runs locally, with no
network calls at ranking time. TF-IDF/BM25 remains the default ranker.

An ``embed_fn`` (list[str] -> list[list[float]]) can be injected, which keeps
this module testable offline without the optional dependency.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from lithos.models import Record

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "paraphrase-MiniLM-L6-v2"

EmbedFn = Callable[[list[str]], list[list[float]]]


def _resolve_embed_fn(model_name: str, embed_fn: Optional[EmbedFn]) -> EmbedFn:
    if embed_fn is not None:
        return embed_fn
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise ImportError(
            "Semantic features require the optional dependency. "
            'Install with: pip install "lithos[semantic]" '
            "(sentence-transformers). TF-IDF/BM25 ranking needs no extra packages."
        ) from e
    model = SentenceTransformer(model_name or DEFAULT_MODEL)

    def _embed(texts: list[str]) -> list[list[float]]:
        vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [list(map(float, v)) for v in vecs]

    return _embed


def _record_text(record: Record, use_full_text: str = "") -> str:
    parts = [record.title, record.abstract, " ".join(record.keywords), use_full_text[:2000]]
    return " ".join(p for p in parts if p)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


@dataclass
class SemanticRanker:
    """Local embedding cosine-similarity ranker (optional extra)."""

    model_name: str = DEFAULT_MODEL
    embed_fn: Optional[EmbedFn] = None
    _query_vec: Optional[list[float]] = None
    _doc_vecs: dict = field(default_factory=dict)

    def _get(self, texts: list[str]) -> list[list[float]]:
        self._embed = getattr(self, "_embed", None) or _resolve_embed_fn(self.model_name, self.embed_fn)
        return self._embed(texts)

    def fit(self, records: list[Record], full_texts: Optional[dict] = None) -> None:
        texts = [_record_text(r, (full_texts or {}).get(r.id, "")) for r in records]
        vecs = self._get(texts) if texts else []
        self._doc_vecs = {r.id: v for r, v in zip(records, vecs)}

    def score(self, query: str, record: Record) -> float:
        if self._query_vec is None:
            self._query_vec = self._get([query])[0]
        return cosine(self._query_vec, self._doc_vecs.get(record.id, []))

    def rank(self, query: str, records: list[Record], full_texts: Optional[dict] = None) -> list[tuple[Record, float]]:
        self._query_vec = None
        self.fit(records, full_texts)
        scored = [(r, self.score(query, r)) for r in records]
        scored.sort(key=lambda x: (-x[1], x[0].id))
        return scored


def semantic_clusters(
    records: list[Record],
    threshold: float = 0.80,
    embed_fn: Optional[EmbedFn] = None,
    model_name: str = DEFAULT_MODEL,
) -> list[list[Record]]:
    """Greedy single-linkage clustering on local embedding cosine similarity.

    Records with similarity >= threshold (transitively) share a cluster.
    Returns clusters sorted by size descending, then by first record id.
    """
    if not records:
        return []
    embed = embed_fn or _resolve_embed_fn(model_name, embed_fn)
    vecs = embed([_record_text(r) for r in records])

    parent = list(range(len(records)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            if cosine(vecs[i], vecs[j]) >= threshold:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri

    groups: dict[int, list[Record]] = {}
    for i, r in enumerate(records):
        groups.setdefault(find(i), []).append(r)
    clusters = sorted(groups.values(), key=lambda g: (-len(g), min(r.id for r in g)))
    return clusters
