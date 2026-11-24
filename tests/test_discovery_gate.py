"""Fixed relevance-gate failure modes."""
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
import discovery_gate as gate


class DiscoveryGateTests(unittest.TestCase):
    def report(self):
        metrics = {"recall": .921875, "mrr": 1., "paper_and_code": 1., "complete_pair_recall": .875}
        return {**gate.EXPECTED, "dataset_sha256": gate.EXPECTED_SHA,
                "methods": {name: {"overall": dict(metrics)} for name in
                            ("fixed_order", "stemmed_bm25", "sqlite_porter", "facet_rank", "evidence_shortlist")},
                "per_query": [{"unique_identities": 32, "duplicates_collapsed": 12} for _ in range(16)]}

    def test_pass_and_detect_regression(self):
        report = self.report()
        self.assertTrue(gate.check(report)["passed"])
        for value in (.5, float("nan"), True, 1.5):
            changed = copy.deepcopy(report)
            changed["methods"]["evidence_shortlist"]["overall"]["recall"] = value
            self.assertFalse(gate.check(changed)["passed"])
        report["per_query"][0]["duplicates_collapsed"] = 10
        self.assertFalse(gate.check(report)["passed"])

    def test_dataset_binding_and_missing_metrics(self):
        report = self.report()
        report["dataset_sha256"] = "wrong"
        del report["methods"]["sqlite_porter"]
        self.assertFalse(gate.check(report)["passed"])
        self.assertFalse(gate.check({})["passed"])


if __name__ == "__main__":
    unittest.main()
