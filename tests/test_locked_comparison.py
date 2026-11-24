"""Practical margins, locked comparisons and evidence eligibility."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import solution_compare as sc
import research_workflow as w
from test_solution_compare import fixture


def locked():
    value = fixture()
    value["schema_version"] = 2
    spec = value["protocol"]
    spec["minimum_replicates"] = 3
    spec["dominance_mode"] = "paired_conservative"
    spec["objectives"][0]["minimum_improvement"] = .1
    spec["objectives"][1]["minimum_improvement"] = .01
    lock = sc.protocol_lock(spec)
    for row in value["candidates"]:
        row["variant_id"] = row["id"]
        row["protocol_sha256"] = lock["protocol_sha256"]
        if row["basis"] == "external":
            row.update(support_ids=["E1"], applicability="adapted", applicability_note="local code mapping",
                       license_status="not_copied", license_note="independent implementation")
        for run in row["runs"]:
            run["variant_id"] = row["id"]
    return value, lock


class LockedComparisonTests(unittest.TestCase):
    def test_requires_independently_retained_lock_and_exact_commands(self):
        value, lock = locked()
        with self.assertRaises(w.WorkflowError):
            sc.compare(value)
        self.assertTrue(sc.compare(value, lock)["protocol_lock_checked"])
        edited = copy.deepcopy(value)
        edited["protocol"]["command"] = "python  eval.py"
        with self.assertRaises(w.WorkflowError):
            sc.compare(edited, lock)
        value["candidates"][1]["runs"][0]["command"] = "python  eval.py"
        report = sc.compare(value, lock)
        fast = next(row for row in report["candidates"] if row["id"] == "fast")
        self.assertFalse(fast["comparable"])

    def test_external_support_and_variant_and_license_requirements(self):
        value, lock = locked()
        value["evidence"][0]["retraction_hint"] = "retracted"
        value["candidates"][2]["license_status"] = "unknown"
        value["candidates"][1]["runs"][0]["variant_id"] = "wrong"
        report = sc.compare(value, lock)
        by_id = {row["id"]: row for row in report["candidates"]}
        self.assertIn("supporting_source_retracted", by_id["accurate"]["reasons"])
        self.assertIn("license_not_cleared", by_id["accurate"]["reasons"])
        self.assertFalse(by_id["fast"]["comparable"])
        self.assertIsNone(report["selected_candidate"])

    def test_meaningless_difference_does_not_choose_winner(self):
        value, lock = locked()
        value["protocol"]["priority"] = ["latency", "accuracy"]
        for candidate in value["candidates"][1:]:
            for run in candidate["runs"]:
                run["metrics"] = {"latency": 3.01 if candidate["id"] == "accurate" else 3,
                                  "accuracy": .90}
        lock = sc.protocol_lock(value["protocol"])
        for candidate in value["candidates"]:
            candidate["protocol_sha256"] = lock["protocol_sha256"]
        report = sc.compare(value, lock)
        self.assertEqual(report["pareto_frontier"], ["accurate", "fast"])
        self.assertIsNone(report["selected_candidate"])

    def test_conservative_paired_dominance_retains_variable_candidate(self):
        value, lock = locked()
        for i, run in enumerate(value["candidates"][2]["runs"]):
            run["metrics"] = {"latency": 2 if i < 2 else 8, "accuracy": .95}
        report = sc.compare(value, lock)
        self.assertEqual(report["pareto_frontier"], ["accurate", "fast"])
        self.assertEqual(report["dominance_mode"], "paired_conservative")
        value["protocol"]["dominance_mode"] = "median"
        lock = sc.protocol_lock(value["protocol"])
        for candidate in value["candidates"]:
            candidate["protocol_sha256"] = lock["protocol_sha256"]
        self.assertEqual(sc.compare(value, lock)["pareto_frontier"], ["accurate"])

    def test_invalid_margin_and_minimum_replicates(self):
        value, _ = locked()
        value["protocol"]["objectives"][0]["minimum_improvement"] = -1
        with self.assertRaises(w.WorkflowError):
            sc.protocol_lock(value["protocol"])
        value, _ = locked()
        value["protocol"]["minimum_replicates"] = 4
        with self.assertRaises(w.WorkflowError):
            sc.protocol_lock(value["protocol"])


if __name__ == "__main__":
    unittest.main()
