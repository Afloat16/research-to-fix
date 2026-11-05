"""Run only the bundled metrics tests and emit a JSON report on stdout."""

import contextlib
import json
import platform
import sys
import types
import unittest
from pathlib import Path


class RecordingResult(unittest.TextTestResult):
    """Aggregate subtests under their parent method; the worst outcome wins."""

    severity = {"pass": 1, "skipped": 2, "fail": 3, "error": 4}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}

    def record(self, test, outcome):
        identifier = getattr(test, "test_case", test).id()
        previous = self.outcomes.get(identifier)
        if previous is None or self.severity[outcome] > self.severity[previous]:
            self.outcomes[identifier] = outcome

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, "fail")

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, "skipped")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.record(test, "fail")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.record(test, "fail")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        outcome = "pass" if err is None else (
            "fail" if issubclass(err[0], test.failureException) else "error")
        self.record(test, outcome)


def test_ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from test_ids(test)
        else:
            yield test.id()


def main():
    # Relative compile filenames keep temporary workspace paths out of tracebacks.
    # These are fixed local modules, never module names or commands from case JSON.
    with contextlib.redirect_stdout(sys.stderr):
        for name in ("metrics", "test_metrics", "test_metrics_streaming"):
            filename = name + ".py"
            module = types.ModuleType(name)
            module.__file__ = filename
            sys.modules[name] = module
            exec(compile(Path(filename).read_bytes(), filename, "exec"), module.__dict__)
        suite = unittest.defaultTestLoader.loadTestsFromNames(
            ("test_metrics", "test_metrics_streaming"))
        identifiers = list(test_ids(suite))
        if len(set(identifiers)) != len(identifiers):
            raise RuntimeError("Duplicate test IDs in the bundled suite")
        result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    json.dump({
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "tests_run": result.testsRun,
        "successful": result.wasSuccessful(),
        "test_results": {key: result.outcomes.get(key, "not_run") for key in identifiers},
    }, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
