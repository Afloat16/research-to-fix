"""Network adapter contract tests with fixed, synthetic responses; no external calls."""
import json
from pathlib import Path
import sys
import unittest
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "research-to-fix" / "scripts"))
import research_workflow as w
import public_discovery as d
from test_research_workflow import PROBLEM


def encoded(value):
    return json.dumps(value).encode()


class DiscoveryTests(unittest.TestCase):
    def test_approval_and_tampered_plan_fail_before_transport(self):
        plan = w.make_plan(PROBLEM)
        calls = []
        def transport(url, provider):
            calls.append(url)
            raise AssertionError("must not call")
        with self.assertRaises(w.WorkflowError):
            d.discover(plan, transport=transport)
        plan["queries"][0]["native_query"] = "unapproved"
        with self.assertRaises(w.WorkflowError):
            d.discover(plan, True, transport=transport)
        self.assertEqual(calls, [])

    def test_fixed_endpoints_limits_and_metadata_only(self):
        plan = w.make_plan(PROBLEM, 12)
        calls = []
        def transport(url, provider):
            calls.append((url, provider))
            self.assertTrue(url.startswith(d.API[provider] + "?"))
            if provider == "github_repositories":
                return encoded({"items": [
                    {"full_name": "Dao-AILab/flash-attention", "html_url": "https://github.com/Dao-AILab/flash-attention",
                     "description": "Fast memory efficient attention", "private": False,
                     "archived": False, "default_branch": "main", "license": {"spdx_id": "BSD-3-Clause"}},
                    {"full_name": "private/repo", "html_url": "https://github.com/private/repo", "private": True}]})
            if provider == "arxiv":
                return b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2205.14135v2</id><title>FlashAttention</title><summary>memory efficient attention</summary></entry></feed>'
            if provider == "crossref":
                return encoded({"message": {"items": [{"DOI": "10.1000/flash", "title": ["Efficient attention"], "type": "posted-content"}]}})
            if provider.startswith("github"):
                return encoded({"items": [], "incomplete_results": True})
            return encoded([])
        report = d.discover(plan, True, 4, 5, transport=transport)
        self.assertEqual(report["requests"], 4)
        self.assertEqual(len(calls), 4)
        self.assertEqual({row["access"] for row in report["results"]}, {"metadata"})
        self.assertTrue(report["host_required_queries"])
        self.assertFalse(report["complete"])
        self.assertNotIn("private/repo", json.dumps(report))
        self.assertIn("partial", {row["status"] for row in report["searches"]})
        triage = w.rank_results(plan, [report])
        self.assertEqual({row["family"] for row in triage["shortlist"]}, {"paper", "code"})
        self.assertTrue(triage["needs_original_review"])

    def test_rate_limit_stops_github_group_and_keeps_other_providers(self):
        plan = w.make_plan(PROBLEM, 12)
        calls = []
        def transport(url, provider):
            calls.append(provider)
            if provider.startswith("github"):
                raise d.ProviderError("rate_limited")
            if provider == "arxiv":
                return b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
            if provider == "crossref":
                return encoded({"message": {"items": []}})
            return encoded([])
        report = d.discover(plan, True, 8, transport=transport)
        self.assertEqual(sum(provider.startswith("github") for provider in calls), 1)
        self.assertIn("crossref", calls)
        self.assertIn("arxiv", calls)
        self.assertIn("rate_limited", {row["status"] for row in report["searches"]})
        self.assertIn("skipped_budget", {row["status"] for row in report["searches"]})

    def test_reject_malformed_and_xml_entities(self):
        q = next(row for row in w.make_plan(PROBLEM)["queries"] if row["provider"] == "arxiv")
        for raw in (b'<!DOCTYPE x [<!ENTITY x "a">]><x>&x;</x>', b"<bad>", b"\xff", b""):
            with self.subTest(raw=raw), self.assertRaises(d.ProviderError):
                d.parse_response(q, raw, 5)
        q = next(row for row in w.make_plan(PROBLEM)["queries"] if row["provider"] == "crossref")
        for raw in (b'{"message":{"items":[],"items":[]}}', b'{"message":[]}', b"[]"):
            with self.assertRaises(d.ProviderError):
                d.parse_response(q, raw, 5)

    def test_request_qualifiers_and_no_redirect(self):
        plan = w.make_plan(dict(PROBLEM, repo="pytorch/pytorch"))
        row = next(row for row in plan["queries"] if row["provider"] == "github_issues")
        parsed = urlsplit(d.make_request(row, 7))
        self.assertEqual(parsed.hostname, "api.github.com")
        self.assertIn("repo:pytorch/pytorch", parse_qs(parsed.query)["q"][0])
        self.assertEqual(parse_qs(parsed.query)["per_page"], ["7"])
        with self.assertRaises(d.ProviderError):
            d.NoRedirect().redirect_request(None, None, 302, "", {}, "http://localhost/")
        with self.assertRaises(d.ProviderError):
            d.request_metadata("https://example.org/?q=x", "crossref")

    def test_archived_public_author_code_is_not_silently_lost(self):
        row = next(row for row in w.make_plan(PROBLEM)["queries"] if row["provider"] == "github_repositories")
        self.assertNotIn("archived:false", row["native_query"])
        result, _ = d.parse_github(row, {"items": [{"html_url": "https://github.com/google-research/simclr",
                                                    "full_name": "google-research/simclr",
                                                    "description": "Visual representations",
                                                    "private": False, "archived": True}]}, 1)
        self.assertEqual(len(result), 1)
        self.assertIn("archived", result[0]["maintenance_hint"])

    def test_public_credential_like_excerpts_are_not_retained(self):
        row = next(row for row in w.make_plan(PROBLEM)["queries"] if row["provider"] == "github_issues")
        result, _ = d.parse_github(row, {"items": [{"html_url": "https://github.com/a/b/issues/1",
                                                    "title": "Attention problem", "body": "password=private-demo",
                                                    "state": "open"}]}, 1)
        self.assertEqual(result[0]["snippet"], "")
        self.assertNotIn("private-demo", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
