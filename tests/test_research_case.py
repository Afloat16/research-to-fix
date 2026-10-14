"""覆盖安全边界、引用完整性及修复声明的关键条件。"""

import copy
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts/research_case.py"
SPEC = importlib.util.spec_from_file_location("research_case", SCRIPT)
research_case = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research_case)


def solved_case(kind="reproduction"):
    case = research_case.new_case()
    case["problem"]["summary"] = "相同维度输入导致索引失败"
    case["searches"] = [{"id": "S1", "query": "site:github.com IndexError",
                         "source": "github", "language": "en", "searched_at": "2026-10-13",
                         "status": "completed", "result_urls": ["https://github.com/example/project/issues/1"]}]
    case["evidence"] = [{"id": "E1", "url": "https://github.com/example/project/issues/1",
                         "title": "索引边界修复", "source": "github", "access_status": "read",
                         "publication_status": "discussion", "published_at": "2026-01-01",
                         "accessed_at": "2026-10-13", "revision": "", "author": "维护者示例", "outcome": "solved_report",
                         "primary_status": "primary", "claim": "维护者记录了边界条件",
                         "relevance": "同一组件和输入条件", "limitations": ["本地版本不同"],
                         "search_ids": ["S1"]}]
    case["mapping"] = [{"id": "M1", "evidence_ids": ["E1"], "local_path": "src/index.py",
                        "symbol": "lookup", "similarities": "同一索引边界", "differences": "版本不同",
                        "hypothesis": "上界应排除等长索引"}]
    case["experiments"] = [{"id": "X1", "mapping_ids": ["M1"], "evidence_ids": ["E1"],
                            "hypothesis": "上界条件导致失败", "change": "调整上界判断",
                            "commands": ["python reproduce.py"], "status": "supports"}]
    case["validation"] = {
        "status": "solved", "summary": "边界输入前失败后通过", "limitations": [],
        "runs": [
            {"id": "V1", "check_id": "boundary", "phase": "before", "kind": kind,
             "command": "python reproduce.py", "exit_code": 1 if kind != "benchmark" else 0,
             "result": "fail", "observed": "错误输出或指标低于阈值", "criteria": "正确率 >= 0.9" if kind == "benchmark" else "输出应为输入中对应索引的值",
             "evidence_ids": ["E1"]},
            {"id": "V2", "check_id": "boundary", "phase": "after", "kind": kind,
             "command": "python reproduce.py", "exit_code": 0, "result": "pass",
             "observed": "预期输出或指标达到阈值", "criteria": "正确率 >= 0.9" if kind == "benchmark" else "输出应为输入中对应索引的值", "evidence_ids": ["E1"]},
        ],
    }
    return case


