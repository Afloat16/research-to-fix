"""查询筛选、候选数量及公开检索词策略的回归测试。"""

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts/research_case.py"
SPEC = importlib.util.spec_from_file_location("research_case_query_tests", SCRIPT)
research_case = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research_case)


def run_cli(*arguments):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *arguments],
                          capture_output=True, text=True, timeout=10)


class QueryControlTests(unittest.TestCase):
    def test_defaults_keep_all_26_candidates_in_original_order(self):
        plan = research_case.make_queries("IndexError", "numpy", "2.0", ["boundary"])
        self.assertEqual([(query["source"], query["language"]) for query in plan["queries"]],
                         [(source, language) for source in research_case.SOURCE_IDS for language in ("en", "zh")])
        self.assertEqual(plan["total_candidates"], 26)
        self.assertFalse(plan["truncated"])
        self.assertTrue(plan["review_required"])

    def test_filters_preserve_first_requested_source_and_language_order(self):
        plan = research_case.make_queries("IndexError",
                                          source_filters=["labs", "github_issues", "labs", "openreview"],
                                          language_filters=["zh", "en", "zh"])
        self.assertEqual([(query["source"], query["language"]) for query in plan["queries"]],
                         [("labs", "zh"), ("labs", "en"), ("github_issues", "zh"),
                          ("github_issues", "en"), ("openreview", "zh"), ("openreview", "en")])
        self.assertEqual([query["id"] for query in plan["queries"]], [f"S{index}" for index in range(1, 7)])
        self.assertEqual(plan["total_candidates"], 6)

    def test_single_language_keeps_all_sources(self):
        plan = research_case.make_queries("IndexError", language_filters=["zh", "zh"])
        self.assertEqual([query["source"] for query in plan["queries"]], list(research_case.SOURCE_IDS))
        self.assertEqual({query["language"] for query in plan["queries"]}, {"zh"})
        self.assertEqual(plan["total_candidates"], 13)

    def test_limit_counts_candidates_after_deduplication_and_filtering(self):
        plan = research_case.make_queries("IndexError",
                                          source_filters=["github_prs", "github_issues", "github_prs"],
                                          language_filters=["zh", "en", "zh"], max_queries=3)
        self.assertEqual([(query["source"], query["language"]) for query in plan["queries"]],
                         [("github_prs", "zh"), ("github_prs", "en"), ("github_issues", "zh")])
        self.assertEqual([query["id"] for query in plan["queries"]], ["S1", "S2", "S3"])
        self.assertEqual(plan["total_candidates"], 4)
        self.assertTrue(plan["truncated"])

    def test_limit_at_or_above_available_count_does_not_claim_truncation(self):
        for limit in (2, 100):
            with self.subTest(limit=limit):
                plan = research_case.make_queries("IndexError", source_filters=["github_issues"], max_queries=limit)
                self.assertEqual(len(plan["queries"]), 2)
                self.assertEqual(plan["total_candidates"], 2)
                self.assertFalse(plan["truncated"])

    def test_repository_changes_only_github_site_paths(self):
        original = research_case.make_queries("IndexError", "numpy", "2.0", ["boundary"])
        scoped = research_case.make_queries("IndexError", "numpy", "2.0", ["boundary"],
                                            repository="Afloat16/research-to-fix")
        sites = {"github_issues": "site:github.com/Afloat16/research-to-fix/issues",
                 "github_prs": "site:github.com/Afloat16/research-to-fix/pull"}
        for before, after in zip(original["queries"], scoped["queries"]):
            with self.subTest(source=after["source"], language=after["language"]):
                expected = copy.deepcopy(before)
                if after["source"] in sites:
                    expected["query"] = before["query"].replace("site:github.com", sites[after["source"]], 1)
                self.assertEqual(after, expected)

    def test_repository_allows_public_style_names_without_network_lookup(self):
        for repository in ("owner/repo", "an-org/.github", "Owner/repo_name.v2"):
            with self.subTest(repository=repository):
                plan = research_case.make_queries("IndexError", source_filters=["github_issues"], repository=repository)
                self.assertIn(f"site:github.com/{repository}/issues ", plan["queries"][0]["query"])

    def test_invalid_repository_values_raise_without_echoing_input(self):
        for repository in ("", "https://github.com/owner/repo", "owner/repo extra", "../repo", "owner/..",
                           "owner/.", "owner/repo/extra", "owner/repo?query=value", "-owner/repo", "owner/repo\n"):
            with self.subTest(repository=repository):
                with self.assertRaises(ValueError) as raised:
                    research_case.make_queries("IndexError", repository=repository)
                if repository:
                    self.assertNotIn(repository, str(raised.exception))

    def test_invalid_limits_and_filters_raise_value_error(self):
        arguments = [{"max_queries": value} for value in (0, -1, True, 1.5, "2")]
        arguments += [{"source_filters": ["missing"]}, {"source_filters": [None]},
                      {"language_filters": ["other"]}, {"language_filters": [False]}]
        for argument in arguments:
            with self.subTest(argument=argument):
                with self.assertRaises(ValueError):
                    research_case.make_queries("IndexError", **argument)

    def test_blank_error_is_rejected_even_with_component_or_concepts(self):
        for error in ("", "   ", "\n\t"):
            with self.subTest(error=error):
                with self.assertRaises(ValueError):
                    research_case.make_queries(error, "numpy", concepts=["boundary"])

    def test_multiline_error_and_concepts_keep_normalized_queries(self):
        plan = research_case.make_queries("  RuntimeError:\n dtype mismatch ", " pytorch ", " 2.0 ",
                                          ["", " mixed\tprecision "], ["github_issues", "openreview"], ["en"])
        self.assertIn("pytorch 2.0 RuntimeError: dtype mismatch", plan["queries"][0]["query"])
        self.assertIn("pytorch mixed precision", plan["queries"][1]["query"])
        self.assertNotIn("RuntimeError", plan["queries"][1]["query"])


