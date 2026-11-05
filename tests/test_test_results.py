"""Preserve the tests behind a passing suite, not only its process exit status."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from test_research_case import research_case, solved_case
from test_validation_workflow import multi_attempt_case


def detailed_case():
    case = solved_case()
    before, after = case["validation"]["runs"]
    before["test_results"] = {"test_boundary": "fail", "test_existing": "pass", "test_optional_gpu": "skipped"}
    after["test_results"] = {"test_boundary": "pass", "test_existing": "pass", "test_optional_gpu": "skipped"}
    return case


class PerTestResultsTests(unittest.TestCase):
    def test_repaired_failure_and_preserved_regression_are_accepted(self):
        self.assertEqual(research_case.validate_case(detailed_case()), [])

    def test_empty_or_all_skipped_cannot_claim_a_passing_run(self):
        for results in ({}, {"test_boundary": "skipped", "test_existing": "skipped"}):
            case = detailed_case()
            case["validation"]["runs"][1]["test_results"] = results
            with self.subTest(results=results):
                errors = research_case.validate_case(case)
                self.assertTrue(any("test_results" in error for error in errors))

    def test_a_deleted_test_is_not_replaced_by_a_new_test(self):
        case = detailed_case()
        results = case["validation"]["runs"][1]["test_results"]
        del results["test_existing"]
        results["test_unrelated_new"] = "pass"
        self.assertTrue(research_case.validate_case(case))

    def test_original_fail_error_or_pass_cannot_become_skipped(self):
        for before_result in ("fail", "error", "pass"):
            case = detailed_case()
            case["validation"]["runs"][0]["test_results"]["test_boundary"] = before_result
            case["validation"]["runs"][1]["test_results"]["test_boundary"] = "skipped"
            with self.subTest(before_result=before_result):
                self.assertTrue(research_case.validate_case(case))

    def test_new_passing_tests_and_preexisting_skips_are_allowed(self):
        case = detailed_case()
        case["validation"]["runs"][1]["test_results"]["test_new_boundary"] = "pass"
        self.assertEqual(research_case.validate_case(case), [])

    def test_details_on_one_side_require_the_other_side_for_solved(self):
        for index in (0, 1):
            case = detailed_case()
            del case["validation"]["runs"][index]["test_results"]
            with self.subTest(index=index):
                self.assertTrue(research_case.validate_case(case))
                case["validation"]["status"] = "partial"
                self.assertEqual(research_case.validate_case(case), [])
        self.assertEqual(research_case.validate_case(solved_case()), [])

    def test_failed_or_unrun_individual_tests_prevent_a_pass_even_if_exit_zero(self):
        for outcome in ("fail", "error", "not_run"):
            case = detailed_case()
            case["validation"]["runs"][1]["test_results"]["test_new"] = outcome
            with self.subTest(outcome=outcome):
                self.assertTrue(research_case.validate_case(case))

    def test_unexecuted_records_cannot_have_executed_outcomes(self):
        for outcome in ("pass", "fail", "error", "skipped", "not_run"):
            case = research_case.new_case()
            case["problem"]["reproduction"]["test_results"] = {"test_boundary": outcome}
            with self.subTest(outcome=outcome):
                errors = research_case.validate_case(case)
                self.assertEqual(bool(errors), outcome != "not_run")

    def test_collection_failure_can_have_no_test_results(self):
        case = detailed_case()
        case["validation"]["status"] = "partial"
        case["validation"]["runs"][0]["test_results"] = {}
        self.assertEqual(research_case.validate_case(case), [])

    def test_historical_success_does_not_fill_missing_final_tests(self):
        case = multi_attempt_case()
        before, final, historical = case["validation"]["runs"]
        before["test_results"] = {"test_boundary": "fail", "test_existing": "pass"}
        historical["test_results"] = {"test_boundary": "fail", "test_existing": "pass"}
        final["test_results"] = {"test_boundary": "pass"}
        self.assertTrue(research_case.validate_case(case))
        final["test_results"]["test_existing"] = "pass"
        self.assertEqual(research_case.validate_case(case), [])

    def test_test_id_comparison_is_exact_and_preserves_parameter_cases(self):
        case = detailed_case()
        for run in case["validation"]["runs"]:
            run["test_results"] = {"test_boundary[small]": "fail" if run["phase"] == "before" else "pass",
                                   "test_boundary[large]": "pass"}
        self.assertEqual(research_case.validate_case(case), [])
        del case["validation"]["runs"][1]["test_results"]["test_boundary[large]"]
        self.assertTrue(research_case.validate_case(case))

    def test_invalid_detail_types_are_rejected_without_crashes(self):
        for value in (None, [], "pass", {"": "pass"}, {"test": []}, {"test": True}, {"test": "success"}, {4: "pass"}):
            case = detailed_case()
            case["validation"]["runs"][1]["test_results"] = value
            with self.subTest(value=value):
                self.assertTrue(research_case.validate_case(case))

    def test_error_messages_do_not_echo_test_ids(self):
        case = detailed_case()
        marker = "private_identifier_not_for_diagnostics"
        case["validation"]["runs"][0]["test_results"][marker] = "pass"
        errors = research_case.validate_case(case)
        self.assertTrue(errors)
        self.assertNotIn(marker, "\n".join(errors))

    def test_explicit_original_failure_details_match_the_linked_baseline(self):
        case = detailed_case()
        baseline = case["validation"]["runs"][0]
        reproduction = case["problem"]["reproduction"]
        reproduction.update(command=baseline["command"], status="fail", exit_code=1,
                            observed="Original test failed", test_results=copy.deepcopy(baseline["test_results"]))
        self.assertEqual(research_case.validate_case(case), [])
        reproduction["test_results"]["test_boundary"] = "pass"
        self.assertTrue(research_case.validate_case(case))

    def test_cli_json_rejects_deleted_regression_and_accepts_full_details(self):
        case = detailed_case()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            for delete_test in (False, True):
                candidate = copy.deepcopy(case)
                if delete_test:
                    del candidate["validation"]["runs"][1]["test_results"]["test_existing"]
                path.write_text(json.dumps(candidate), encoding="utf-8")
                output, error = io.StringIO(), io.StringIO()
                with redirect_stdout(output), redirect_stderr(error):
                    exit_code = research_case.main(["validate", str(path), "--format", "json"])
                self.assertEqual(error.getvalue(), "")
                self.assertEqual(exit_code, 1 if delete_test else 0)
                self.assertEqual(json.loads(output.getvalue())["valid"], not delete_test)


if __name__ == "__main__":
    unittest.main()
