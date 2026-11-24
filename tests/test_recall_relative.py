"""Regression properties for exact bounded explanation and relative filtering."""
from collections import Counter
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "research-to-fix" / "scripts"))
import research_case as rc


def reference(index, terms, limit, threshold):
    ranked = index.rank(terms)
    cutoff = threshold * (ranked[0][0] if ranked else 0.0)
    retained = [row for row in ranked if row[0] >= cutoff]
    return len(retained), retained[:limit]


class RelativeRankTests(unittest.TestCase):
    def test_exact_scores_counts_explanations_and_cutoff(self):
        rng = random.Random(82491)
        vocab = ["缓存", "stem:attent", "phrase:kernel:launch"] + [f"term{i}" for i in range(40)]
        for size in (0, 1, 19, 180):
            docs = [(f"id{i:03d}", Counter(rng.choices(vocab, k=rng.randrange(0, 32))),
                     Counter(rng.choices(vocab, k=rng.randrange(0, 80)))) for i in range(size)]
            rng.shuffle(docs)
            for index in (rc.PostingIndex([(key, a + b) for key, a, b in docs]),
                          rc.FieldIndex(docs), rc.FieldIndex(docs, 1, 0)):
                for _ in range(18):
                    query = rng.choices(vocab + ["missing"], k=rng.randrange(0, 52))
                    for threshold in (0., .15, .5, 1.):
                        for limit in (1, 5, 250):
                            self.assertEqual(index.rank_relative(iter(query), limit, threshold),
                                             reference(index, query, limit, threshold))

    def test_boundary_ties_and_explanation_cap(self):
        vocab = [f"term{i:02d}" for i in range(30)]
        docs = [(name, Counter(vocab)) for name in ("z", "a", "m", "b")]
        index = rc.PostingIndex(docs)
        count, result = index.rank_relative(vocab + vocab, 2, 1.)
        self.assertEqual(count, 4)
        self.assertEqual([row[1] for row in result], ["a", "b"])
        self.assertEqual(result[0][2], vocab[:20])
        self.assertEqual(index.rank_relative(["missing"], 3, .2), (0, []))
        for limit, threshold in ((0, .2), (True, .2), (1, -1), (1, 1.1), (1, float("nan"))):
            with self.assertRaises(ValueError):
                index.rank_relative(vocab, limit, threshold)


if __name__ == "__main__":
    unittest.main()
