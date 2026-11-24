"""Search coverage is not relevance or absence of counterexamples."""
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "research-to-fix" / "scripts"))
import research_workflow as w


class CoverageAuditTests(unittest.TestCase):
    def test_stage_state_and_mixed_outcomes(self):
        stages = ["exact", "implementation", "alternatives", "counterevidence", "counterevidence", "verification"]
        queries = {f"Q{i}": {"source": "github_issues", "family": "code", "stage": stage}
                   for i, stage in enumerate(stages)}
        searches = {"Q0": ["completed"], "Q1": ["skipped_budget"], "Q2": ["partial"],
                    "Q3": ["completed", "rate_limited"], "Q4": ["completed"], "Q5": ["completed"]}
        returned = Counter({"Q0": 2, "Q2": 3, "Q3": 1})
        reads = Counter({"Q0": 1})
        coverage, audit = w.audit_search_coverage(queries, searches, returned, reads)
        rows = {row["stage"]: row for row in audit["stages"]}
        self.assertEqual(rows["exact"]["state"], "completed_with_valid_observations")
        self.assertEqual(rows["exact"]["read_observations"], 1)
        self.assertEqual(rows["mechanism"]["state"], "not_planned")
        self.assertEqual(rows["implementation"]["state"], "no_completion_recorded")
        self.assertEqual(rows["implementation"]["attempted_queries"], 0)
        self.assertEqual(rows["alternatives"]["state"], "no_completion_recorded")
        self.assertEqual(rows["counterevidence"]["state"], "partial_or_mixed")
        self.assertEqual(rows["counterevidence"]["completed_queries"], 2)
        self.assertEqual(rows["counterevidence"]["completed_query_ids_without_valid_observations"], ["Q4"])
        self.assertEqual(rows["verification"]["state"], "completed_no_valid_observations")
        self.assertEqual(audit["mixed_attempt_queries"], ["Q3"])
        self.assertEqual(audit["observations_without_completed_search"], ["Q2"])
        self.assertEqual(audit["stages_without_completed_search"], ["mechanism", "implementation", "alternatives"])
        self.assertEqual(len(coverage), 6)

    def test_actual_triage_distinguishes_invalid_results_and_unrecorded(self):
        problem = {"symptom": "attention memory grows", "task": "efficient attention",
                   "concepts": ["memory efficient attention"], "alternative_concepts": ["tiled attention"]}
        plan = w.make_plan(problem, 24)
        query = next(q for q in plan["queries"] if q["stage"] == "counterevidence")
        other = next(q for q in plan["queries"] if q["source"] == "github_repositories")
        report = w.rank_results(plan, [{"searches": [{"query_id": query["id"], "status": "completed"}],
            "results": [{"query_id": query["id"], "url": "http://127.0.0.1/private", "title": "Invalid source"},
                        {"query_id": other["id"], "url": "https://github.com/example/attention",
                         "title": "Memory efficient attention", "access": "read"}]}])
        coverage = {row["query_id"]: row for row in report["coverage"]}
        self.assertTrue(coverage[query["id"]]["completion_recorded"])
        self.assertEqual(coverage[query["id"]]["returned"], 0)
        self.assertEqual(coverage[other["id"]]["read_observations"], 1)
        self.assertFalse(coverage[other["id"]]["completion_recorded"])
        self.assertIn(other["id"], report["coverage_audit"]["observations_without_completed_search"])


if __name__ == "__main__":
    unittest.main()
