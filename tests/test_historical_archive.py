import json
from pathlib import Path
import sys
import unittest
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import public_discovery as d
import research_workflow as w
from test_comprehensive_plan import PROBLEM


class HistoricalArchiveTests(unittest.TestCase):
    def test_fixed_exact_filter_fallback_and_license_provenance(self):
        plan = w.make_plan(PROBLEM, 1, ["paperswithcode"], "comprehensive")
        calls = []
        def transport(url, provider):
            calls.append(provider)
            if provider == "paperswithcode_detail":
                raise d.ProviderError("unavailable")
            parsed = urlsplit(url)
            self.assertEqual(parsed.netloc, "datasets-server.huggingface.co")
            self.assertEqual(parse_qs(parsed.query)["where"], ['"paper_arxiv_id"=\'1705.04932\''])
            return json.dumps({"rows": [{"row": {
                "paper_arxiv_id": "1705.04932", "paper_title": "Efficient attention memory",
                "repo_url": "https://github.com/example/old", "is_official": True}}]}).encode()
        result = d.resolve_papers(plan, ["1705.04932"], plan["queries"][0]["id"], True,
                                  transport=transport, archive_fallback=True)
        self.assertEqual(calls, ["paperswithcode_detail", "pwc_archive"])
        self.assertEqual(result["requests"], 2)
        self.assertTrue(result["complete"])
        self.assertEqual({row["origin"] for row in result["results"]}, {"pwc_archive"})
        self.assertTrue(all(row["catalog_license"] == "CC-BY-SA-4.0" for row in result["results"]))
        report = w.rank_results(plan, [result])
        self.assertTrue(report["shortlist"])
        self.assertEqual(report["shortlist"][0]["provenance"][0]["catalog_snapshot"], "2025-07-28")
        self.assertEqual(result["searches"], [])

    def test_no_fallback_without_opt_in_and_budget_respected(self):
        plan = w.make_plan(PROBLEM, 1, ["paperswithcode"], "comprehensive")
        calls = []
        def transport(url, provider):
            calls.append(provider)
            raise d.ProviderError("unavailable")
        q = plan["queries"][0]["id"]
        result = d.resolve_papers(plan, ["1705.04932"], q, True, transport=transport)
        self.assertEqual(calls, ["paperswithcode_detail"])
        self.assertFalse(result["complete"])
        calls.clear()
        result = d.resolve_papers(plan, ["1705.04932"], q, True, transport=transport,
                                  archive_fallback=True, max_requests=1)
        self.assertEqual(calls, ["paperswithcode_detail"])
        self.assertEqual(result["lookups"][1]["status"], "skipped_budget")


if __name__ == "__main__":
    unittest.main()
