import importlib.util
from pathlib import Path
import unittest


class ExactTopKTests(unittest.TestCase):
    def test_all_methods_match_integer_oracle(self):
        path = Path(__file__).resolve().parents[1] / "examples/exact-topk/compare_methods.py"
        spec = importlib.util.spec_from_file_location("r2f_exact_topk", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        vectors, query = module.inputs(11)
        expected = module.oracle(vectors, query, module.K)
        for name, method in module.METHODS.items():
            with self.subTest(method=name):
                self.assertEqual(method(vectors, query, module.K), expected)
                self.assertTrue(module.regression(method))


if __name__ == "__main__":
    unittest.main()
