import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("attention_demo", ROOT / "examples/exact-attention/compare_attention.py")
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


class AttentionTests(unittest.TestCase):
    def test_all_candidates_against_stable_reference(self):
        q, k, v = demo.sample(11)
        q, k, v = q[:7], k[:53], v[:53]
        expected = demo.oracle(q, k, v)
        for name, method in demo.METHODS.items():
            with self.subTest(name=name):
                self.assertLessEqual(demo.error(method(q, k, v), expected), demo.TOL)
                self.assertTrue(demo.regressions(method))

    def test_causal_and_partial_block(self):
        q, k, v = demo.sample(23)
        q, k, v = q[:29], k[:29], v[:29]
        expected = demo.oracle(q, k, v, True)
        for name, method in demo.METHODS.items():
            with self.subTest(name=name):
                self.assertLessEqual(demo.error(method(q, k, v, True), expected), demo.TOL)
                with self.assertRaises(ValueError):
                    method(q[:-1], k, v, True)


if __name__ == "__main__":
    unittest.main()
