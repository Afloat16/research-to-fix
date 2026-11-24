#!/usr/bin/env python3
"""Child entrypoint for explicitly approved trusted local unittest snapshots.

This is not a sandbox. Do not execute it against untrusted test/implementation
code. The parent records only complete, strict method-level reports.
"""
import contextlib
import importlib
import json
from pathlib import Path
import platform
import sys
import unittest


class CaptureResult(unittest.TextTestResult):
    severity = {"pass": 1, "skipped": 2, "fail": 3, "error": 4}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}
        self.unsupported = False

    def record(self, test, outcome):
        identifier = getattr(test, "test_case", test).id()
        prior = self.outcomes.get(identifier)
        if prior is None or self.severity[outcome] > self.severity[prior]:
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
        self.unsupported = True

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.unsupported = True

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.record(test, "pass" if err is None else
                    "fail" if issubclass(err[0], test.failureException) else "error")


def ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from ids(test)
        else:
            yield test.id()


def main():
    workspace = Path.cwd().resolve()
    sys.path.insert(0, str(workspace))
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    with contextlib.redirect_stdout(sys.stderr):
        for name in sys.argv[1:]:
            module = importlib.import_module(name)
            target = workspace.joinpath(*name.split("."))
            permitted = {target.with_suffix(".py").resolve(), (target / "__init__.py").resolve()}
            if not getattr(module, "__file__", None) or Path(module.__file__).resolve() not in permitted:
                raise RuntimeError("test module did not originate in snapshot")
            suite.addTests(loader.loadTestsFromModule(module))
        identifiers = list(ids(suite))
        if loader.errors or not 1 <= len(identifiers) <= 2000 or len(set(identifiers)) != len(identifiers):
            raise RuntimeError("incomplete, excessive or duplicate test suite")
        result = unittest.TextTestRunner(verbosity=2, resultclass=CaptureResult).run(suite)
    if (result.unsupported or result.testsRun != len(identifiers)
            or set(result.outcomes) != set(identifiers)):
        raise RuntimeError("unsupported or incomplete test outcomes")
    report = {"python_version": platform.python_version(),
              "python_implementation": platform.python_implementation(),
              "tests_run": result.testsRun, "successful": result.wasSuccessful(),
              "test_results": result.outcomes}
    json.dump(report, sys.stdout, ensure_ascii=True, sort_keys=True, indent=2)
    print()
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