class SensitiveQueryInputTests(unittest.TestCase):
    def test_empty_search_text_remains_safe_for_unperformed_search_records(self):
        self.assertTrue(research_case.safe_search_input(["", "\n \t"]))

    def test_prefixed_fields_and_cli_options_are_rejected(self):
        values = ["DB_PASSWORD=demo-password", "AWS_SECRET_ACCESS_KEY=demo-secret-key",
                  "client_secret=demo-client-secret", "error: DB_PASSWORD=demo-password",
                  '{"DB_PASSWORD":"demo-password"}', "API key: demo-api-key", "access token=demo-token",
                  "--password demo-password", "--db-password=demo-password", "--client-secret 'demo-secret'",
                  "--api-key=demo-api-key", "--AWS_SECRET_ACCESS_KEY demo-secret-key",
                  "AWSAccessKeyId=demo-access-key", "clientSecret=demo-secret"]
        for value in values:
            with self.subTest(value=value):
                self.assertFalse(research_case.safe_search_input([value]))
                with self.assertRaises(ValueError) as raised:
                    research_case.make_queries(value)
                self.assertNotIn(value, str(raised.exception))

    def test_all_query_text_fields_use_the_same_sensitive_check(self):
        for argument in ({"error": "DB_PASSWORD=demo-password"}, {"component": "DB_PASSWORD=demo-password"},
                         {"version": "DB_PASSWORD=demo-password"}, {"concepts": ["DB_PASSWORD=demo-password"]},
                         {"repository": "owner/ghp_" + "a" * 36}):
            values = {"error": "IndexError", **argument}
            with self.subTest(field=next(iter(argument))):
                with self.assertRaises(ValueError) as raised:
                    research_case.make_queries(**values)
                self.assertIn("凭据", str(raised.exception))

    def test_decoded_url_keys_share_the_same_policy_in_query_and_fragment(self):
        fields = ("secret", "pwd", "authorization", "client_secret", "DB_PASSWORD", "AWS_SECRET_ACCESS_KEY",
                  "sig", "X-Amz-Credential", "X-Amz-Signature", "X-Amz-Security-Token", "X-Goog-Signature")
        for field in fields:
            encoded = f"%{ord(field[0]):02x}{field[1:]}"
            for key in (field, encoded):
                for separator in ("?", "#", "#/callback?"):
                    url = f"https://example.org/page{separator}{key}=demo-private-value"
                    with self.subTest(field=key, separator=separator):
                        self.assertFalse(research_case.public_url(url))
                        with self.assertRaises(ValueError):
                            research_case.make_queries(f"request failed at {url}")

    def test_non_http_uris_are_rejected_even_without_credentials(self):
        uris = ("file:///home/alice/private-project/config.json", "ssh://build-server/private-repo",
                "redis://cache/db", "s3://public-style-bucket/path", "git+ssh://example.org/repo",
                "FILE:///home/alice/config.json", "file:/home/alice/config.json",
                "mailto:demo@example.org", "data:text/plain,demo-value", "urn:example:resource")
        for uri in uris:
            with self.subTest(uri=uri):
                with self.assertRaises(ValueError) as raised:
                    research_case.make_queries(f"operation failed for {uri}; retry unavailable")
                self.assertNotIn(uri, str(raised.exception))

    def test_normal_errors_and_public_urls_are_still_allowed(self):
        values = ("password authentication failed", "tokenization mismatch", "API key missing",
                  "RuntimeError:dtype mismatch", "error in std::vector::at", "module:Symbol failed",
                  "tokenizer_parallelism=false", "--max-tokens 1024",
                  "https://openreview.net/forum?id=example", "https://github.com/owner/repo/issues/1",
                  "https://token.example.org:8443/docs", "https://api-key.example.org:443/docs",
                  "https://example.org/docs?version=2&api_version=1#installation")
        for value in values:
            with self.subTest(value=value):
                self.assertTrue(research_case.safe_search_input([value]))
                self.assertEqual(len(research_case.make_queries(value, source_filters=["github_issues"])["queries"]), 2)

    def test_case_url_and_query_checks_use_the_repaired_policy(self):
        case = research_case.new_case()
        case["searches"] = [{"id": "S1", "query": "IndexError", "source": "github_issues", "language": "en",
                             "searched_at": "2026-11-04", "status": "completed", "result_urls": ["https://example.org/issue/1"]}]
        case["evidence"] = [{"id": "E1", "url": "https://example.org/issue/1", "title": "Candidate issue",
                             "source": "github_issues", "access_status": "not_checked", "publication_status": "unknown",
                             "primary_status": "unknown", "published_at": "", "accessed_at": "", "revision": "", "author": "",
                             "outcome": "lead", "claim": "Candidate only", "relevance": "Similar symptom",
                             "limitations": [], "search_ids": ["S1"]}]
        self.assertEqual(research_case.validate_case(case), [])
        private_url = "https://example.org/issue/1?%73ecret=demo-private-value"
        mutations = (("searches", "query", "DB_PASSWORD=demo-password", "case.searches[0].query"),
                     ("searches", "result_urls", [private_url], "case.searches[0].result_urls"),
                     ("evidence", "url", private_url, "case.evidence[0].url"))
        for collection, field, value, path in mutations:
            candidate = copy.deepcopy(case)
            candidate[collection][0][field] = value
            with self.subTest(path=path):
                errors = research_case.validate_case(candidate)
                self.assertTrue(any(error.startswith(path + ":") for error in errors))
                self.assertNotIn("demo-private-value", "\n".join(errors))
                self.assertNotIn("demo-password", "\n".join(errors))