class QuerySafetyTests(unittest.TestCase):
    def test_complete_bilingual_plan(self):
        plan = research_case.make_queries("IndexError", "numpy", "2.0", ["boundary"])
        sources = {query["source"] for query in plan["queries"]}
        self.assertTrue({"github_issues", "github_prs", "huggingface", "huggingface_forum", "zhihu", "xiaohongshu",
                         "openreview", "pmlr", "cvf", "acl", "journals", "scholars", "labs"} <= sources)
        self.assertEqual(len(plan["queries"]), 26)
        self.assertEqual({query["language"] for query in plan["queries"]}, {"en", "zh"})
        self.assertTrue(plan["review_required"])

    def test_repeated_source_filters_select_only_requested_candidates(self):
        plan = research_case.make_queries("IndexError", source_filters=["github_issues", "huggingface_forum"])
        self.assertEqual(len(plan["queries"]), 4)
        self.assertEqual({query["source"] for query in plan["queries"]}, {"github_issues", "huggingface_forum"})
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(research_case.main(["queries", "--error", "IndexError", "--source", "github_issues", "--source", "huggingface_forum"]), 0)
        self.assertEqual(len(json.loads(output.getvalue())["queries"]), 4)

    def test_papers_and_labs_use_mechanism_instead_of_full_error_and_version(self):
        plan = research_case.make_queries("UNIQUE_RuntimeError", "numpy", "2.3.99", ["boundary conditions"])
        for query in plan["queries"]:
            with self.subTest(source=query["source"]):
                if query["stage"] == "mechanism":
                    self.assertIn("boundary conditions", query["query"])
                    self.assertNotIn("UNIQUE_RuntimeError", query["query"])
                    self.assertNotIn("2.3.99", query["query"])
                else:
                    self.assertIn("UNIQUE_RuntimeError", query["query"])
                    self.assertIn("2.3.99", query["query"])
        fallback = research_case.make_queries("IndexError", "numpy")
        self.assertTrue(all("待人工改写" in query["note"] for query in fallback["queries"] if query["stage"] == "mechanism"))
        self.assertIn("候选", fallback["note"])

    def test_secrets_and_private_urls_are_rejected(self):
        inputs = ["ghp_" + "a" * 36, "hf_" + "b" * 30, "api_key=supersecret",
                  "token=supersecret", '{"api_key":"private-key"}', '{"token":"private-token"}',
                  "https://example.org/file?sig=private-signature", "https://example.org/file?%73ig=private-signature",
                  "https://example.org/file?%74oken=private-token", "endpoint 192.168.1.25", "host ::1",
                  "Authorization: Bearer secret", "https://user:pass@example.org/a",
                  "postgresql://user:demo-password@example.com/db", "mongodb+srv://user:demo-password@example.com/db",
                  "Server=example.com;User ID=demo;Pwd=demo-password;Database=test",
                  "http://127.0.0.1:8000/a", "https://10.1.2.3/a", "http://[::1]/a",
                  "https://worker.internal/a", "http://localhost/a"]
        for value in inputs:
            with self.subTest(value=value):
                with self.assertRaises(ValueError) as raised:
                    research_case.make_queries(value)
                self.assertNotIn(value, str(raised.exception))

    def test_urls_with_ambiguous_addresses_are_not_accepted(self):
        for url in ["http://2130706433/a", "http://127.1/a", "http://0x7f000001/a",
                    "http://example.org\\@localhost/a", "https://example.org:bad/a"]:
            with self.subTest(url=url):
                self.assertFalse(research_case.public_url(url))
        self.assertTrue(research_case.public_url("https://openreview.net/forum?id=example"))

    def test_cli_errors_never_echo_rejected_input(self):
        secret = "ghp_" + "a" * 36
        for arguments in [["queries", "--error", secret], ["queries", "--bogus", secret]]:
            result = subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(secret, result.stdout + result.stderr)

    def test_non_http_connection_credentials_are_never_echoed(self):
        connection = "postgresql://user:demo-password@example.com/db"
        result = subprocess.run([sys.executable, str(SCRIPT), "queries", "--error", connection], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(connection, result.stdout + result.stderr)
        self.assertNotIn("demo-password", result.stdout + result.stderr)


class EvidenceValidationTests(unittest.TestCase):
    def test_empty_blocked_template_is_valid(self):
        self.assertEqual(research_case.validate_case(research_case.new_case()), [])

    def test_solved_with_realistic_before_after_records_is_structurally_valid(self):
        self.assertEqual(research_case.validate_case(solved_case()), [])

    def test_benchmark_failure_can_have_zero_exit_code(self):
        self.assertEqual(research_case.validate_case(solved_case("benchmark")), [])
        case = solved_case("benchmark")
        del case["validation"]["runs"][0]["criteria"]
        self.assertTrue(research_case.validate_case(case))

    def test_changed_benchmark_target_cannot_claim_solved(self):
        case = solved_case("benchmark")
        case["validation"]["runs"][1]["criteria"] = "正确率 >= 0.1"
        self.assertTrue(research_case.validate_case(case))

    def test_after_only_pass_cannot_claim_solved(self):
        case = solved_case()
        case["validation"]["runs"] = case["validation"]["runs"][1:]
        self.assertTrue(research_case.validate_case(case))
        case["validation"]["status"] = "partial"
        self.assertEqual(research_case.validate_case(case), [])

    def test_unrelated_before_after_checks_cannot_claim_solved(self):
        case = solved_case()
        case["validation"]["runs"][1]["check_id"] = "different-symptom"
        self.assertTrue(research_case.validate_case(case))

    def test_different_after_command_cannot_claim_solved(self):
        case = solved_case()
        case["validation"]["runs"][1]["command"] = "python unrelated.py"
        self.assertTrue(research_case.validate_case(case))

    def test_every_original_problem_check_requires_an_after_pass(self):
        case = solved_case()
        extra = copy.deepcopy(case["validation"]["runs"][0])
        extra.update(id="V3", check_id="another-symptom")
        case["validation"]["runs"].append(extra)
        self.assertTrue(research_case.validate_case(case))

    def test_original_problem_criteria_is_required_and_cannot_change(self):
        for mutation in (None, "不同的宽松标准"):
            case = solved_case()
            case["validation"]["runs"][1]["criteria"] = mutation
            with self.subTest(mutation=mutation):
                self.assertTrue(research_case.validate_case(case))

    def test_local_code_inference_can_solve_without_claiming_external_evidence(self):
        case = solved_case()
        case["evidence"] = []
        case["mapping"][0].update(basis="local_code", evidence_ids=[])
        case["experiments"][0]["evidence_ids"] = []
        for run in case["validation"]["runs"]:
            run["evidence_ids"] = []
        self.assertEqual(research_case.validate_case(case), [])
        del case["mapping"][0]["basis"]
        self.assertTrue(research_case.validate_case(case))

    def test_executed_experiment_cannot_have_blank_commands(self):
        for commands in ([], [""], ["  "], ["python reproduce.py", ""]):
            case = solved_case()
            case["experiments"][0]["commands"] = commands
            with self.subTest(commands=commands):
                self.assertTrue(research_case.validate_case(case))

    def test_access_publication_outcome_and_search_statuses(self):
        for status in ("read", "snippet_only", "access_blocked", "unavailable", "accessible"):
            case = solved_case()
            case["evidence"][0]["access_status"] = status
            if status in {"snippet_only", "access_blocked", "unavailable"}:
                case["evidence"][0]["outcome"] = "lead"
            with self.subTest(access_status=status):
                self.assertEqual(research_case.validate_case(case), [])
        for status in ("submitted", "accepted", "not_applicable"):
            case = solved_case()
            case["evidence"][0]["publication_status"] = status
            with self.subTest(publication_status=status):
                self.assertEqual(research_case.validate_case(case), [])
        for status in ("not_relevant", "unavailable", "access_blocked", "planned", "completed", "blocked"):
            case = solved_case()
            case["searches"][0]["status"] = status
            with self.subTest(search_status=status):
                self.assertEqual(research_case.validate_case(case), [])
        for field in ("accessed_at", "revision", "outcome", "author"):
            case = solved_case()
            del case["evidence"][0][field]
            with self.subTest(field=field):
                self.assertTrue(research_case.validate_case(case))
        case = solved_case()
        case["evidence"][0]["accessed_at"] = ""
        self.assertTrue(research_case.validate_case(case))
        case["evidence"][0]["access_status"] = "snippet_only"
        case["evidence"][0]["outcome"] = "lead"
        self.assertEqual(research_case.validate_case(case), [])

    def test_unread_sources_cannot_claim_a_solution_or_viable_route(self):
        for access in ("snippet_only", "partial", "access_blocked", "unavailable", "inaccessible", "not_checked"):
            for outcome in ("solved_report", "viable_route"):
                case = solved_case()
                case["evidence"][0].update(access_status=access, outcome=outcome)
                with self.subTest(access=access, outcome=outcome):
                    self.assertTrue(research_case.validate_case(case))
            case["evidence"][0]["outcome"] = "lead"
            self.assertEqual(research_case.validate_case(case), [])

    def test_unit_test_alone_is_not_original_problem_reproduction(self):
        self.assertTrue(research_case.validate_case(solved_case("test")))

    def test_missing_execution_details_or_remaining_failure_reject_solved(self):
        for mutation in ("command", "exit_code", "observed", "later_failure"):
            case = solved_case()
            if mutation == "later_failure":
                failed = copy.deepcopy(case["validation"]["runs"][1])
                failed.update(id="V3", result="fail", exit_code=1)
                case["validation"]["runs"].append(failed)
            else:
                del case["validation"]["runs"][1][mutation]
            with self.subTest(mutation=mutation):
                self.assertTrue(research_case.validate_case(case))

    def test_duplicate_ids_and_dangling_references_are_rejected(self):
        case = solved_case()
        case["mapping"][0]["id"] = "E1"
        case["experiments"][0]["evidence_ids"] = ["missing"]
        errors = research_case.validate_case(case)
        self.assertTrue(any("唯一" in error for error in errors))
        self.assertTrue(any("引用" in error for error in errors))

    def test_malformed_objects_do_not_crash(self):
        for malformed in [None, [], {}, {"schema_version": True},
                          {**research_case.new_case(), "evidence": [False]},
                          {**research_case.new_case(), "validation": {"status": ["solved"]}}]:
            with self.subTest(malformed=malformed):
                self.assertTrue(research_case.validate_case(malformed))

    def test_malformed_execution_types_do_not_crash(self):
        for key in ("result", "kind", "check_id", "phase", "command", "exit_code"):
            case = solved_case()
            case["validation"]["runs"][0][key] = ["wrong-type"]
            with self.subTest(key=key):
                self.assertTrue(research_case.validate_case(case))

    def test_invalid_url_does_not_leak_url_or_credentials(self):
        case = solved_case()
        secret_url = "https://user:password@example.org/file"
        case["evidence"][0]["url"] = secret_url
        errors = research_case.validate_case(case)
        self.assertTrue(errors)
        self.assertNotIn(secret_url, "\n".join(errors))


class FileCliTests(unittest.TestCase):
    def test_init_does_not_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "CASE.json"
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(research_case.main(["init", "--output", str(output)]), 0)
                original = output.read_bytes()
                self.assertEqual(research_case.main(["init", "--output", str(output)]), 2)
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(research_case.validate_case(json.loads(original)), [])

    def test_validate_success_explicitly_limits_what_it_proves(self):
        with tempfile.TemporaryDirectory() as temporary:
            case_path = Path(temporary) / "CASE.json"
            case_path.write_text(json.dumps(solved_case()), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(research_case.main(["validate", str(case_path)]), 0)
            self.assertIn("不独立证明", output.getvalue())

    def test_malformed_json_error_does_not_echo_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            case_path = Path(temporary) / "CASE.json"
            secret = "secret_value_not_for_output"
            case_path.write_text('{"broken": ' + secret, encoding="utf-8")
            output = io.StringIO()
            with redirect_stderr(output):
                self.assertEqual(research_case.main(["validate", str(case_path)]), 2)
            self.assertNotIn(secret, output.getvalue())


if __name__ == "__main__":
    unittest.main()
