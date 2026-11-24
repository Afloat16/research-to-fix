import importlib.util
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
import discovery


class DiscoveryBenchmarkTests(unittest.TestCase):
    def test_metrics_preserve_complete_pair_and_coverage(self):
        values = discovery.metrics(["p", "x", "c"], {"p", "c"}, [["p", "c"]],
                                   {"p": "paper", "c": "code", "x": "paper"})
        self.assertEqual(values["recall"], 1.0)
        self.assertEqual(values["complete_pair_recall"], 1.0)
        self.assertEqual(values["paper_and_code"], 1.0)

    def test_numerical_repair_formulas_against_oracle(self):
        spec = importlib.util.spec_from_file_location("variance_demo",
                     ROOT / "examples" / "numerical-variance" / "compare_methods.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        values, expected = module.inputs(11)
        self.assertGreater(abs(module.naive(values) - expected) / expected, module.TOLERANCE)
        for key in ("centered", "online", "stdlib"):
            method = module.METHODS[key]
            self.assertLessEqual(abs(method(values) - expected) / expected, module.TOLERANCE)
            self.assertTrue(module.regressions(method))
