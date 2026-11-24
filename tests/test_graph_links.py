"""Explicit graph links survive zero lexical overlap without promoting code."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import research_workflow as w
from test_comprehensive_plan import PROBLEM


class GraphLinksTests(unittest.TestCase):
    def test_opaque_code_link_is_review_followup_not_shortlist(self):
        plan = w.make_plan(PROBLEM, 1, ["paperswithcode"], "comprehensive")
        qid = plan["queries"][0]["id"]
        paper = {"query_id": qid, "url": "https://arxiv.org/abs/2205.14135",
                 "kind": "paper", "title": "memory efficient exact attention",
                 "access": "metadata", "links": [{"url": "https://github.com/xyz/abc",
                 "relation": "implements", "basis": "metadata"}]}
        code = {"query_id": qid, "url": "https://github.com/xyz/abc",
                "kind": "repository", "title": "xyz abc", "access": "metadata",
                "links": [{"url": paper["url"], "relation": "describes", "basis": "metadata"}]}
        rows = [paper, code]
        for ranking in ("bm25", "facet", "fusion"):
            report = w.rank_results(plan, [{"results": rows}], 6, ranking)
            self.assertEqual([x["url"] for x in report["shortlist"]], [paper["url"]])
            self.assertEqual(report["evidence_graph"]["pair_count"], 1)
            self.assertEqual(report["evidence_graph"]["paper_code_pairs"][0]["assertion_count"], 2)
            self.assertEqual(report["linked_followups"][0]["url"], code["url"])
            self.assertTrue(report["linked_followups"][0]["review_required"])
            self.assertEqual(report["evidence_graph"]["unresolved_count"], 0)


if __name__ == "__main__":
    unittest.main()
