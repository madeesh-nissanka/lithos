#!/usr/bin/env python3
"""Unit tests for LITHOS."""
import json
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from lithos import (
    rebuild_abstract,
    strip_doi_prefix,
    normalize_title,
    title_similarity,
    first_author_surname,
    dedupe_records,
)


class TestLithos(unittest.TestCase):

    def test_rebuild_abstract(self):
        inv = {"the": [0, 3], "cat": [1], "sat": [2]}
        self.assertEqual(rebuild_abstract(inv), "the cat sat the")
        self.assertEqual(rebuild_abstract({}), "")
        self.assertEqual(rebuild_abstract(None), "")

    def test_strip_doi_prefix(self):
        self.assertEqual(strip_doi_prefix("https://doi.org/10.1000/xyz"), "10.1000/xyz")
        self.assertEqual(strip_doi_prefix("10.1000/xyz"), "10.1000/xyz")
        self.assertIsNone(strip_doi_prefix(None))
        self.assertIsNone(strip_doi_prefix(""))

    def test_normalize_title(self):
        self.assertEqual(normalize_title("The Cat Sat"), "the cat sat")
        self.assertEqual(normalize_title("Title: With, Punctuation!"), "title with punctuation")
        self.assertEqual(normalize_title(""), "")
        self.assertEqual(normalize_title(None), "")

    def test_title_similarity(self):
        self.assertGreaterEqual(title_similarity("The Cat Sat", "The Cat Sat"), 0.99)
        self.assertLess(title_similarity("The Cat Sat", "The Dog Ran"), 0.90)
        self.assertEqual(title_similarity("", ""), 1.0)
        self.assertEqual(title_similarity("A", "B"), 0.0)

    def test_first_author_surname(self):
        self.assertEqual(first_author_surname(["Smith, John"]), "Smith")
        self.assertEqual(first_author_surname(["John Smith"]), "Smith")
        self.assertEqual(first_author_surname(["Van der Waals"]), "Waals")
        self.assertIsNone(first_author_surname([]))
        self.assertIsNone(first_author_surname(None))

    def test_dedupe_records(self):
        recs = [
            {"doi": "10.1000/1", "title": "Paper One", "query_hits": ["q1"]},
            {"doi": "10.1000/1", "title": "Paper One", "query_hits": ["q2"]},
            {"doi": None, "title": "Paper Two", "query_hits": ["q1"]},
            {"doi": None, "title": "paper two", "query_hits": ["q3"]},
            {"doi": "10.1000/3", "title": "Paper Three", "query_hits": ["q1"]},
        ]
        out = dedupe_records(recs)
        self.assertEqual(len(out), 3)
        for r in out:
            if r["doi"] == "10.1000/1":
                self.assertEqual(set(r["query_hits"]), {"q1", "q2"})
            if r["title"] == "Paper Two":
                self.assertEqual(set(r["query_hits"]), {"q1", "q3"})


class TestStatusAssignment(unittest.TestCase):
    """Test status assignment logic using hand-made Crossref-like dicts."""

    def make_cr_msg(self, title, year, authors, update_to=None):
        msg = {
            "title": [title],
            "issued": {"date-parts": [[year]]},
            "author": [{"family": a} for a in authors],
        }
        if update_to:
            msg["update-to"] = update_to
        return msg

    def test_retracted(self):
        from lithos import check_retraction
        msg = self.make_cr_msg("Title", 2020, ["Smith"], [{"type": "retraction"}])
        self.assertTrue(check_retraction(msg))
        msg = self.make_cr_msg("Title", 2020, ["Smith"], [{"type": "withdrawal"}])
        self.assertTrue(check_retraction(msg))
        msg = self.make_cr_msg("Title", 2020, ["Smith"], [{"type": "correction"}])
        self.assertFalse(check_retraction(msg))

    def test_author_order_differs(self):
        from lithos import first_author_surname
        rec_authors = ["Smith, John", "Jones, Mary"]
        cr_surnames = ["Jones", "Smith"]
        rec_first = first_author_surname(rec_authors)
        self.assertEqual(rec_first, "Smith")
        self.assertIn(rec_first, cr_surnames)
        self.assertNotEqual(cr_surnames[0], rec_first)

    def test_author_mismatch(self):
        from lithos import first_author_surname
        rec_authors = ["Smith, John"]
        cr_surnames = ["Jones", "Brown"]
        rec_first = first_author_surname(rec_authors)
        self.assertNotIn(rec_first, cr_surnames)


if __name__ == "__main__":
    unittest.main()