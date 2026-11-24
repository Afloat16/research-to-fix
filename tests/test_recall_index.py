"""Exact ranking equivalence and reuse of a validated in-memory corpus."""
from collections import Counter
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import research_case as rc
from test_case_recall import recall_case


def scan_reference(documents, terms):
    """Independent transcription of the pre-index BM25 scorer."""
    lengths = [sum(counts.values()) for _, counts in documents]
    mean = sum(lengths) / len(lengths) if lengths else 1.0
    frequencies = Counter(term for _, doc in documents for term in set(terms).intersection(doc))
    result = []
    for (identifier, doc), length in zip(documents, lengths):
        norm = 1.5 * (0.25 + 0.75 * length / (mean or 1.0))
        contributions = {term: math.log1p((len(documents) - frequencies[term] + 0.5)
                                        / (frequencies[term] + 0.5)) * (2.5 * doc[term])
                         / (doc[term] + norm)
                         for term in sorted(set(terms).intersection(doc))}
        score = sum(contributions.values())
        if score > 0:
            result.append((score, identifier, sorted(contributions,
                            key=lambda term: (-contributions[term], term))[:20]))
    return sorted(result, key=lambda row: (-row[0], row[1]))


class IndexTests(unittest.TestCase):
    def test_randomized_exact_equivalence(self):
        rng = random.Random(551)
        vocabulary = ["dtype", "tensor", "iterator", "缓存", "内存", "oom", "batch", "shape"]
        for size in (0, 1, 10, 200):
            docs = [(f"{i:04d}", Counter(rng.choices(vocabulary, k=rng.randrange(0, 80))))
                    for i in range(size)]
            index = rc.PostingIndex(docs)
            for _ in range(30):
                terms = rng.choices(vocabulary + ["missing"], k=rng.randrange(1, 10))
                self.assertEqual(index.rank(terms), scan_reference(docs, terms))

    def test_batch_reads_each_case_once_and_matches_single(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for i, summary in enumerate(("Tensor dtype mismatch", "Iterator consumption", "Chinese 缓存")):
                (path / f"{i}.json").write_text(json.dumps(recall_case(summary), ensure_ascii=False), encoding="utf-8")
            errors = ["dtype", "iterator", "缓存", "nothing"]
            expected = [rc.recall_cases(path, error) for error in errors]
            with patch.object(rc, "_recall_read", wraps=rc._recall_read) as reader:
                result = rc.recall_batch(path, errors)
                self.assertEqual(reader.call_count, 3)
            self.assertEqual(result["results"], expected)

    def test_invalid_batch_does_not_open_directory(self):
        for errors in ([], ["good", ""], ["good", 4], ["a"] * 129, "bad"):
            with self.subTest(errors=type(errors)):
                with patch.object(rc, "_load_recall_corpus") as load:
                    with self.assertRaises(rc.RecallInputError):
                        rc.recall_batch("unused", errors)
                    load.assert_not_called()

    def test_snapshot_results_are_independent_and_source_changes_require_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            case_path = path / "case.json"
            case_path.write_text(json.dumps(recall_case("Tensor mismatch")), encoding="utf-8")
            snapshot = rc.RecallSnapshot(path)
            report = snapshot.search("Tensor")
            self.assertEqual(len(report["matches"]), 1)
            report["matches"][0]["summary"] = "changed externally"
            self.assertNotEqual(snapshot.search("Tensor")["matches"][0]["summary"], "changed externally")
            case_path.unlink()
            self.assertEqual(len(snapshot.search("Tensor")["matches"]), 1)
            self.assertEqual(rc.recall_cases(path, "Tensor")["matches"], [])


if __name__ == "__main__":
    unittest.main()
