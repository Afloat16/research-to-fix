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

    def test_coverage_first_round_covers_six_stages_and_preserves_old_session(self):
        legacy = s.start(PROBLEM)
        self.assertNotIn("selection_strategy", legacy)
        self.assertEqual(s.next_round(legacy, budget=6)["selected_queries"],
                         w.make_plan(PROBLEM, w.MAX_QUERIES)["queries"][:6])
        state = s.start(PROBLEM, 12, 3, "coverage")
        first = s.next_round(state, budget=6)
        self.assertEqual({row["stage"] for row in first["selected_queries"]}, set(w.STAGES))
        self.assertEqual(first, s.next_round(copy.deepcopy(state), budget=6))
        with self.assertRaises(w.WorkflowError):
            s.append(legacy, first, [{"results": []}])
        statuses = [{"query_id": row["id"], "status": "completed"}
                    for row in first["selected_queries"]]
        state = s.append(state, first, [{"searches": statuses}])
        self.assertEqual(state["selection_strategy"], "coverage")
        second = s.next_round(state, budget=6)
        self.assertEqual(len(second["query_ids"]), 6)
        self.assertFalse({s.signature(q) for q in first["selected_queries"]} &
                         {s.signature(q) for q in second["selected_queries"]})

    def test_coverage_uses_clean_completion_and_transport_fallback(self):
        def q(id, stage, family, source, provider):
            return {"id": id, "stage": stage, "family": family, "source": source, "provider": provider}
        old = q("Q01", "mechanism", "paper", "arxiv", "arxiv")
        same = q("Q02", "mechanism", "paper", "arxiv", "arxiv")
        fallback = q("Q03", "mechanism", "paper", "crossref", "crossref")
        other = q("Q04", "verification", "code", "github_prs", "github_prs")
        state = {"rounds": [{"plan": {"queries": [old, other]}, "query_ids": ["Q01", "Q04"],
                             "payloads": [{"searches": [{"query_id": "Q01", "status": "rate_limited"},
                                                        {"query_id": "Q04", "status": "completed"}]}]}]}
        self.assertEqual(s.coverage_selection(state, [same, fallback], 1), [fallback])
        # Contradictory statuses are not treated as a clean completion.
        state["rounds"][0]["payloads"].append({"searches": [{"query_id": "Q01", "status": "completed"}]})
        self.assertEqual(s.coverage_selection(state, [same, fallback], 1), [fallback])
        with self.assertRaises(w.WorkflowError):
            s.start(PROBLEM, strategy="unknown")

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
