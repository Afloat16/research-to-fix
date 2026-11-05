"""Exercise the example recorder against real subprocess test outcomes."""

import hashlib
import importlib.util
import io
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/streaming-metrics"
SCRIPT = EXAMPLE / "record_case.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recorder = load_module("metrics_case_recorder", SCRIPT)
runner = load_module("metrics_test_runner", EXAMPLE / "_record_tests.py")
validator = load_module("recording_validator", ROOT / "skills/research-to-fix/scripts/research_case.py")


class CaseRecordingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output = Path(cls.temporary.name) / "recorded"
        cls.process = subprocess.run(
            [sys.executable, str(SCRIPT), "--output", str(cls.output)],
            capture_output=True, text=True, timeout=60, check=False)
        if cls.process.returncode != 0:
            raise AssertionError(cls.process.stderr)
        cls.case = json.loads((cls.output / "case.json").read_text(encoding="utf-8"))

    def test_generated_record_passes_validator_and_matches_raw_reports(self):
        self.assertEqual(validator.validate_case(self.case), [])
        self.assertEqual(self.case["validation"]["status"], "solved")
        self.assertEqual({path.name for path in self.output.iterdir()}, {"case.json", "runs"})
        for run in self.case["validation"]["runs"]:
            artifacts = self.output / "runs" / run["phase"]
            report = json.loads((artifacts / "stdout.log").read_text(encoding="utf-8"))
            self.assertEqual(report, json.loads((artifacts / "results.json").read_text(encoding="utf-8")))
            self.assertEqual(run["test_results"], report["test_results"])
            self.assertEqual(report["tests_run"], 6)
            self.assertEqual(report["python_version"], platform.python_version())
            self.assertNotIn("metrics-record-", (artifacts / "stderr.log").read_text(encoding="utf-8"))
        self.assertNotIn(self.temporary.name, json.dumps(self.case))

    def test_real_fail_to_pass_and_pass_to_pass_transitions_are_preserved(self):
        before, after = self.case["validation"]["runs"]
        self.assertEqual((before["exit_code"], after["exit_code"]), (1, 0))
        self.assertEqual(set(before["test_results"]), set(after["test_results"]))
        self.assertEqual(set(after["test_results"].values()), {"pass"})
        self.assertEqual(before["test_results"]["test_metrics.MetricsTests.test_list"], "pass")
        self.assertEqual(before["test_results"]["test_metrics.MetricsTests.test_stream"], "error")
        self.assertEqual(before["test_results"]["test_metrics_streaming.StreamingMetricsTests.test_single_use_iterable"], "fail")
        # The empty-input method has both errors and a later failing subtest.
        self.assertEqual(before["test_results"]["test_metrics_streaming.StreamingMetricsTests.test_empty_inputs"], "error")
        error_log = (self.output / "runs/before/stderr.log").read_text(encoding="utf-8")
        self.assertIn("ZeroDivisionError", error_log)
        self.assertIn("input traversed more than once", error_log)

    def test_real_record_can_be_recalled_by_the_documented_query(self):
        report = validator.recall_cases(self.output, "single-use iterator count mean", limit=3)
        self.assertEqual(report["eligible"], 1)
        self.assertEqual(len(report["matches"]), 1)
        self.assertEqual(report["matches"][0]["file"], "case.json")
        self.assertEqual(report["matches"][0]["case_id"], self.case["case_id"])
        self.assertTrue({"count", "mean"}.issubset(report["matches"][0]["matched_terms"]))

    def test_identical_test_bytes_and_python_context_are_recorded(self):
        before, after = self.case["validation"]["runs"]
        self.assertEqual(before["command"], after["command"])
        self.assertEqual(before["comparison_context"], after["comparison_context"])
        for name in (*recorder.TEST_FILES, recorder.RUNNER):
            source = (EXAMPLE / name).read_bytes()
            self.assertEqual((self.output / "runs/before" / name).read_bytes(), source)
            self.assertEqual((self.output / "runs/after" / name).read_bytes(), source)
            self.assertEqual(before["comparison_context"][name + ".sha256"], hashlib.sha256(source).hexdigest())
        self.assertEqual((self.output / "runs/before/metrics.py").read_bytes(), recorder.BROKEN)
        self.assertEqual((self.output / "runs/after/metrics.py").read_bytes(), (EXAMPLE / "metrics.py").read_bytes())
        self.assertNotEqual(before["implementation_sha256"], after["implementation_sha256"])
        self.assertIn("--- before/metrics.py", self.case["experiments"][0]["change"])

    def test_existing_output_is_refused_without_changing_any_artifact(self):
        saved = {path.relative_to(self.output): path.read_bytes()
                 for path in self.output.rglob("*") if path.is_file()}
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--output", str(self.output)],
            capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 2)
        self.assertIn("already exists", process.stderr)
        self.assertNotIn(self.temporary.name, process.stderr)
        current = {path.relative_to(self.output): path.read_bytes()
                   for path in self.output.rglob("*") if path.is_file()}
        self.assertEqual(current, saved)

    def test_bad_current_implementation_is_recorded_as_partial(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            example = base / "example"
            example.mkdir()
            for name in (*recorder.TEST_FILES, recorder.RUNNER, "README.md"):
                shutil.copyfile(EXAMPLE / name, example / name)
            (example / "metrics.py").write_bytes(recorder.BROKEN)
            with mock.patch.object(recorder, "EXAMPLE", example):
                case = recorder.record_case(base / "partial")
            self.assertEqual(validator.validate_case(case), [])
            self.assertEqual(case["validation"]["status"], "partial")
            self.assertEqual(case["validation"]["runs"][1]["exit_code"], 1)
            self.assertEqual(case["experiments"][0]["status"], "inconclusive")

    def test_crlf_checkout_keeps_the_same_documented_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            example = base / "example"
            example.mkdir()
            for name in (*recorder.TEST_FILES, recorder.RUNNER, "README.md", "metrics.py"):
                source = (EXAMPLE / name).read_bytes().replace(b"\r\n", b"\n")
                (example / name).write_bytes(source.replace(b"\n", b"\r\n"))
            with mock.patch.object(recorder, "EXAMPLE", example):
                case = recorder.record_case(base / "recorded")
            self.assertEqual(validator.validate_case(case), [])
            self.assertEqual(case["validation"]["status"], "solved")
            for name in recorder.TEST_FILES:
                captured = (base / "recorded/runs/after" / name).read_bytes()
                self.assertEqual(captured, (example / name).read_bytes())

    def test_invalid_destination_errors_do_not_echo_private_path(self):
        missing = Path(self.temporary.name) / "missing-private-parent" / "case"
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--output", str(missing)],
            capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(process.returncode, 2)
        self.assertNotIn(str(missing), process.stderr)
        self.assertNotIn("missing-private-parent", process.stderr)


class SubtestRecordingTests(unittest.TestCase):
    def test_later_success_cannot_erase_failure_or_error(self):
        class Example(unittest.TestCase):
            def test_fail_then_pass(self):
                for value in (False, True):
                    with self.subTest(value=value):
                        self.assertTrue(value)

            def test_error_then_pass(self):
                for value in (0, 1):
                    with self.subTest(value=value):
                        1 / value

            def test_skip_then_error(self):
                with self.subTest(stage="skip"):
                    self.skipTest("synthetic skip")
                with self.subTest(stage="error"):
                    raise ValueError("synthetic error")

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Example)
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=runner.RecordingResult).run(suite)
        by_method = {key.rsplit(".", 1)[1]: value for key, value in result.outcomes.items()}
        self.assertEqual(by_method, {"test_fail_then_pass": "fail", "test_error_then_pass": "error",
                                     "test_skip_then_error": "error"})


if __name__ == "__main__":
    unittest.main()
