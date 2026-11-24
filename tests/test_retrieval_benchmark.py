"""Benchmark metrics and strict label checks."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "retrieval.py"
SPEC = importlib.util.spec_from_file_location("retrieval_bench", PATH)
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


class BenchmarkTests(unittest.TestCase):
    def test_metrics_known_values(self):
        scores = bench.metrics(["irrelevant", "a", "b"], ["a", "c"], 3)
        self.assertEqual(scores["mrr"], .5)
        self.assertEqual(scores["recall"], .5)
        self.assertEqual(scores["hit"], 1)
        self.assertAlmostEqual(scores["ndcg"], (1 / __import__("math").log2(3)) / (1 + 1 / __import__("math").log2(3)))
        self.assertTrue(bench.metrics([], [], 10)["abstained"])
        self.assertFalse(bench.metrics(["a"], [], 10)["abstained"])

    def test_public_title_dataset_has_traceable_labels(self):
        corpus, queries, meta = bench.load_github_titles()
        self.assertEqual(meta["kind"], "public_issue_title_retrieval")
        self.assertEqual(len(corpus), 44)
        self.assertEqual(len(queries), 18)
        self.assertTrue(all(row["source_url"].startswith("https://github.com/") for row in corpus))
        self.assertTrue(all(row["judgment_url"].startswith(row["source_url"] + "#issuecomment-")
                            and len(row["relevant"]) == 1 for row in queries))
        result = bench.run(corpus, queries, meta, k=5, repeats=1)
        self.assertTrue(result["legacy_indexed_top_k_exact_match"])

    def test_dataset_and_end_to_end_benchmark(self):
        corpus, queries, meta = bench.load_synthetic()
        self.assertGreaterEqual(len(corpus), 40)
        report = bench.run(corpus, queries, meta, k=5, repeats=1)
        self.assertTrue(report["legacy_indexed_top_k_exact_match"])
        self.assertEqual(report["methods"]["legacy_scan"]["mrr@5"],
                         report["methods"]["indexed_bm25"]["mrr@5"])
        for result in report["methods"].values():
            if result["status"] == "completed":
                self.assertGreaterEqual(result["mrr@5"], 0)
                self.assertLessEqual(result["ndcg@5"], 1)


if __name__ == "__main__":
    unittest.main()
