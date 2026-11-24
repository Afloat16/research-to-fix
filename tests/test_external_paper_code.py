"""Public archive labels and replay logic; no network."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
import external_paper_code as ep


class ExternalArchiveTests(unittest.TestCase):
    def test_only_official_labels_and_no_title_leak_into_candidates(self):
        archive = {"slices": [{"rows": [
            {"row": {"paper_arxiv_id": "2205.14135", "paper_title": "FlashAttention memory efficient attention",
                     "repo_url": "https://github.com/Dao-AILab/flash-attention", "is_official": True}},
            {"row": {"paper_arxiv_id": "2205.14135", "paper_title": "FlashAttention memory efficient attention",
                     "repo_url": "https://github.com/example/fork", "is_official": False}},
            {"row": {"paper_arxiv_id": "2205.14135", "paper_title": "FlashAttention memory efficient attention",
                     "repo_url": "http://localhost/", "is_official": True}}]}]}
        queries, repos = ep.fixture(archive)
        self.assertEqual(len(queries), 1)
        self.assertEqual(len(repos), 2)
        self.assertEqual(queries[0]["relevant"], ["https://github.com/dao-ailab/flash-attention"])
        self.assertEqual(ep.metric(queries[0]["relevant"], queries[0]["relevant"])["recall"], 1)
        self.assertIn("bm25", ep.slug_benchmark(queries, repos))


if __name__ == "__main__":
    unittest.main()
