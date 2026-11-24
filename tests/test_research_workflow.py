import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "research-to-fix" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import research_workflow as w


PROBLEM = {"symptom": "attention GPU memory grows with sequence length",
           "task": "efficient attention", "component": "PyTorch",
           "concepts": ["FlashAttention", "memory efficient attention"],
           "alternative_concepts": ["block sparse attention"], "focus": "algorithm"}


class PlanTests(unittest.TestCase):
    def test_small_budget_covers_code_and_paper_and_exact_symptom(self):
        plan = w.make_plan(PROBLEM, 3)
        self.assertEqual([row["source"] for row in plan["queries"]],
                         ["github_repositories", "arxiv", "github_issues"])
        self.assertEqual({row["family"] for row in plan["queries"]}, {"code", "paper"})
        self.assertEqual(plan, w.validate_plan(plan))
        self.assertEqual(w.make_plan(PROBLEM, 3), plan)
        self.assertTrue(plan["omitted_sources"])

    def test_focus_and_native_queries(self):
        plan = w.make_plan(dict(PROBLEM, focus="bug", repo="pytorch/pytorch"), 12)
        self.assertEqual(plan["queries"][0]["source"], "github_issues")
        self.assertIn("repo:pytorch/pytorch", plan["queries"][0]["native_query"])
        self.assertIn("is:issue", plan["queries"][0]["native_query"])
        self.assertNotIn("site:", plan["queries"][0]["native_query"])
        self.assertIn("counterevidence", {row["stage"] for row in plan["queries"]})

    def test_redaction_and_plan_tampering(self):
        for symptom in ("token=secretvalue", "/home/alice/project/private.py", "http://127.0.0.1/path",
                        "contact dev@example.com", "https://example.com/path"):
            with self.subTest(symptom=symptom), self.assertRaises(w.WorkflowError):
                w.make_plan(dict(PROBLEM, symptom=symptom))
        plan = w.make_plan(PROBLEM)
        plan["queries"][0]["native_query"] = "unreviewed hidden query"
        with self.assertRaises(w.WorkflowError):
            w.validate_plan(plan)

    def test_source_filter_and_explicit_omissions(self):
        plan = w.make_plan(PROBLEM, 8, ["crossref", "arxiv"])
        self.assertEqual({row["source"] for row in plan["queries"]}, {"crossref", "arxiv"})
        self.assertEqual(plan["omitted_sources"], [])
        with self.assertRaises(w.WorkflowError):
            w.make_plan(PROBLEM, 0)


class TriageTests(unittest.TestCase):
    def setUp(self):
        self.plan = w.make_plan(PROBLEM, 12)
        self.ids = {q["source"]: q["id"] for q in self.plan["queries"]}

    def row(self, source, url, title, **extra):
        return dict(query_id=self.ids[source], url=url, title=title, **extra)

    def test_transitive_duplicate_identity_and_version_preservation(self):
        rows = [
            self.row("arxiv", "https://arxiv.org/abs/2205.14135v2", "FlashAttention: memory efficient attention",
                     doi="10.1000/flash", revision="v2", access="metadata"),
            self.row("crossref", "https://doi.org/10.1000/flash", "FlashAttention efficient attention",
                     access="metadata"),
            self.row("arxiv", "https://arxiv.org/pdf/2205.14135v3.pdf", "FlashAttention attention",
                     revision="v3"),
            self.row("github_repositories", "https://github.com/Dao-AILab/flash-attention/",
                     "FlashAttention GPU memory efficient attention"),
            self.row("github_repositories", "https://github.com/dao-ailab/flash-attention?utm_source=x",
                     "FlashAttention efficient attention"),
        ]
        report = w.rank_results(self.plan, [{"results": rows}])
        self.assertEqual(report["unique_identities"], 2)
        self.assertEqual(report["duplicates_collapsed"], 3)
        self.assertEqual({row["family"] for row in report["shortlist"]}, {"code", "paper"})
        paper = next(row for row in report["shortlist"] if row["family"] == "paper")
        self.assertEqual({p["revision"] for p in paper["provenance"]}, {"", "v2", "v3"})
        self.assertEqual(paper["access"], "metadata")
        self.assertIn(paper["id"], report["needs_original_review"])

    def test_relevance_over_popularity_and_unrelated_results(self):
        rows = [
            self.row("github_repositories", "https://github.com/example/popular", "PyTorch",
                     stars=1000000, snippet="General purpose package"),
            self.row("github_repositories", "https://github.com/example/attn",
                     "FlashAttention efficient attention", snippet="Reduce GPU memory"),
            self.row("arxiv", "https://arxiv.org/abs/2205.14135", "Efficient attention for long sequences"),
            self.row("arxiv", "https://arxiv.org/abs/2101.00001", "Completely unrelated astronomy"),
        ]
        report = w.rank_results(self.plan, [{"results": rows}])
        self.assertEqual(report["ranked_count"], 2)
        self.assertEqual(report["skipped"]["no_relevance"], 2)
        self.assertEqual({row["family"] for row in report["shortlist"]}, {"code", "paper"})

    def test_coverage_and_blocked_results_are_not_promoted(self):
        rows = [self.row("arxiv", "https://arxiv.org/abs/2205.14135", "FlashAttention attention",
                         access="access_blocked")]
        report = w.rank_results(self.plan, [{"results": rows, "searches": [
            {"query_id": self.ids["arxiv"], "status": "access_blocked"}]}])
        self.assertEqual(report["shortlist"], [])
        self.assertIn("paper", report["family_gaps"])
        self.assertIn(self.ids["github_repositories"], report["unrecorded_queries"])

    def test_github_objects_not_collapsed_and_invalid_urls_skipped(self):
        self.assertNotEqual(w.canonical_url("https://github.com/a/b/issues/12#issuecomment-3"),
                            w.canonical_url("https://github.com/a/b/pull/12"))
        self.assertEqual(w.canonical_url("https://arxiv.org/pdf/2205.14135v2.pdf"),
                         "https://arxiv.org/abs/2205.14135")
        rows = [self.row("arxiv", "http://127.0.0.1/a", "FlashAttention"),
                self.row("arxiv", "https://arxiv.org/abs/2205.14135", "FlashAttention")]
        report = w.rank_results(self.plan, [{"results": rows}])
        self.assertEqual(report["skipped"]["invalid_public_url"], 1)
        self.assertEqual(report["valid_observations"], 1)

    def test_no_search_claim_without_explicit_status_and_stable_order(self):
        rows = [self.row("arxiv", "https://arxiv.org/abs/2205.14135", "FlashAttention attention"),
                self.row("github_repositories", "https://github.com/dao-ailab/flash-attention",
                         "FlashAttention attention")]
        a = w.rank_results(self.plan, [{"results": rows}])
        b = w.rank_results(self.plan, [{"results": list(reversed(rows))}])
        self.assertEqual(a, b)
        self.assertEqual(a["unrecorded_queries"], [q["id"] for q in self.plan["queries"]])
        self.assertTrue(all(row["status"] == ["not_recorded"] for row in a["coverage"]))


if __name__ == "__main__":
    unittest.main()
