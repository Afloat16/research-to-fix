"""BM25F field normalization and deterministic ranking properties."""
from collections import Counter
import math
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "research-to-fix" / "scripts"))
import research_case as rc


def reference(documents, terms, tw, bw):
    n = len(documents)
    avg_t = sum(sum(t.values()) for _, t, _ in documents) / n if n else 1.
    avg_b = sum(sum(b.values()) for _, _, b in documents) / n if n else 1.
    df = Counter(term for _, title, body in documents for term in set(title) | (set(body) if bw else set()))
    rows = []
    for key, title, body in documents:
        contributions = {}
        for term in sorted(set(terms)):
            freq = tw * title.get(term, 0) / (.7 + .3 * sum(title.values()) / (avg_t or 1.)) + bw * body.get(term, 0) / (.25 + .75 * sum(body.values()) / (avg_b or 1.))
            if freq:
                idf = math.log1p((n - df[term] + .5) / (df[term] + .5))
                contributions[term] = idf * 2.5 * freq / (freq + 1.5)
        score = sum(contributions.values())
        if score:
            rows.append((score, key, sorted(contributions, key=lambda term: (-contributions[term], term))[:20]))
    return sorted(rows, key=lambda row: (-row[0], row[1]))


class FieldIndexTests(unittest.TestCase):
    def test_exact_reference_and_topk(self):
        rng = random.Random(451)
        vocab = ["attention", "kernel", "graph", "缓存", "tensor", "data_loader"]
        for n in (0, 1, 12, 80):
            docs = [(str(i), Counter(rng.choices(vocab, k=rng.randrange(0, 8))),
                     Counter(rng.choices(vocab, k=rng.randrange(0, 40)))) for i in range(n)]
            for tw, bw in ((1, 0), (2, 1), (4, 1), (8, 1)):
                index = rc.FieldIndex(docs, tw, bw)
                for _ in range(12):
                    query = rng.choices(vocab + ["missing"], k=4)
                    expected = reference(docs, query, tw, bw)
                    self.assertEqual(index.rank(query), expected)
                    self.assertEqual(index.rank(query, 3, False),
                                     [(score, key, []) for score, key, _ in expected[:3]])

    def test_title_normalization_and_no_match(self):
        docs = [("a", *rc.field_counts("attention kernel", "unrelated " * 200)),
                ("b", *rc.field_counts("attention kernel", "unrelated " * 10))]
        index = rc.FieldIndex(docs, 8, 1)
        # Exact independent-field normalization: unrelated body length cannot
        # change the contribution from an otherwise identical title.
        ranked = index.rank(["attent", "kernel"])
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0][0], ranked[1][0])
        self.assertEqual([row[1] for row in ranked], ["a", "b"])
        self.assertEqual(index.rank(["unseen"]), [])
        with self.assertRaises(ValueError):
            rc.FieldIndex([docs[0], docs[0]])
        self.assertEqual(rc.FieldIndex(docs, 1, 0).rank(["unrel"]), [])


if __name__ == "__main__":
    unittest.main()
