"""Optional acceleration tests; run in benchmark environment with NumPy."""
from collections import Counter
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import research_case as rc
from numpy_rank import NumpyRanker

try:
    import numpy
except ImportError:
    numpy = None


@unittest.skipIf(numpy is None or sys.implementation.name != "cpython", "optional NumPy benchmark")
class VectorRankTests(unittest.TestCase):
    def test_exact_scores_ties_and_empty_queries(self):
        rng = random.Random(748913)
        terms = ["attention", "kernel", "缓存", "phrase:a:b", "stem:attent", "torch", "graph"]
        for size in (0, 1, 23, 500):
            docs = [(str(i), Counter(rng.choices(terms, k=rng.randrange(0, 50))),
                     Counter(rng.choices(terms, k=rng.randrange(0, 120)))) for i in range(size)]
            for index in (rc.FieldIndex(docs), rc.PostingIndex([(key, a + b) for key, a, b in docs])):
                fast = NumpyRanker(index)
                for _ in range(40):
                    query = rng.choices(terms + ["missing"], k=rng.randrange(0, 12))
                    for k in (None, 0, 1, 10, 1000):
                        self.assertEqual(fast.rank(query, k, False), index.rank(query, k, False))
                self.assertEqual(fast.rank(terms, 5, True), index.rank(terms, 5, True))
        index = rc.PostingIndex([("z", Counter(a=1)), ("a", Counter(a=1))])
        self.assertEqual(NumpyRanker(index).rank(["a"], 1, False)[0][1], "a")
