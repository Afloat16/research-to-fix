"""Regression checks for comparable, multi-attempt, and combined repair records."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from test_research_case import research_case, solved_case


def multi_attempt_case():
    case = solved_case()
    final = case["validation"]["runs"][1]
    final["attempt_id"] = "A2"
    historical = copy.deepcopy(final)
    historical.update(id="V3", attempt_id="A1", result="fail", exit_code=1)
    case["validation"]["runs"].append(historical)
    case["validation"]["final_attempt_id"] = "A2"
    case["experiments"][0]["attempt_id"] = "A2"
    earlier = copy.deepcopy(case["experiments"][0])
    earlier.update(id="X2", attempt_id="A1", status="rejects")
    case["experiments"].append(earlier)
    return case


def combined_case():
    case = multi_attempt_case()
    mapping = copy.deepcopy(case["mapping"][0])
    mapping.update(id="M2", basis="local_code", evidence_ids=[],
                   local_path="src/normalize.py", hypothesis="Normalize the boundary before lookup")
    case["mapping"].append(mapping)
    case["experiments"][0]["mapping_ids"] = ["M1", "M2"]
    case["solution"] = {
        "strategy": "combined",
        "components": [
            {"mapping_id": "M1", "contribution": "Bound checking", "adaptation": "Use local indexing rules"},
            {"mapping_id": "M2", "contribution": "Input normalization", "adaptation": "Preserve local types",
             "omitted": "No additional caching"},
        ],
        "rationale": "Both mechanisms are needed for the boundary case",
        "compatibility": "Normalization runs before bounds checking",
        "tradeoffs": ["An additional validation branch"],
        "unresolved_conflicts": [],
    }
    return case


class ComparableValidationTests(unittest.TestCase):
    def test_validator_can_be_reused_without_leaking_previous_state(self):
        validator = research_case.CaseValidator()
        self.assertTrue(validator.validate({}))
        self.assertEqual(validator.validate(solved_case()), [])
        self.assertEqual(validator.validate(solved_case()), [])

    def test_every_recorded_regression_requires_an_after_result(self):
        for before_result in ("pass", "fail", "not_run"):
            case = solved_case()
            regression = {"id": "R1", "check_id": "regression", "phase": "before", "kind": "test",
                          "command": "python -m unittest", "exit_code": None if before_result == "not_run" else 0,
                          "result": before_result, "observed": "Baseline", "evidence_ids": []}
            case["validation"]["runs"].append(regression)
            with self.subTest(before_result=before_result):
                self.assertTrue(research_case.validate_case(case))
                final = copy.deepcopy(regression)
                final.update(id="R2", phase="after", exit_code=0, result="pass")
                case["validation"]["runs"].append(final)
                self.assertEqual(research_case.validate_case(case), [])

    def test_regression_criteria_cannot_be_changed_to_pass(self):
        case = solved_case()
        for index, phase in enumerate(("before", "after")):
            case["validation"]["runs"].append({
                "id": f"R{index}", "check_id": "regression", "phase": phase, "kind": "test",
                "command": "python -m unittest", "exit_code": 0, "result": "pass",
                "observed": "All tests passed", "criteria": "All 20 tests pass", "evidence_ids": [],
            })
        self.assertEqual(research_case.validate_case(case), [])
        case["validation"]["runs"][-1]["criteria"] = "One test passes"
        self.assertTrue(research_case.validate_case(case))

    def test_reported_reproduction_must_match_the_original_check(self):
        case = solved_case()
        case["problem"]["reproduction"].update(
            command="python reproduce.py", status="fail", exit_code=1,
            expected="Return the indexed value", observed="IndexError", check_id="boundary")
        self.assertEqual(research_case.validate_case(case), [])
        for field, value in (("command", "python unrelated.py"), ("check_id", "unrelated")):
            changed = copy.deepcopy(case)
            changed["problem"]["reproduction"][field] = value
            with self.subTest(field=field):
                self.assertTrue(research_case.validate_case(changed))

    def test_a_nonzero_expected_exit_can_be_a_semantic_success(self):
        case = solved_case()
        before, after = case["validation"]["runs"]
        before.update(exit_code=0, expected_exit_code=2, observed="Invalid input was wrongly accepted")
        after.update(exit_code=2, expected_exit_code=2, observed="Invalid input is rejected")
        for run in (before, after):
            run["criteria"] = "Invalid input must be rejected with exit status 2"
        self.assertEqual(research_case.validate_case(case), [])
        before["expected_exit_code"] = 0
        self.assertTrue(research_case.validate_case(case))

    def test_original_reproduction_declared_conditions_must_match_its_baseline(self):
        case = solved_case()
        context = {"input": "boundary-fixture-v1", "check_revision": "v1"}
        for run in case["validation"]["runs"]:
            run["comparison_context"] = copy.deepcopy(context)
        reproduction = case["problem"]["reproduction"]
        reproduction.update(command="python reproduce.py", check_id="boundary", status="fail", exit_code=1,
                            expected="Return the indexed value", observed="IndexError", expected_exit_code=0,
                            criteria=case["validation"]["runs"][0]["criteria"], comparison_context=copy.deepcopy(context))
        self.assertEqual(research_case.validate_case(case), [])
        for field, value in (("comparison_context", {"input": "different-fixture", "check_revision": "v1"}),
                             ("expected_exit_code", 2), ("criteria", "Accept any output")):
            changed = copy.deepcopy(case)
            changed["problem"]["reproduction"][field] = value
            with self.subTest(field=field):
                self.assertTrue(research_case.validate_case(changed))

    def test_expected_exit_code_defaults_to_zero_and_rejects_invalid_types(self):
        case = solved_case()
        case["validation"]["runs"][1]["expected_exit_code"] = 0
        self.assertEqual(research_case.validate_case(case), [])
        for value in (True, None, "0", [], {}):
            case["validation"]["runs"][1]["expected_exit_code"] = value
            with self.subTest(value=value):
                self.assertTrue(research_case.validate_case(case))

    def test_declared_comparison_context_must_match_on_both_sides(self):
        case = solved_case("benchmark")
        context = {"dataset": "fixture-v1", "seed": "42", "measurement_protocol": "peak-rss-v1"}
        for run in case["validation"]["runs"]:
            run["comparison_context"] = copy.deepcopy(context)
        self.assertEqual(research_case.validate_case(case), [])
        case["validation"]["runs"][1]["comparison_context"]["dataset"] = "easier-fixture"
        self.assertTrue(research_case.validate_case(case))
        del case["validation"]["runs"][1]["comparison_context"]
        self.assertTrue(research_case.validate_case(case))

    def test_malformed_context_and_criteria_do_not_crash_or_pass(self):
        for value in (None, [], {}, {"seed": 42}, {"": "v1"}, {"dataset": " "}):
            case = solved_case()
            case["validation"]["runs"][1]["comparison_context"] = value
            with self.subTest(context=value):
                self.assertTrue(research_case.validate_case(case))
        case = solved_case()
        regression = copy.deepcopy(case["validation"]["runs"][1])
        regression.update(id="R1", check_id="regression", kind="test", criteria={"not": "text"})
        case["validation"]["runs"].append(regression)
        self.assertTrue(research_case.validate_case(case))


class MultiAttemptTests(unittest.TestCase):
    def test_explicit_final_attempt_preserves_failed_history_regardless_of_order(self):
        case = multi_attempt_case()
        self.assertEqual(research_case.validate_case(case), [])
        case["validation"]["runs"].reverse()
        self.assertEqual(research_case.validate_case(case), [])

    def test_attempts_require_explicit_complete_and_existing_selection(self):
        for mutation in ("missing_final", "missing_label", "unknown_final", "invalid_final", "invalid_label"):
            case = multi_attempt_case()
            validation = case["validation"]
            if mutation == "missing_final":
                del validation["final_attempt_id"]
            elif mutation == "missing_label":
                del validation["runs"][1]["attempt_id"]
            elif mutation == "unknown_final":
                validation["final_attempt_id"] = "A3"
            elif mutation == "invalid_final":
                validation["final_attempt_id"] = []
            else:
                validation["runs"][1]["attempt_id"] = []
            with self.subTest(mutation=mutation):
                self.assertTrue(research_case.validate_case(case))

    def test_historical_support_cannot_replace_final_experiment(self):
        case = multi_attempt_case()
        case["experiments"][0]["attempt_id"] = "A1"
        self.assertTrue(research_case.validate_case(case))

    def test_final_failure_or_unexecuted_check_blocks_solved(self):
        for result, exit_code in (("fail", 1), ("not_run", None)):
            case = multi_attempt_case()
            case["validation"]["runs"][1].update(result=result, exit_code=exit_code)
            with self.subTest(result=result):
                self.assertTrue(research_case.validate_case(case))

    def test_prior_attempt_cannot_supply_a_missing_final_regression(self):
        case = multi_attempt_case()
        regression = copy.deepcopy(case["validation"]["runs"][0])
        regression.update(id="R1", check_id="regression", kind="test", result="pass", exit_code=0)
        historical = copy.deepcopy(regression)
        historical.update(id="R2", phase="after", attempt_id="A1")
        case["validation"]["runs"].extend([regression, historical])
        self.assertTrue(research_case.validate_case(case))

    def test_partial_attempts_can_be_recorded_before_choosing_a_final_one(self):
        case = multi_attempt_case()
        case["validation"]["status"] = "partial"
        del case["validation"]["final_attempt_id"]
        self.assertEqual(research_case.validate_case(case), [])

    def test_legacy_single_attempt_remains_strict(self):
        case = solved_case()
        failed = copy.deepcopy(case["validation"]["runs"][1])
        failed.update(id="V3", result="fail", exit_code=1)
        case["validation"]["runs"].append(failed)
        self.assertTrue(research_case.validate_case(case))


class SolutionCompositionTests(unittest.TestCase):
    def test_combined_external_and_local_components_with_joint_validation(self):
        self.assertEqual(research_case.validate_case(combined_case()), [])

    def test_individual_successes_cannot_replace_joint_validation(self):
        case = combined_case()
        first = case["experiments"][0]
        first["mapping_ids"] = ["M1"]
        second = copy.deepcopy(first)
        second.update(id="X3", mapping_ids=["M2"])
        case["experiments"].append(second)
        self.assertTrue(research_case.validate_case(case))

    def test_single_strategy_requires_exactly_one_component(self):
        case = combined_case()
        case["solution"]["strategy"] = "single"
        self.assertTrue(research_case.validate_case(case))
        case["solution"]["components"].pop()
        self.assertEqual(research_case.validate_case(case), [])

    def test_component_references_must_be_unique_and_existing(self):
        for mapping_id in ("M1", "missing", [], None):
            case = combined_case()
            case["solution"]["components"][1]["mapping_id"] = mapping_id
            with self.subTest(mapping_id=mapping_id):
                self.assertTrue(research_case.validate_case(case))

    def test_combination_requires_usable_descriptions_and_valid_types(self):
        for field in ("rationale", "compatibility", "strategy", "components", "tradeoffs"):
            case = combined_case()
            case["solution"][field] = None
            with self.subTest(field=field):
                self.assertTrue(research_case.validate_case(case))
        for field in ("contribution", "adaptation", "omitted"):
            case = combined_case()
            case["solution"]["components"][0][field] = None
            with self.subTest(component_field=field):
                self.assertTrue(research_case.validate_case(case))

    def test_unresolved_conflicts_allow_partial_but_prevent_solved(self):
        case = combined_case()
        case["solution"]["unresolved_conflicts"] = ["Version compatibility is still unresolved"]
        self.assertTrue(research_case.validate_case(case))
        case["validation"]["status"] = "partial"
        self.assertEqual(research_case.validate_case(case), [])


class SearchRecordTests(unittest.TestCase):
    def test_unused_or_blocked_source_can_have_a_reason_without_a_query(self):
        for status in ("not_relevant", "blocked", "unavailable", "access_blocked"):
            case = research_case.new_case()
            case["searches"] = [{"id": "S1", "source": "papers", "language": "en", "query": "",
                                 "searched_at": "", "status": status, "reason": "Not applicable to this case",
                                 "result_urls": []}]
            with self.subTest(status=status):
                self.assertEqual(research_case.validate_case(case), [])
                del case["searches"][0]["reason"]
                self.assertTrue(research_case.validate_case(case))

    def test_completed_and_legacy_searched_require_query_and_time(self):
        for status in ("completed", "searched"):
            case = solved_case()
            case["searches"][0]["status"] = status
            with self.subTest(status=status):
                self.assertEqual(research_case.validate_case(case), [])
                for field in ("query", "searched_at"):
                    invalid = copy.deepcopy(case)
                    invalid["searches"][0][field] = ""
                    self.assertTrue(research_case.validate_case(invalid))


class StructuredCliTests(unittest.TestCase):
    def invoke(self, path):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = research_case.main(["validate", str(path), "--format", "json"])
        self.assertEqual(stderr.getvalue(), "")
        return code, json.loads(stdout.getvalue())

    def test_json_result_separates_consistency_failure_from_input_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "case.json"
            path.write_text(json.dumps(combined_case()), encoding="utf-8")
            code, report = self.invoke(path)
            self.assertEqual(code, 0)
            self.assertTrue(report["valid"])
            self.assertEqual(report["scope"], "record_consistency")
            self.assertIn("不独立证明", report["notice"])
            invalid = combined_case()
            invalid["validation"]["runs"][1]["result"] = "fail"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            code, report = self.invoke(path)
            self.assertEqual(code, 1)
            self.assertFalse(report["valid"])
            self.assertFalse(report["input_error"])
            self.assertTrue(report["errors"])
            path.unlink()
            code, report = self.invoke(path)
            self.assertEqual(code, 2)
            self.assertFalse(report["valid"])
            self.assertTrue(report["input_error"])
            self.assertNotIn(str(path), json.dumps(report))

    def test_ambiguous_or_malformed_json_is_rejected_without_echo(self):
        secret = "synthetic_private_value"
        duplicate = json.dumps(solved_case())[:-1] + ', "case_id": "' + secret + '"}'
        inputs = [duplicate, '{"broken": ' + secret, '{"value": NaN}', '{"value": Infinity}']
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "case.json"
            for source in inputs:
                path.write_text(source, encoding="utf-8")
                code, report = self.invoke(path)
                with self.subTest(prefix=source[:20]):
                    self.assertEqual(code, 2)
                    self.assertTrue(report["input_error"])
                    self.assertNotIn(secret, json.dumps(report))
            # Parser nesting limits differ across Python versions. Either a JSON
            # input error or an invalid top-level case is a safe rejection.
            path.write_text("[" * 2000 + "0" + "]" * 2000, encoding="utf-8")
            code, report = self.invoke(path)
            self.assertIn(code, (1, 2))
            self.assertFalse(report["valid"])
            path.write_bytes(b"\xff\xfe")
            code, report = self.invoke(path)
            self.assertEqual(code, 2)
            self.assertTrue(report["input_error"])


if __name__ == "__main__":
    unittest.main()
