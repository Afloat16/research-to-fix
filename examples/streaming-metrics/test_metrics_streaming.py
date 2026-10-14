import unittest

from metrics import summarize


class SingleUseIterable:
    def __init__(self, values):
        self.values = values
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.iterations > 1:
            raise AssertionError("input traversed more than once")
        return iter(self.values)


class StreamingMetricsTests(unittest.TestCase):
    def test_single_use_iterable(self):
        values = SingleUseIterable([0, -3, 6])
        self.assertEqual(summarize(values), {"count": 3, "mean": 1.0})
        self.assertEqual(values.iterations, 1)

    def test_empty_inputs(self):
        for values in ([], (x for x in ()), SingleUseIterable([])):
            with self.subTest(input_type=type(values).__name__):
                with self.assertRaisesRegex(ValueError, "empty"):
                    summarize(values)

    def test_builtin_sum_precision(self):
        values = [1e16, 1.0, -1e16]
        expected = {"count": 3, "mean": sum(values) / 3}
        for data in (values, iter(values)):
            with self.subTest(input_type=type(data).__name__):
                self.assertEqual(summarize(data), expected)


if __name__ == "__main__":
    unittest.main()
