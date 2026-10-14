import unittest
from metrics import summarize


class MetricsTests(unittest.TestCase):
    def test_list(self):
        self.assertEqual(summarize([1.0, 2.0, 6.0]), {"count": 3, "mean": 3.0})

    def test_stream(self):
        self.assertEqual(summarize(float(i) for i in [1, 2, 6]), {"count": 3, "mean": 3.0})

    def test_empty(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            summarize(iter(()))


if __name__ == '__main__':
    unittest.main()
