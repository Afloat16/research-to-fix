"""Round binding, cross-round provenance and saturation behavior."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import research_workflow as w
import research_session as session
from test_comprehensive_plan import PROBLEM


def make_round(problem, source, url, title, **extra):
    plan = w.make_plan(problem, 2, [source], "comprehensive")
    qid = plan["queries"][0]["id"]
    return {"plan": plan, "inputs": [{"plan_id": plan["plan_id"],
            "results": [dict(query_id=qid, url=url, title=title, **extra)],
            "searches": [{"query_id": qid, "status": "completed"}]}]}


class ResearchSessionTests(unittest.TestCase):
    def test_cross_round_dedup_and_query_namespace(self):
        a = make_round(PROBLEM, "arxiv", "https://arxiv.org/abs/2205.14135v1",
                       "memory efficient exact attention", doi="10.1234/test")
        b = make_round(PROBLEM, "crossref", "https://doi.org/10.1234/test",
                       "memory efficient exact attention")
        c = make_round(PROBLEM, "github_repositories", "https://github.com/a/b",
                       "memory efficient exact attention")
        report = session.aggregate([a, b, c])
        self.assertEqual(report["unique_queries"], 3)
        self.assertEqual(report["attempted_queries"], 3)
        self.assertEqual([row["first_seen_identities"] for row in report["rounds"]], [1, 0, 1])
        self.assertEqual(report["triage"]["duplicates_collapsed"], 1)
        paper = next(row for row in report["triage"]["shortlist"] if row["family"] == "paper")
        self.assertEqual({row["query_id"] for row in paper["provenance"]}, {"R01-Q01", "R02-Q01"})
        self.assertEqual(report["suggested_action"], "read_and_verify_originals")

    def test_reject_wrong_binding_or_changed_intent(self):
        a = make_round(PROBLEM, "arxiv", "https://arxiv.org/abs/2205.14135", "attention")
        b = make_round(dict(PROBLEM, component="other"), "crossref", "https://doi.org/10.1234/test",
                       "attention")
        with self.assertRaises(w.WorkflowError):
            session.aggregate([a, b])
        bad = copy.deepcopy(a)
        bad["inputs"][0]["plan_id"] = "not-the-plan"
        with self.assertRaises(w.WorkflowError):
            session.aggregate([bad])
        with self.assertRaises(w.WorkflowError):
            session.aggregate([a, a])

    def test_rounds_distinguish_saturation_from_nonattempts(self):
        a = make_round(PROBLEM, "arxiv", "https://arxiv.org/abs/2205.14135", "attention")
        b = make_round(PROBLEM, "openalex", "https://arxiv.org/abs/2205.14135v2", "attention")
        c = make_round(PROBLEM, "crossref", "https://arxiv.org/pdf/2205.14135.pdf", "attention")
        self.assertTrue(session.aggregate([a,b,c])["two_round_novelty_saturation"])
        c["inputs"][0]["searches"][0]["status"] = "skipped_budget"
        self.assertFalse(session.aggregate([a,b,c])["two_round_novelty_saturation"])

    def test_repeated_query_definitions_count_once(self):
        a = make_round(PROBLEM, "arxiv", "https://arxiv.org/abs/2205.14135", "attention")
        plan = w.make_plan(PROBLEM, 3, ["arxiv", "crossref"], "comprehensive")
        b = {"plan": plan, "inputs": [{"plan_id": plan["plan_id"], "results": [],
                "searches": [{"query_id": plan["queries"][0]["id"], "status": "completed"}]}]}
        report = session.aggregate([a, b])
        self.assertGreaterEqual(report["rounds"][1]["repeated_query_definitions"], 1)
        self.assertEqual(report["attempted_queries"], 1)
        self.assertTrue(report["next_query_candidates"])


if __name__ == "__main__":
    unittest.main()
