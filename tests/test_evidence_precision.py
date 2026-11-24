"""Precision, deduplication and optional rank fusion regressions."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import research_workflow as w
from test_comprehensive_plan import PROBLEM


class EvidencePrecisionTests(unittest.TestCase):
    def setUp(self):
        self.plan = w.make_plan(PROBLEM, 18, strategy="comprehensive")
        self.q = {q["source"]: q["id"] for q in self.plan["queries"]}

    def row(self, source, url, title, **extra):
        return {"query_id": self.q[source], "url": url, "title": title, **extra}

    def test_contradictory_arxiv_bridge_quarantines_without_merge(self):
        rows = [self.row("arxiv", "https://arxiv.org/abs/2205.14135",
                         "memory efficient attention", doi="10.1234/x"),
                self.row("arxiv", "https://arxiv.org/abs/2307.08691",
                         "memory efficient attention", doi="10.1234/x"),
                self.row("github_repositories", "https://github.com/a/b", "memory efficient attention")]
        report = w.rank_results(self.plan, [{"results": rows}])
        self.assertEqual(report["unique_identities"], 3)
        self.assertEqual(report["identity_conflict_count"], 2)
        self.assertEqual(len(report["shortlist"]), 1)
        self.assertEqual(report["shortlist"][0]["url"], "https://github.com/a/b")
        self.assertEqual(report, w.rank_results(self.plan, [{"results": list(reversed(rows))}]))

    def test_metadata_cannot_claim_read_and_retraction_cannot_win(self):
        rows = [self.row("openalex", "https://doi.org/10.1234/x", "memory efficient attention",
                         access="read", origin="openalex"),
                self.row("openalex", "https://doi.org/10.1234/y", "memory efficient attention",
                         origin="openalex", retraction_hint="retracted"),
                self.row("arxiv", "https://arxiv.org/abs/2205.14135", "memory efficient attention")]
        result = w.rank_results(self.plan, [{"results": rows}])
        self.assertEqual(result["skipped"]["metadata_origin_cannot_claim_read"], 1)
        self.assertEqual(len(result["shortlist"]), 1)
        self.assertEqual(result["shortlist"][0]["url"], "https://arxiv.org/abs/2205.14135")

    def test_fusion_uses_one_best_provider_rank_and_never_solely_popularity(self):
        code = self.row("github_repositories", "https://github.com/a/b",
                        "memory efficient exact attention", provider_rank=5, origin="github_repositories")
        repeated = dict(code, provider_rank=3)
        paper = self.row("arxiv", "https://arxiv.org/abs/2205.14135",
                         "memory efficient attention", provider_rank=1, origin="arxiv")
        unrelated = self.row("github_repositories", "https://github.com/a/c", "Astronomy",
                             provider_rank=1, origin="github_repositories")
        report = w.rank_results(self.plan, [{"results": [code, repeated, paper, unrelated]}], ranking="fusion")
        self.assertEqual(report["ranked_count"], 2)
        result = next(row for row in report["shortlist"] if row["family"] == "code")
        self.assertEqual(result["provider_ranks"], {"github_repositories": 3})
        self.assertEqual(result["observations"], 2)
        self.assertGreater(result["fusion_score"], 0)
        self.assertEqual(report["ranking"], "fusion")


if __name__ == "__main__":
    unittest.main()
