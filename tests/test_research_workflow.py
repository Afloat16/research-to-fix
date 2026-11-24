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

    def test_linked_paper_code_routes_and_unresolved_links(self):
        code = self.row("github_repositories", "https://github.com/Dao-AILab/flash-attention",
                        "FlashAttention efficient attention", access="read",
                        links=[{"url": "https://arxiv.org/abs/2205.14135v2", "relation": "implements", "basis": "read"},
                               {"url": "https://arxiv.org/abs/2307.08691", "relation": "implements", "basis": "read"}])
        paper = self.row("arxiv", "https://arxiv.org/pdf/2205.14135v3.pdf",
                         "FlashAttention efficient attention")
        result = w.rank_results(self.plan, [{"results": [code, paper]}])
        graph = result["evidence_graph"]
        self.assertEqual(graph["pair_count"], 1)
        self.assertEqual(graph["paper_code_pairs"][0]["basis"], "read")
        self.assertEqual(graph["unresolved_count"], 1)
        code["access"] = "metadata"
        result = w.rank_results(self.plan, [{"results": [code, paper]}])
        self.assertEqual(result["skipped"]["unread_relation"], 1)
        self.assertEqual(result["evidence_graph"]["pair_count"], 0)

    def test_unavailable_copy_does_not_hide_accessible_result(self):
        rows = [
            self.row("arxiv", "https://arxiv.org/abs/2205.14135v2", "FlashAttention GPU memory efficient attention",
                     access="access_blocked"),
            self.row("arxiv", "https://arxiv.org/abs/2205.14135v1", "FlashAttention",
                     access="metadata")]
        result = w.rank_results(self.plan, [{"results": rows}])
        self.assertEqual(len(result["shortlist"]), 1)
        self.assertEqual(result["shortlist"][0]["access"], "metadata")
        self.assertEqual(result["shortlist"][0]["observations"], 2)

    def test_distinct_alternative_is_searchable_within_default_budget(self):
        rows = [row for row in self.plan["queries"] if row["stage"] == "alternatives"]
        self.assertIn("github_repositories", {row["source"] for row in rows})
        self.assertIn("crossref", {row["source"] for row in rows})
        self.assertTrue(any("block sparse attention" in row["query"] for row in rows))

    def test_linked_followup_preserves_alternative_paper_without_displacing_top_rank(self):
        code = self.row("github_repositories", "https://github.com/Dao-AILab/flash-attention",
                        "FlashAttention efficient attention", access="read",
                        links=[{"url": "https://arxiv.org/abs/2205.14135", "relation": "implements", "basis": "read"}])
        paper = self.row("arxiv", "https://arxiv.org/abs/2205.14135", "FlashAttention attention")
        report = w.rank_results(self.plan, [{"results": [code, paper]}], 1)
        self.assertEqual(len(report["shortlist"]), 1)
        self.assertEqual(len(report["linked_followups"]), 1)
        self.assertNotEqual(report["linked_followups"][0]["id"], report["shortlist"][0]["id"])
        self.assertTrue(report["linked_followups"][0]["review_required"])

    def test_rank_modes_and_graph_nodes(self):
        code = self.row("github_repositories", "https://github.com/Dao-AILab/flash-attention",
                        "FlashAttention efficient attention", access="read",
                        links=[{"url": "https://arxiv.org/abs/2205.14135", "relation": "implements", "basis": "read"}])
        paper = self.row("arxiv", "https://arxiv.org/abs/2205.14135", "FlashAttention efficient attention")
        for mode in ("bm25", "facet"):
            report = w.rank_results(self.plan, [{"results": [code, paper]}], 2, mode)
            self.assertEqual(report["ranking"], mode)
            self.assertEqual(len(report["evidence_graph"]["nodes"]), 2)
            self.assertTrue(all(row["bm25_score"] > 0 for row in report["shortlist"]))
        with self.assertRaises(w.WorkflowError):
            w.rank_results(self.plan, [{"results": []}], 2, "unknown")

    def test_nonlexical_linked_implementation_is_visible_not_ranked(self):
        paper = self.row("arxiv", "https://arxiv.org/abs/2205.14135",
                         "FlashAttention memory efficient attention", access="read",
                         links=[{"url": "https://github.com/example/xyz", "relation": "mentions", "basis": "read"}])
        code = self.row("github_repositories", "https://github.com/example/xyz", "xyz")
        report = w.rank_results(self.plan, [{"results": [paper, code]}], 2)
        self.assertEqual(len(report["shortlist"]), 1)
        self.assertEqual(report["linked_followups"][0]["url"], "https://github.com/example/xyz")
        self.assertEqual(report["evidence_graph"]["pair_count"], 0)
        self.assertEqual(len(report["evidence_graph"]["nodes"]), 2)

    def test_conflicting_transitive_aliases_are_not_silently_merged(self):
        a = self.row("arxiv", "https://arxiv.org/abs/2205.14135", "FlashAttention",
                     doi="10.1000/example")
        b = self.row("arxiv", "https://arxiv.org/abs/2307.08691", "FlashAttention 2",
                     doi="10.1000/example")
        c = self.row("crossref", "https://doi.org/10.1000/example", "Attention")
        report = w.rank_results(self.plan, [{"results": [a, b, c]}], 5)
        self.assertEqual(report["identity_conflicts"], 1)
        self.assertEqual(report["unique_identities"], 3)
        self.assertGreaterEqual(report["evidence_graph"]["ambiguous_aliases"], 1)

    def test_fusion_deterministic_and_abstains_on_component_only(self):
        rows = [self.row("arxiv", "https://arxiv.org/abs/2205.14135", "FlashAttention efficient attention"),
                self.row("github_repositories", "https://github.com/example/attention", "block sparse attention"),
                self.row("github_repositories", "https://github.com/example/torch", "PyTorch")]
        a = w.rank_results(self.plan, [{"results": rows}], 3, "fusion")
        b = w.rank_results(self.plan, [{"results": list(reversed(rows))}], 3, "fusion")
        self.assertEqual(a, b)
        self.assertEqual(len(a["shortlist"]), 2)
        self.assertTrue(all(row["fusion_score"] > 0 for row in a["shortlist"]))

    def test_paired_ranking_only_promotes_explicit_relationship(self):
        paper = self.row("arxiv", "https://arxiv.org/abs/2205.14135",
                         "FlashAttention memory efficient attention", access="read",
                         links=[{"url": "https://github.com/example/xyz", "relation": "implements", "basis": "read"},
                                {"url": "https://github.com/example/abc", "relation": "mentions", "basis": "read"}])
        code = self.row("github_repositories", "https://github.com/example/xyz", "xyz")
        mention = self.row("github_repositories", "https://github.com/example/abc", "abc")
        report = w.rank_results(self.plan, [{"results": [paper, code, mention]}], 3, "paired")
        self.assertEqual(len(report["shortlist"]), 2)
        linked = report["shortlist"][1]
        self.assertTrue(linked["linked_only"])
        self.assertEqual(linked["url"], code["url"])
        self.assertTrue(linked["review_required"])
        self.assertIn(mention["url"], {r["url"] for r in report["linked_followups"]})

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