class QueryControlCliTests(unittest.TestCase):
    def test_cli_combines_filters_repository_and_limit(self):
        result = run_cli("queries", "--error", "IndexError", "--repo", "owner/repo",
                         "--source", "github_prs", "--source", "huggingface_forum", "--source", "github_prs",
                         "--language", "zh", "--language", "en", "--language", "zh", "--limit", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual([(query["source"], query["language"]) for query in plan["queries"]],
                         [("github_prs", "zh"), ("github_prs", "en"), ("huggingface_forum", "zh")])
        self.assertTrue(plan["queries"][0]["query"].startswith("site:github.com/owner/repo/pull "))
        self.assertTrue(plan["queries"][2]["query"].startswith("site:discuss.huggingface.co "))
        self.assertEqual(plan["total_candidates"], 4)
        self.assertTrue(plan["truncated"])

    def test_markdown_reports_candidate_count_and_truncation(self):
        result = run_cli("queries", "--error", "IndexError", "--source", "github_issues",
                         "--language", "zh", "--language", "en", "--limit", "1", "--format", "markdown")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("生成候选：1 / 2", result.stdout)
        self.assertIn("已按数量上限截断", result.stdout)
        self.assertIn("github_issues / zh", result.stdout)
        self.assertNotIn("github_issues / en", result.stdout)
        self.assertIn("不是实际联网预算", result.stdout)

    def test_cli_rejects_invalid_controls_without_echoing_arguments(self):
        arguments = (("--limit", "0"), ("--limit", "-1"), ("--limit", "invalid_limit_marker"),
                     ("--language", "invalid_language_marker"), ("--repo", "owner/invalid_repo_marker/extra"))
        for argument in arguments:
            with self.subTest(option=argument[0], value=argument[1]):
                result = run_cli("queries", "--error", "IndexError", *argument)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertNotIn(argument[1], result.stderr)

    def test_cli_rejects_blank_error(self):
        result = run_cli("queries", "--error", "\n \t", "--component", "numpy")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_rejected_secrets_and_uris_never_reach_json_or_markdown_output(self):
        arguments = (("--error", "DB_PASSWORD=demo-password-marker", "demo-password-marker"),
                     ("--error", "--password demo-option-marker", "demo-option-marker"),
                     ("--concept", "https://example.org/?%73ecret=demo-url-marker", "demo-url-marker"),
                     ("--error", "file:///home/alice/private-path-marker/config.json", "private-path-marker"),
                     ("--repo", "owner/ghp_" + "a" * 36, "ghp_" + "a" * 36))
        for output_format in ("json", "markdown"):
            for option, value, marker in arguments:
                with self.subTest(format=output_format, option=option, marker=marker):
                    result = run_cli("queries", "--error", "IndexError", f"{option}={value}", "--format", output_format)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    self.assertNotIn(value, result.stderr)
                    self.assertNotIn(marker, result.stderr)

    def test_query_help_explains_offline_uri_policy_and_new_options(self):
        result = run_cli("queries", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ("--language", "--limit", "--repo", "HTTP(S)", "离线公开检索词", "不是完整保证", "实际联网预算"):
            self.assertIn(text, result.stdout)


if __name__ == "__main__":
    unittest.main()
