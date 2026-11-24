import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "research-to-fix" / "scripts"))
import solution_compare as s
import research_workflow as w


def fixture():
    ctx = {"dataset": "fixed fixture", "hardware": "same CPU", "seed_schedule": "s1,s2,s3"}
    spec = {"id": "protocol1", "context": ctx, "command": "python eval.py",
            "replicates": ["s1", "s2", "s3"],
            "objectives": [{"id": "latency", "direction": "min", "unit": "ms"},
                           {"id": "accuracy", "direction": "max", "unit": "ratio", "threshold": .8}],
            "checks": [{"id": "original", "kind": "original", "description": "original behavior"},
                       {"id": "regression", "kind": "regression", "description": "retained checks"}]}
    def row(key, basis, latency, accuracy, original="pass"):
        return {"id": key, "title": key, "basis": basis, "state": "measured",
                "protocol_id": "protocol1", "context": dict(ctx),
                "mechanism": "test " + key, "local_target": "src.py:fn",
                "hypothesis": "expected outcome", "change": "change " + key,
                "evidence_ids": [] if basis != "external" else ["E1"],
                "runs": [{"replicate": rep, "command": "python eval.py", "observed": "fixture observation",
                          "metrics": {"latency": latency, "accuracy": accuracy},
                          "checks": {"original": original, "regression": "pass"}} for rep in spec["replicates"]]}
    return {"schema_version": 1, "protocol": spec,
            "evidence": [{"id": "E1", "url": "https://arxiv.org/abs/2205.14135",
                          "access": "read", "claim": "test evidence", "conditions": "conditions",
                          "limitations": "limitations"}],
            "candidates": [row("baseline", "baseline", 10, .85, "fail"),
                           row("fast", "local", 3, .88), row("accurate", "external", 6, .95)]}


class CompareTests(unittest.TestCase):
    def test_pareto_tradeoffs_not_false_winner(self):
        result = s.compare(fixture())
        self.assertEqual(result["pareto_frontier"], ["accurate", "fast"])
        self.assertIsNone(result["selected_candidate"])
        self.assertEqual(result["decision"], "tradeoffs_require_choice")
        fast = next(row for row in result["candidates"] if row["id"] == "fast")
        self.assertEqual(fast["paired_improvement"]["latency"]["median"], 7.0)
        self.assertEqual(fast["paired_improvement"]["latency"]["improved_pairs"], 3)

    def test_explicit_priority_and_unique_dominance(self):
        value = fixture()
        value["protocol"]["priority"] = ["latency", "accuracy"]
        self.assertEqual(s.compare(value)["selected_candidate"], "fast")
        value["protocol"]["priority"] = []
        for run in value["candidates"][2]["runs"]:
            run["metrics"]["latency"] = 2
        result = s.compare(value)
        self.assertEqual(result["selected_candidate"], "accurate")
        self.assertEqual(result["decision"], "unique_measured_frontier")

    def test_unknown_or_failed_checks_and_unread_evidence_excluded(self):
        value = fixture()
        value["evidence"][0]["access"] = "snippet_only"
        value["candidates"][1]["runs"][0]["checks"]["regression"] = "not_run"
        result = s.compare(value)
        self.assertIsNone(result["selected_candidate"])
        self.assertEqual(result["pareto_frontier"], [])
        by_id = {row["id"]: row for row in result["candidates"]}
        self.assertIn("original_evidence_not_read", by_id["accurate"]["reasons"])
        self.assertIn("hard_checks_not_passed", by_id["fast"]["reasons"])

    def test_missing_replicates_context_or_command_never_win(self):
        value = fixture()
        value["candidates"][1]["runs"].pop()
        value["candidates"][2]["context"]["dataset"] = "different"
        result = s.compare(value)
        self.assertEqual(result["pareto_frontier"], [])
        by_id = {row["id"]: row for row in result["candidates"]}
        self.assertFalse(by_id["accurate"]["comparable"])
        self.assertIn("missing_replicates", by_id["fast"]["reasons"])
        value = fixture()
        value["candidates"][0]["runs"][0]["command"] = "different"
        self.assertEqual(s.compare(value)["decision"], "baseline_not_comparable")

    def test_threshold_all_replicates_and_feasible_baseline(self):
        value = fixture()
        value["candidates"][1]["runs"][0]["metrics"]["accuracy"] = .79
        result = s.compare(value)
        self.assertEqual(result["selected_candidate"], "accurate")
        value = fixture()
        for run in value["candidates"][0]["runs"]:
            run["checks"]["original"] = "pass"
            run["metrics"] = {"latency": 1, "accuracy": .99}
        self.assertEqual(s.compare(value)["decision"], "baseline_preferred")

    def test_nonfinite_unknown_fields_duplicates_and_incomplete_priority(self):
        for bad in (float("nan"), float("inf"), True, "3", 10**500):
            value = fixture()
            value["candidates"][1]["runs"][0]["metrics"]["latency"] = bad
            with self.subTest(bad=type(bad)), self.assertRaises(w.WorkflowError):
                s.compare(value)
        value = fixture()
        value["candidates"][1]["runs"].append(copy.deepcopy(value["candidates"][1]["runs"][0]))
        with self.assertRaises(w.WorkflowError):
            s.compare(value)
        value = fixture()
        value["protocol"]["priority"] = ["latency"]
        with self.assertRaises(w.WorkflowError):
            s.compare(value)

    def test_unmeasured_options_never_selected(self):
        value = fixture()
        value["candidates"][1].update(state="planned", runs=[])
        value["candidates"][2].update(state="blocked", runs=[], blocker="no GPU")
        result = s.compare(value)
        self.assertIsNone(result["selected_candidate"])
        self.assertIn("unmeasured_options_remain", result["warnings"])


if __name__ == "__main__":
    unittest.main()
