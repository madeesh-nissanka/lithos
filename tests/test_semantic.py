# LITHOS - Copyright (c) 2026 Madeesh P. Nissanka. MIT License.
"""Tests for lithos.semantic module (offline, deterministic embed_fn injection)."""
from testhelpers import add_src_path
add_src_path()

import unittest

from testhelpers import make_record
from lithos.models import Record
from lithos.semantic import SemanticRanker, cosine, semantic_clusters

DIM_KEYS = ["consolidation", "slope", "concrete"]


def keyword_embed(texts):
    """Deterministic embed_fn: one dimension per keyword, value = count."""
    return [[float(t.lower().count(k)) for k in DIM_KEYS] for t in texts]


def sentence_transformers_importable():
    """True when the optional semantic extra can be imported."""
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


class TestCosine(unittest.TestCase):
    """Tests for the cosine helper."""

    def test_empty_vectors(self):
        """Empty vectors score 0.0."""
        self.assertEqual(cosine([], []), 0.0)

    def test_one_empty_vector(self):
        """One empty vector scores 0.0."""
        self.assertEqual(cosine([], [1.0]), 0.0)
        self.assertEqual(cosine([1.0], []), 0.0)

    def test_unequal_lengths(self):
        """Unequal-length vectors score 0.0."""
        self.assertEqual(cosine([1.0, 0.0], [1.0]), 0.0)
        self.assertEqual(cosine([1.0], [1.0, 0.0]), 0.0)
        self.assertEqual(cosine([1.0, 2.0, 3.0], [1.0, 2.0]), 0.0)

    def test_parallel_unit_vectors(self):
        """Parallel unit vectors score about 1.0."""
        self.assertAlmostEqual(cosine([1.0, 0.0], [1.0, 0.0]), 1.0, places=7)
        self.assertAlmostEqual(cosine([0.0, 1.0], [0.0, 1.0]), 1.0, places=7)
        vec = [1.0 / 3 ** 0.5] * 3
        self.assertAlmostEqual(cosine(vec, vec), 1.0, places=7)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors score 0.0."""
        self.assertEqual(cosine([1.0, 0.0], [0.0, 1.0]), 0.0)


class TestSemanticRanker(unittest.TestCase):
    """Tests for SemanticRanker with an injected embed_fn."""

    def setUp(self):
        self.records = [
            make_record(
                id="c1",
                title="Soil consolidation settlement of soft clay",
                abstract="Consolidation of soft clay under embankment loading.",
                keywords=["consolidation", "settlement", "clay"],
            ),
            make_record(
                id="s1",
                title="Slope stability analysis of earth embankments",
                abstract="Limit equilibrium slope stability assessment.",
                keywords=["slope", "stability"],
            ),
            make_record(
                id="d1",
                title="Concrete durability under chloride exposure",
                abstract="Chloride ingress reduces concrete durability.",
                keywords=["concrete", "durability", "chloride"],
            ),
        ]
        self.ranker = SemanticRanker(embed_fn=keyword_embed)

    def test_rank_orders_by_similarity(self):
        """rank puts the record matching the query first."""
        ranked = self.ranker.rank("consolidation", self.records)
        self.assertEqual(len(ranked), 3)
        self.assertEqual(ranked[0][0].id, "c1")
        self.assertGreaterEqual(ranked[0][1], ranked[1][1])
        self.assertGreaterEqual(ranked[1][1], ranked[2][1])

    def test_rank_returns_record_score_tuples(self):
        """rank returns (Record, float) tuples."""
        ranked = self.ranker.rank("slope stability", self.records)
        for item in ranked:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[0], Record)
            self.assertIsInstance(item[1], float)
        self.assertEqual(ranked[0][0].id, "s1")

    def test_fit_stores_one_vector_per_record(self):
        """fit stores one vector per record id."""
        self.ranker.fit(self.records)
        self.assertEqual(len(self.ranker._doc_vecs), len(self.records))
        self.assertEqual(set(self.ranker._doc_vecs), {r.id for r in self.records})
        for record in self.records:
            self.assertEqual(len(self.ranker._doc_vecs[record.id]), len(DIM_KEYS))

    def test_score_zero_for_unrelated_query(self):
        """An unrelated query scores 0.0 for every record."""
        self.ranker.fit(self.records)
        for record in self.records:
            self.assertEqual(self.ranker.score("unrelated topic", record), 0.0)


class TestSemanticClusters(unittest.TestCase):
    """Tests for semantic_clusters with a deterministic embed_fn."""

    def setUp(self):
        self.consolidation_1 = make_record(
            id="c1",
            title="Soil consolidation settlement of soft clay",
            abstract="Consolidation of clay under loading.",
            keywords=["consolidation", "settlement"],
        )
        self.consolidation_2 = make_record(
            id="c2",
            title="Consolidation of layered clay deposits",
            abstract="Layered consolidation analysis.",
            keywords=["consolidation", "clay"],
        )
        self.slope = make_record(
            id="s1",
            title="Slope stability of earth embankments",
            abstract="Slope stability by limit equilibrium.",
            keywords=["slope", "stability"],
        )
        self.concrete = make_record(
            id="d1",
            title="Concrete durability under chloride exposure",
            abstract="Chloride ingress in concrete.",
            keywords=["concrete", "durability"],
        )

    def test_groups_records_above_threshold(self):
        """Only the two consolidation records share a cluster."""
        clusters = semantic_clusters(
            [self.consolidation_1, self.consolidation_2, self.slope],
            threshold=0.9,
            embed_fn=keyword_embed,
        )
        self.assertEqual(len(clusters[0]), 2)
        self.assertEqual({r.id for r in clusters[0]}, {"c1", "c2"})
        self.assertEqual(len(clusters), 2)
        for cluster in clusters:
            self.assertLessEqual(len(cluster), 2)

    def test_empty_records(self):
        """Empty input returns no clusters."""
        self.assertEqual(semantic_clusters([], embed_fn=keyword_embed), [])

    def test_impossible_threshold_yields_singletons(self):
        """A threshold above 1.0 leaves every record in its own cluster."""
        records = [self.consolidation_1, self.slope, self.concrete]
        clusters = semantic_clusters(records, threshold=1.01, embed_fn=keyword_embed)
        self.assertEqual(len(clusters), len(records))
        for cluster in clusters:
            self.assertEqual(len(cluster), 1)
        self.assertEqual(
            {cluster[0].id for cluster in clusters},
            {r.id for r in records},
        )


@unittest.skipUnless(
    not sentence_transformers_importable(),
    "sentence_transformers is importable; ImportError path unavailable",
)
class TestMissingOptionalDependency(unittest.TestCase):
    """ImportError path when the optional semantic extra is absent."""

    def test_fit_raises_import_error_without_embed_fn(self):
        """fit without embed_fn raises ImportError naming the extra."""
        records = [
            make_record(
                id="c1",
                title="Soil consolidation settlement of soft clay",
                abstract="Consolidation of clay under loading.",
                keywords=["consolidation"],
            ),
        ]
        ranker = SemanticRanker(embed_fn=None)
        with self.assertRaises(ImportError) as ctx:
            ranker.fit(records)
        self.assertIn("lithos[semantic]", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
