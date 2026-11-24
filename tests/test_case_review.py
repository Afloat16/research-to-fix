"""Review is a deterministic, non-certifying summary of declared records."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "research-to-fix" / "scripts" / "research_case.py"
sys.path.insert(0, str(SCRIPT.parent))
import research_case as rc


def run(identifier, phase, result, **extra):
    return {"id": identifier, "check_id": "same-check", "phase": phase,
            "kind": "reproduction", "command": "synthetic command", "criteria": "works",
            "observed": "synthetic private observation", "result": result,
            "exit_code": 0 if result == "pass" else 1, "evidence_ids": [], **extra}


class ReviewTests(unittest.TestCase):
    def test_blocked_template_is_valid_but_has_review_prompts(self):
        report = rc.review_case(rc.new_case())
        self.assertTrue(report["valid"])
        self.assertEqual(report["declared_status"], "blocked")
        self.assertIn("no_baseline_checks", report["findings"])
        self.assertIn("no_original_failure_check", report["findings"])

    def test_final_round_only_and_no_raw_fields(self):
        case = rc.new_case()
        case["validation"]["status"] = "partial"
        case["validation"]["runs"] = [
            run("V1", "before", "fail"),
            run("V2", "after", "pass", attempt_id="old"),
            run("V3", "after", "fail", attempt_id="final"),
        ]
        case["validation"]["final_attempt_id"] = "final"
        report = rc.review_case(case)
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["checks"]["historical_after_runs"], 1)
        self.assertEqual(report["checks"]["final_passed_checks"], 0)
        self.assertIn("baseline_checks_without_final_pass", report["findings"])
        self.assertIn("final_checks_not_all_passed", report["findings"])
        self.assertNotIn("synthetic private observation", json.dumps(report))

    def test_unselected_round_not_counted_as_final(self):
        case = rc.new_case()
        case["validation"]["runs"] = [run("V1", "before", "fail"),
                                      run("V2", "after", "pass", attempt_id="trial")]
        report = rc.review_case(case)
        self.assertIn("final_attempt_not_selected", report["findings"])
        self.assertEqual(report["checks"]["final_paired_checks"], 0)

    def test_counts_matching_declared_context_and_artifacts(self):
        case = rc.new_case()
        context = {"input": "private fixture"}
        case["validation"]["runs"] = [
            run("V1", "before", "fail", comparison_context=context,
                test_results={"test": "fail"}, artifacts={"stdout": "before.log"}),
            run("V2", "after", "pass", comparison_context=dict(context),
                test_results={"test": "pass"}, artifacts={"stdout": "after.log"})]
        report = rc.review_case(case)
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["checks"]["passed_with_matching_context"], 1)
        self.assertEqual(report["checks"]["paired_with_test_details"], 1)
        self.assertEqual(report["checks"]["paired_with_declared_artifacts"], 1)
        self.assertNotIn("private fixture", json.dumps(report))
        case["validation"]["runs"][1]["comparison_context"] = {"input": "different"}
        self.assertIn("final_pass_without_matching_declared_context", rc.review_case(case)["findings"])

    def test_partial_review_detects_changed_acceptance_and_dropped_tests(self):
        case = rc.new_case()
        case["validation"]["status"] = "partial"
        case["validation"]["runs"] = [
            run("V1", "before", "fail", test_results={"a": "fail", "b": "pass"}),
            run("V2", "after", "pass", test_results={"a": "pass"})]
        case["validation"]["runs"][1]["criteria"] = "weaker requirement"
        report = rc.review_case(case)
        self.assertTrue(report["valid"], report)
        self.assertIn("paired_checks_with_changed_acceptance", report["findings"])
        self.assertIn("baseline_test_ids_missing_or_not_passing", report["findings"])
        self.assertEqual(report["checks"]["paired_with_changed_acceptance"], 1)
        self.assertEqual(report["checks"]["paired_with_test_detail_regressions"], 1)

    def test_unread_evidence_is_not_read_support(self):
        case = rc.new_case()
        case["evidence"] = [{
            "id": "E1", "url": "https://example.org/docs", "title": "lead", "source": "docs",
            "claim": "possible route", "relevance": "mechanism", "access_status": "snippet_only",
            "publication_status": "published", "primary_status": "unknown", "published_at": "",
            "accessed_at": "", "revision": "", "author": "", "outcome": "lead",
            "limitations": [], "search_ids": []}]
        case["mapping"] = [{"id": "M1", "local_path": "src", "symbol": "", "similarities": "x",
                            "differences": "y", "hypothesis": "z", "evidence_ids": ["E1"]}]
        report = rc.review_case(case)
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["evidence"]["read_support"], 0)
        self.assertIn("external_mappings_without_read_support", report["findings"])

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            for content, expected in ((json.dumps(rc.new_case()), 0), ("[]", 1), ("{", 2)):
                path.write_text(content, encoding="utf-8")
                process = subprocess.run([sys.executable, str(SCRIPT), "review", str(path)],
                                         capture_output=True, text=True, encoding="utf-8", timeout=5)
                self.assertEqual(process.returncode, expected, process.stderr)
                report = json.loads(process.stdout)
                self.assertEqual(report["scope"], "case_review")
                self.assertEqual(report["valid"], expected == 0)
                self.assertEqual(report["input_error"], expected == 2)


if __name__ == "__main__":
    unittest.main()
