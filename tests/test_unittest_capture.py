"""Actual local Python subprocess tests; never run external/untrusted code."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"
sys.path.insert(0, str(SCRIPTS))
import case_bundle as bundle
import research_case as core
import unittest_capture as capture

TESTS = b"""import os
import unittest
from calculation import divide

class CalculationTests(unittest.TestCase):
    def test_zero(self):
        with self.assertRaises(ValueError):
            divide(3, 0)

    def test_normal(self):
        self.assertEqual(divide(6, 2), 3)

    def test_subtests(self):
        for a, b, result in [(8, 2, 4), (-6, 2, -3)]:
            with self.subTest(a=a, b=b):
                self.assertEqual(divide(a, b), result)

    def test_environment(self):
        self.assertNotIn("R2F_PRIVATE_TEST_ENV", os.environ)
"""
BEFORE = b"def divide(a, b):\n    return a / b\n"
FIXED = b"def divide(a, b):\n    if b == 0:\n        raise ValueError('zero')\n    return a / b\n"
BAD = b"def divide(a, b):\n    if b == 0:\n        raise ValueError('zero')\n    return abs(a / b)\n"


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.before, self.after, self.tests = (self.root / name for name in ("before", "after", "tests"))
        for directory in (self.before, self.after, self.tests):
            directory.mkdir()
        (self.before / "calculation.py").write_bytes(BEFORE)
        (self.after / "calculation.py").write_bytes(FIXED)
        (self.tests / "test_calculation.py").write_bytes(TESTS)
        self.spec = {"schema_version": 1, "case_id": "division-capture",
                     "summary": "Division zero exception contract", "component": "calculation",
                     "hypothesis": "Check denominator without changing signed nonzero division.",
                     "implementation_files": ["calculation.py"], "comparison_files": ["test_calculation.py"],
                     "test_modules": ["test_calculation"], "original_test_ids": ["test_calculation.CalculationTests.test_zero"],
                     "timeout_seconds": 15}

    def freeze(self):
        return capture.freeze(self.spec, self.before, self.after, self.tests)

    def record(self, lock, name="recorded", **kwargs):
        return capture.record(lock, self.before, self.after, self.tests, self.root / name, **kwargs)

    def test_real_frozen_before_after_capture_and_audit(self):
        from unittest.mock import patch
        lock = self.freeze()
        pin = bundle.digest(capture.canonical(lock))
        with patch.dict("os.environ", {"R2F_PRIVATE_TEST_ENV": "synthetic-only"}):
            result = self.record(lock, approved=True, expected_digest=pin)
        root = self.root / "recorded"
        self.assertEqual(result["declared_status"], "solved")
        self.assertEqual(result["capture_audit"]["test_outcomes_audited"], 8)
        self.assertTrue(bundle.audit_capture(root, result["manifest_sha256"])["ok"])
        case = json.loads((root / "case.json").read_bytes())
        self.assertEqual(core.validate_case(case), [])
        before, after = case["validation"]["runs"]
        self.assertEqual((before["exit_code"], after["exit_code"]), (1, 0))
        self.assertEqual(before["test_results"]["test_calculation.CalculationTests.test_zero"], "error")
        self.assertEqual(set(after["test_results"].values()), {"pass"})
        self.assertEqual(before["comparison_context"], after["comparison_context"])
        self.assertEqual((root / "runs/after/workspace/calculation.py").read_bytes(), FIXED)
        self.assertNotIn(self.tmp.name, capture.canonical(lock).decode())
        self.assertNotIn("synthetic-only", (root / "case.json").read_text(encoding="utf-8"))

    def test_partial_candidate_and_missing_original_failure(self):
        (self.after / "calculation.py").write_bytes(BAD)
        result = self.record(self.freeze(), approved=True)
        self.assertEqual(result["declared_status"], "partial")
        self.assertIn("candidate_checks_not_all_passed", result["transition_findings"])
        case = json.loads((self.root / "recorded/case.json").read_bytes())
        self.assertEqual(case["validation"]["runs"][1]["test_results"]["test_calculation.CalculationTests.test_subtests"], "fail")
        self.assertTrue(result["capture_audit"]["ok"])
        (self.before / "calculation.py").write_bytes(FIXED)
        (self.after / "calculation.py").write_bytes(FIXED)
        result = self.record(self.freeze(), "no-failure", approved=True)
        self.assertEqual(result["declared_status"], "partial")
        self.assertIn("original_failure_not_reproduced", result["transition_findings"])
        self.assertIn("implementation_not_changed", result["transition_findings"])

    def test_deny_execution_and_lock_drift_before_output(self):
        lock = self.freeze()
        with self.assertRaisesRegex(bundle.BundleError, "local_execution_approval_required"):
            self.record(lock)
        with self.assertRaisesRegex(bundle.BundleError, "frozen_plan_digest_mismatch"):
            self.record(lock, approved=True, expected_digest="0" * 64)
        (self.tests / "test_calculation.py").write_bytes(TESTS + b"\n# changed tests\n")
        with self.assertRaisesRegex(bundle.BundleError, "frozen_plan_changed"):
            self.record(lock, approved=True)
        self.assertFalse((self.root / "recorded").exists())

    def test_invalid_specs_and_linked_sources(self):
        for field, value in (("implementation_files", ["../escape.py"]),
                             ("comparison_files", ["test_calculation.py", "calculation.py"]),
                             ("test_modules", ["os"]), ("timeout_seconds", True),
                             ("original_test_ids", ["bad id"])):
            bad = copy.deepcopy(self.spec)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(bundle.BundleError):
                capture.normalize_spec(bad)
        target = self.before / "calculation.py"
        target.unlink()
        try:
            target.symlink_to(self.after / "calculation.py")
        except (NotImplementedError, OSError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(bundle.BundleError):
            self.freeze()

    def test_timeout_preserves_bounded_logs_without_solved_record(self):
        self.spec["timeout_seconds"] = 1
        (self.before / "calculation.py").write_bytes(b"import time\ntime.sleep(10)\n" + BEFORE)
        with self.assertRaisesRegex(bundle.BundleError, "capture_timeout"):
            self.record(self.freeze(), "timed-out", approved=True)
        root = self.root / "timed-out"
        self.assertTrue((root / "runs/before/stdout.log").is_file())
        self.assertFalse((root / "case.json").exists())
        self.assertFalse((root / "manifest.json").exists())

    def test_directory_case_alias_rejected(self):
        bad = copy.deepcopy(self.spec)
        bad["implementation_files"] = ["Pkg/calculation.py", "pkg/helper.py"]
        with self.assertRaisesRegex(bundle.BundleError, "ambiguous_directory_case"):
            capture.normalize_spec(bad)

    def test_cli_freeze_record_and_existing_destination(self):
        spec_path, plan_path = self.root / "spec.json", self.root / "plan.json"
        spec_path.write_text(json.dumps(self.spec), encoding="utf-8")
        output = self.root / "cli-case"
        shared = ["--before", str(self.before), "--after", str(self.after), "--tests", str(self.tests)]
        def call(*args):
            return subprocess.run([sys.executable, str(SCRIPTS / "unittest_capture.py"), *args, *shared],
                                  capture_output=True, text=True, encoding="utf-8", timeout=60)
        first = call("freeze", "--spec", str(spec_path), "--output", str(plan_path))
        self.assertEqual(first.returncode, 0, first.stderr)
        pin = json.loads(first.stdout)["plan_sha256"]
        denied = call("record", "--plan", str(plan_path), "--output", str(output))
        self.assertEqual(denied.returncode, 2)
        self.assertFalse(output.exists())
        final = call("record", "--plan", str(plan_path), "--output", str(output),
                     "--approve-local-execution", "--expected-plan-sha256", pin)
        self.assertEqual(final.returncode, 0, final.stdout + final.stderr)
        self.assertEqual(json.loads(final.stdout)["declared_status"], "solved")
        existing = call("record", "--plan", str(plan_path), "--output", str(output), "--approve-local-execution")
        self.assertEqual(existing.returncode, 2)
        self.assertNotIn(self.tmp.name, existing.stdout)


if __name__ == "__main__":
    unittest.main()
