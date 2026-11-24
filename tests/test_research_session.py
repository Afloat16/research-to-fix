import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "research-to-fix" / "scripts"))
import research_session as s
import research_workflow as w

PROBLEM = {"symptom": "attention memory grows", "task": "efficient attention",
           "concepts": ["memory efficient attention"], "alternative_concepts": ["tiled attention"]}


def payload(proposal, source="github_repositories", url="https://github.com/example/attention"):
    query = next(q for q in proposal["selected_queries"] if q["source"] == source)
    return {"plan_sha256": proposal["plan_sha256"],
            "results": [{"query_id": query["id"], "url": url, "title": "Memory efficient attention",
                         "kind": query["kind"], "access": "metadata"}],
            "searches": [{"query_id": query["id"], "status": "completed"}]}


class SessionTests(unittest.TestCase):
    def test_rounds_namespaced_and_no_repeat(self):
        state = s.start(PROBLEM, 12, 3)
        p1 = s.next_round(state, budget=4)
        original = copy.deepcopy(state)
        state = s.append(state, p1, [payload(p1)])
        self.assertEqual(original["rounds"], [])
        p2 = s.next_round(state, budget=5)
        self.assertFalse({s.signature(q) for q in p1["selected_queries"]} &
                         {s.signature(q) for q in p2["selected_queries"]})
        q = p2["selected_queries"][0]
        p = {"results": [{"query_id": q["id"], "url": "https://arxiv.org/abs/2205.14135",
                          "title": "Memory efficient attention", "kind": "paper", "access": "metadata"}],
             "searches": [{"query_id": q["id"], "status": "partial"}]}
        state = s.append(state, p2, [p])
        report = s.review(state)
        self.assertEqual(report["planned_distinct_queries"], 9)
        self.assertEqual(report["remaining_query_budget"], 3)
        self.assertEqual(report["attempted_queries"], 2)
        self.assertEqual(report["completed_queries"], 1)
        self.assertEqual({r["query_id"].split("-")[0] for r in report["triage"]["coverage"]}, {"R01", "R02"})
        self.assertEqual(report["triage"]["unique_identities"], 2)
        audit = report["triage"]["coverage_audit"]
        self.assertEqual(sum(row["planned_queries"] for row in audit["stages"]), 9)
        self.assertEqual(sum(row["attempted_queries"] for row in audit["stages"]), 2)
        self.assertEqual(sum(row["completed_queries"] for row in audit["stages"]), 1)
        self.assertEqual(sum(row["valid_observations"] for row in audit["stages"]), 2)

    def test_tampered_or_stale_proposal_and_mismatched_payload(self):
        state = s.start(PROBLEM)
        proposal = s.next_round(state, budget=4)
        bad = copy.deepcopy(proposal)
        bad["plan_sha256"] = "0" * 64
        with self.assertRaises(w.WorkflowError):
            s.append(state, bad, [payload(proposal)])
        bad_payload = payload(proposal)
        bad_payload["plan_sha256"] = "0" * 64
        with self.assertRaises(w.WorkflowError):
            s.append(state, proposal, [bad_payload])
        new = s.append(state, proposal, [payload(proposal)])
        with self.assertRaises(w.WorkflowError):
            s.append(new, proposal, [payload(proposal)])

    def test_bounds_and_anchor(self):
        state = s.start(PROBLEM, 3, 1)
        p = s.next_round(state, budget=12)
        self.assertEqual(len(p["query_ids"]), 3)
        state = s.append(state, p, [payload(p)])
        with self.assertRaises(w.WorkflowError):
            s.next_round(state)
        with self.assertRaises(w.WorkflowError):
            s.next_round(s.start(PROBLEM), dict(PROBLEM, task="different"))
        with self.assertRaises(w.WorkflowError):
            s.start(PROBLEM, 65)

    def test_wrong_query_and_mismatched_plan_fail(self):
        state = s.start(PROBLEM)
        p = s.next_round(state, budget=1)
        data = payload(p)
        data["results"][0]["query_id"] = "Q24"
        with self.assertRaises(w.WorkflowError):
            s.append(state, p, [data])
        plan = w.make_plan(PROBLEM)
        with self.assertRaises(w.WorkflowError):
            w.rank_results(plan, [{"plan_sha256": "different", "results": []}])

    def test_conflicting_paper_identifiers_are_not_promoted(self):
        plan = w.make_plan(PROBLEM)
        qid = next(q["id"] for q in plan["queries"] if q["source"] == "arxiv")
        rows = [{"query_id": qid, "url": "https://arxiv.org/abs/2205.14135",
                 "arxiv_id": "2307.08691", "title": "Efficient attention"}]
        result = w.rank_results(plan, [{"results": rows}])
        self.assertEqual(result["skipped"], {"conflicting_arxiv": 1})
        self.assertEqual(result["shortlist"], [])


if __name__ == "__main__":
    unittest.main()
