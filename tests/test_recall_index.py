"""Exact ranking equivalence and reuse of a validated in-memory corpus."""
from collections import Counter
import json
import math
from pathlib import Path
import random
import sys
import subprocess
import tempfile
import unittest
import unicodedata
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
                expected = scan_reference(docs, terms)
                self.assertEqual(index.rank(terms), expected)
                self.assertEqual(rc.scan_rank(docs, terms), expected)
                self.assertEqual(index.rank(terms, limit=3, explain=False),
                                 [(score, identifier, []) for score, identifier, _ in expected[:3]])

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

    def test_excerpt_optimization_preserves_legacy_unicode_normalization(self):
        rng = random.Random(902)
        alphabet = "ab 中文éß\0\r\n\u200b\u2028\ue000\t\ud800"
        for size in (0, 1, 50, 1000):
            for limit in (1, 10, 500):
                text = "".join(rng.choices(alphabet, k=size))
                old = " ".join("".join(" " if unicodedata.category(char).startswith("C") else char
                                       for char in text).split())
                expected = old if len(old) <= limit else old[:limit - 1] + "…"
                self.assertEqual(rc._recall_excerpt(text, limit), expected)

    def test_technical_aliases_and_chinese(self):
        self.assertIn("runtime", rc.technical_tokens("RuntimeError"))
        self.assertIn("dataloader", rc.technical_tokens("data_loader"))
        self.assertIn("缓存", rc.technical_tokens("缓存泄漏"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "case.json").write_text(json.dumps(recall_case("data_loader exhausted")), encoding="utf-8")
            self.assertEqual(rc.recall_cases(path, "DataLoader")["matches"], [])
            self.assertEqual(rc.recall_cases(path, "DataLoader", ranking="technical")["matches"][0]["file"], "case.json")
            self.assertEqual(rc.recall_batch(path, ["DataLoader"], ranking="technical")["results"][0],
                             rc.recall_cases(path, "DataLoader", ranking="technical"))

    def test_cli_batch_file_and_no_query_echo(self):
        script = Path(rc.__file__)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "case.json").write_text(json.dumps(recall_case("Tensor mismatch")), encoding="utf-8")
            queries = path / "queries.data"
            def invoke():
                return subprocess.run([sys.executable, str(script), "recall-batch",
                                       "--cases-dir", str(path), "--queries-file", str(queries)],
                                      capture_output=True, text=True, encoding="utf-8", timeout=10)
            queries.write_text(json.dumps(["Tensor", "private-unique-unmatched-query"]), encoding="utf-8")
            result = invoke()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(json.loads(result.stdout)["results"]), 2)
            # Matched terms may appear; original unmatched queries are not echoed.
            self.assertNotIn("private-unique-unmatched-query", result.stdout)
            queries.write_text('["private-unique-unmatched-query", 3]', encoding="utf-8")
            result = invoke()
            self.assertEqual(result.returncode, 2)
            self.assertTrue(json.loads(result.stdout)["input_error"])
            self.assertNotIn("private-unique-unmatched-query", result.stdout)

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
