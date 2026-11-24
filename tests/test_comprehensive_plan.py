"""Versioned comprehensive research plans and stable source bindings."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import research_workflow as w

PROBLEM = {"task": "long sequence attention", "symptom": "GPU memory grows with sequence length",
           "component": "PyTorch", "concepts": ["memory efficient exact attention", "online softmax"],
           "alternative_concepts": ["block sparse attention"], "focus": "algorithm"}


class ComprehensivePlanTests(unittest.TestCase):
    def test_legacy_plan_remains_compatible(self):
        plan = w.make_plan(PROBLEM, 12)
        self.assertEqual(plan["schema_version"], 1)
        self.assertNotIn("paperswithcode", plan["requested_sources"])
        self.assertEqual(w.validate_plan(plan), plan)

    def test_comprehensive_plan_allocates_distinct_lanes(self):
        plan = w.make_plan(PROBLEM, 16, strategy="comprehensive")
        self.assertEqual(plan["schema_version"], 2)
        self.assertEqual(w.validate_plan(plan), plan)
        self.assertEqual([q["source"] for q in plan["queries"][:3]],
                         ["github_repositories", "paperswithcode", "arxiv"])
        self.assertIn("alternatives", {q["stage"] for q in plan["queries"]})
        self.assertIn("counterevidence", {q["stage"] for q in plan["queries"]})
        self.assertTrue({"openalex", "semantic_scholar", "dblp"}.issubset({q["source"] for q in plan["queries"]}))
        self.assertEqual(len({(q["source"], q["native_query"] or q["query"]) for q in plan["queries"]}), len(plan["queries"]))

    def test_focused_provider_queries_use_only_reviewed_short_phrases(self):
        plan = w.make_plan(PROBLEM, 20, strategy="focused")
        self.assertEqual(plan["schema_version"], 3)
        self.assertEqual(plan, w.validate_plan(plan))
        first = {row["source"]: row for row in reversed(plan["queries"])}
        self.assertEqual(first["paperswithcode"]["native_query"], PROBLEM["concepts"][1])
        self.assertEqual(first["arxiv"]["native_query"], PROBLEM["concepts"][0])
        self.assertEqual(first["openalex"]["native_query"], PROBLEM["alternative_concepts"][0])
        self.assertIn(PROBLEM["concepts"][1], first["github_repositories"]["native_query"])
        self.assertIn(PROBLEM["task"], first["paperswithcode"]["query"])
        self.assertNotEqual(plan["plan_id"], w.make_plan(PROBLEM, 20, strategy="comprehensive")["plan_id"])

    def test_versioned_plan_and_payload_binding(self):
        plan = w.make_plan(PROBLEM, 8, strategy="comprehensive")
        edited = copy.deepcopy(plan)
        edited["queries"][0]["native_query"] = "different"
        with self.assertRaises(w.WorkflowError):
            w.validate_plan(edited)
        with self.assertRaises(w.WorkflowError):
            w.rank_results(plan, [{"plan_id": "x", "results": []}])
        report = w.rank_results(plan, [{"plan_id": w.plan_fingerprint(plan), "results": []}])
        self.assertEqual(report["plan_id"], w.plan_fingerprint(plan))

    def test_filtered_new_sources_and_public_input(self):
        plan = w.make_plan(PROBLEM, 3, ["dblp", "openalex"], "comprehensive")
        self.assertEqual({q["source"] for q in plan["queries"]}, {"dblp", "openalex"})
        with self.assertRaises(w.WorkflowError):
            w.make_plan(PROBLEM, 3, ["openalex"])
        with self.assertRaises(w.WorkflowError):
            w.make_plan(dict(PROBLEM, symptom="/home/alice/private"), strategy="comprehensive")

if __name__ == "__main__":
    unittest.main()
