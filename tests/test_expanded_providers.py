"""Documented public adapter response shapes; network calls are mocked."""
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import public_discovery as d
import research_workflow as w
from test_comprehensive_plan import PROBLEM


class ExpandedProviderTests(unittest.TestCase):
    def query(self, source):
        return w.make_plan(PROBLEM, 3, [source], "comprehensive")["queries"][0]

    def test_pwc_catalog_returns_paper_and_bounded_linked_code(self):
        q = self.query("paperswithcode")
        params = parse_qs(urlsplit(d.make_request(q, 5)).query)
        self.assertEqual(params["include_resources"], ["true"])
        self.assertEqual(params["has_code"], ["true"])
        rows, _ = d.parse_paperswithcode(q, {"results": [{
            "arxiv_id": "2205.14135", "title": "FlashAttention memory efficient exact attention",
            "abstract": "GPU memory efficient exact attention", "version": "v2",
            "repositories": [
                {"url": "https://github.com/Dao-AILab/flash-attention", "is_official": True},
                {"url": "https://github.com/Dao-AILab/flash-attention?utm_source=x"},
                {"url": "https://github.com/a/b/issues/1"},
                {"url": "http://localhost/"},
                {"url": "https://github.com/a/c"}]}]}, 5)
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["kind"] for row in rows}, {"paper", "repository"})
        self.assertTrue(all(row["access"] == "metadata" for row in rows))
        self.assertNotIn("localhost", json.dumps(rows))
        self.assertEqual(len(rows[0]["links"]), 2)

    def test_openalex_abstract_and_retraction(self):
        q = self.query("openalex")
        rows, _ = d.parse_openalex(q, {"results": [{
            "id": "https://openalex.org/W123", "doi": "https://doi.org/10.1234/demo",
            "title": "GPU memory efficient attention", "publication_year": 2024,
            "is_retracted": True, "abstract_inverted_index": {"efficient": [1], "memory": [0]},
            "primary_location": {"source": {"display_name": "Synthetic venue"}}}]}, 4)
        self.assertEqual(rows[0]["snippet"], "memory efficient")
        self.assertEqual(rows[0]["retraction_hint"], "retracted")
        self.assertEqual(rows[0]["year"], 2024)
        self.assertEqual(d.reconstruct_abstract({"x": [0], "y": [0]}), "")
        self.assertEqual(d.reconstruct_abstract({"x": [-1]}), "")
        self.assertEqual(d.reconstruct_abstract({"x": [999999999]}), "")
        plan = w.make_plan(PROBLEM, 3, ["openalex"], "comprehensive")
        report = w.rank_results(plan, [{"results": rows}])
        self.assertEqual(report["shortlist"], [])
        self.assertEqual(report["ranked"][0]["retraction_hint"], "retracted")

    def test_semantic_scholar_and_dblp_ids(self):
        q = self.query("semantic_scholar")
        rows, _ = d.parse_semantic_scholar(q, {"data": [{"title": "Exact attention",
            "externalIds": {"DOI": "10.1234/example", "ArXiv": "2205.14135"},
            "year": 2022, "venue": "Example", "url": "https://www.semanticscholar.org/paper/demo"}]}, 4)
        self.assertEqual(rows[0]["url"], "https://arxiv.org/abs/2205.14135")
        self.assertEqual(rows[0]["doi"], "10.1234/example")
        q = self.query("dblp")
        rows, _ = d.parse_dblp(q, {"result": {"hits": {"hit": [
            {"info": {"title": "Memory efficient attention", "doi": "10.1234/demo",
                      "venue": "Example", "year": "2023"}}]}}}, 3)
        self.assertEqual(rows[0]["year"], 2023)
        self.assertEqual(rows[0]["url"], "https://doi.org/10.1234/demo")

    def test_group_fairness_parallel_and_bound_plan(self):
        plan = w.make_plan(PROBLEM, 20, strategy="comprehensive")
        calls = []
        lock = threading.Lock()
        def transport(url, provider):
            with lock:
                calls.append(provider)
            if provider == "arxiv":
                return b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
            if provider.startswith("github"):
                return b'{"items":[]}'
            if provider == "crossref":
                return b'{"message":{"items":[]}}'
            if provider.startswith("huggingface"):
                return b'[]'
            if provider == "semantic_scholar":
                return b'{"data":[]}'
            if provider == "dblp":
                return b'{"result":{"hits":{}}}'
            return b'{"results":[]}'
        result = d.discover(plan, True, 8, transport=transport, workers=4)
        self.assertEqual(result["requests"], 8)
        self.assertEqual(len({d.GROUPS[p] for p in calls}), 8)
        self.assertEqual(result["plan_id"], w.plan_fingerprint(plan))
        self.assertTrue(all(row["status"] in ("completed", "skipped_budget") for row in result["searches"]))
        self.assertTrue(result["host_required_queries"])

if __name__ == "__main__":
    unittest.main()
