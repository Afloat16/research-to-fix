import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
from independent_data import nasa_records
from independent_retrieval import partition, paired_interval


class IndependentProtocolTests(unittest.TestCase):
    def test_partition_is_disjoint_stable_and_complete(self):
        q = [{"id": str(i)} for i in range(876)]
        a, b = partition(q, "development"), partition(q, "holdout")
        self.assertEqual(len(a) + len(b), len(q))
        self.assertFalse({x["id"] for x in a} & {x["id"] for x in b})
        self.assertEqual(a, partition(q, "development"))
        self.assertEqual(partition(q, "all"), q)

    def test_nasa_ignores_query_metadata_and_prefixes_ids(self):
        docs, questions, pairs = nasa_records(
            [{"_id": "1", "name": "Repo", "text": "README", "additional_context": "ignore"}],
            [{"_id": "1", "text": "question", "metadata": {"url": "gold"}}],
            [b"query-id\tcorpus-id\tscore\n1\t1\t1\n1\t1\t1\n"])
        self.assertEqual(docs, [{"_id": "1", "title": "Repo", "text": "README"}])
        self.assertEqual(questions, [{"_id": "query:1", "text": "question"}])
        self.assertEqual(pairs, {("query:1", "1")})

    def test_paired_constant_interval(self):
        result = paired_interval([0.75] * 10, [0.5] * 10, resamples=100)
        self.assertEqual(result["ci95_low"], .25)
        self.assertEqual(result["ci95_high"], .25)
        self.assertEqual(result["win"], 10)
