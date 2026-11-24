"""Exact paper-ID lookup preserves query provenance and never guesses identities."""
import json
from pathlib import Path
import sys
import unittest
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import public_discovery as d
import research_workflow as w
from test_comprehensive_plan import PROBLEM


class PaperLookupTests(unittest.TestCase):
    def setUp(self):
        self.plan = w.make_plan(PROBLEM, 1, ["paperswithcode"], "comprehensive")
        self.qid = self.plan["queries"][0]["id"]

    def test_explicit_ids_all_validated_before_network(self):
        calls = []
        def transport(url, provider):
            calls.append(url)
            raise AssertionError("no request expected")
        for ids in (["2205.14135", "https://example.org"], ["2205.14135", "2205.14135v2"],
                    ["../etc/passwd"], ["2205.14135?x=y"]):
            with self.assertRaises(w.WorkflowError):
                d.resolve_papers(self.plan, ids, self.qid, True, transport=transport)
        with self.assertRaises(w.WorkflowError):
            d.resolve_papers(self.plan, ["2205.14135"], self.qid, False, transport=transport)
        self.assertEqual(calls, [])

    def test_exact_identity_links_and_no_fabricated_search_status(self):
        def transport(url, provider):
            self.assertEqual(provider, "paperswithcode_detail")
            self.assertEqual(urlsplit(url).netloc, "paperswithcode.co")
            self.assertEqual(urlsplit(url).path, "/api/v1/papers/arxiv/2205.14135")
            return json.dumps({"arxiv_id": "2205.14135", "title": "memory efficient attention",
                               "repositories": [{"url": "https://github.com/Dao-AILab/flash-attention",
                                                 "is_official": True}]}).encode()
        result = d.resolve_papers(self.plan, ["2205.14135v2"], self.qid, True, transport=transport)
        self.assertEqual(result["requests"], 1)
        self.assertEqual(result["lookups"][0]["status"], "completed")
        self.assertEqual(result["searches"], [])
        self.assertEqual(result["plan_id"], self.plan["plan_id"])
        self.assertEqual({row["kind"] for row in result["results"]}, {"paper", "repository"})
        report = w.rank_results(self.plan, [result])
        self.assertEqual(report["evidence_graph"]["pair_count"], 2)
        self.assertEqual(report["unrecorded_queries"], [self.qid])

    def test_wrong_identity_and_rate_limit(self):
        result = d.resolve_papers(self.plan, ["2205.14135"], self.qid, True,
                                  transport=lambda *_: b'{"arxiv_id":"2307.08691","title":"other"}')
        self.assertEqual(result["lookups"][0]["status"], "invalid_response")
        self.assertEqual(result["results"], [])
        def throttle(*_):
            raise d.ProviderError("rate_limited")
        report = d.resolve_papers(self.plan, ["2205.14135", "2307.08691"], self.qid, True, transport=throttle)
        self.assertEqual(report["requests"], 1)
        self.assertEqual(report["lookups"][1]["status"], "skipped_budget")


if __name__ == "__main__":
    unittest.main()
