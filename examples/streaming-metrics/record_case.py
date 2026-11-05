#!/usr/bin/env python3
"""Record real before/after results for this example using the standard library."""

import argparse
import difflib
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


EXAMPLE = Path(__file__).resolve().parent
VALIDATOR = EXAMPLE.parents[1] / "skills/research-to-fix/scripts/research_case.py"
TEST_FILES = ("test_metrics.py", "test_metrics_streaming.py")
RUNNER = "_record_tests.py"
COMMAND = "python -I _record_tests.py"
CRITERIA = "The unchanged six-method unittest suite completes with exit 0 and every method passes."
BROKEN = b'''def summarize(values):
    total = sum(values)
    count = sum(1 for _ in values)
    return {"count": count, "mean": total / count}
'''


class RecordingError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_validator():
    spec = importlib.util.spec_from_file_location("_research_case_validator", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_tests(destination, phase, sources, implementation):
    artifacts = destination / "runs" / phase
    artifacts.mkdir(parents=True)
    snapshots = {**sources, "metrics.py": implementation}
    with tempfile.TemporaryDirectory(prefix="metrics-record-") as temporary:
        workspace = Path(temporary)
        for name, data in snapshots.items():
            (workspace / name).write_bytes(data)
            (artifacts / name).write_bytes(data)
        process = subprocess.run(
            [sys.executable, "-I", RUNNER], cwd=workspace, capture_output=True,
            timeout=30, check=False)
    (artifacts / "stdout.log").write_bytes(process.stdout)
    (artifacts / "stderr.log").write_bytes(process.stderr)
    report = json.loads(process.stdout)
    outcomes = report["test_results"]
    if (not isinstance(outcomes, dict) or len(outcomes) != 6
            or report["tests_run"] != 6
            or any(value not in {"pass", "fail", "error", "skipped", "not_run"}
                   for value in outcomes.values())):
        raise RecordingError("The bundled suite did not produce a complete six-test report.")
    (artifacts / "results.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = Counter(outcomes.values())
    observed = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    passed = process.returncode == 0 and all(value == "pass" for value in outcomes.values())
    return {
        "id": "V1" if phase == "before" else "V2", "check_id": "streaming-metrics-suite",
        "phase": phase, "kind": "reproduction", "command": COMMAND,
        "exit_code": process.returncode, "expected_exit_code": 0,
        "result": "pass" if passed else "fail", "criteria": CRITERIA,
        "observed": f"{report['tests_run']} test methods: {observed}; exit {process.returncode}.",
        "test_results": outcomes, "evidence_ids": [],
        "implementation_sha256": digest(implementation),
        "artifacts": {name: f"runs/{phase}/{name}" for name in ("stdout.log", "stderr.log", "results.json")},
    }, report


def record_case(output):
    # mkdir is an exclusive reservation, including existing and dangling symlinks.
    output.mkdir()
    sources = {name: (EXAMPLE / name).read_bytes() for name in (*TEST_FILES, RUNNER)}
    if "```python\n" + BROKEN.decode("utf-8") + "```" not in (EXAMPLE / "README.md").read_text(encoding="utf-8"):
        raise RecordingError("The documented baseline no longer matches the recorder.")
    fixed = (EXAMPLE / "metrics.py").read_bytes()
    validator = load_validator()
    before, first_report = run_tests(output, "before", sources, BROKEN)
    after, last_report = run_tests(output, "after", sources, fixed)
    context = {name + ".sha256": digest(data) for name, data in sources.items()}
    for key in ("python_version", "python_implementation"):
        if first_report[key] != last_report[key]:
            raise RecordingError("The two runs used different Python environments.")
        context[key] = first_report[key]
    context["inputs"] = "All fixed input literals and iterable fixtures are contained in the unchanged test files."
    before["comparison_context"] = dict(context)
    after["comparison_context"] = dict(context)
    change = "".join(difflib.unified_diff(
        BROKEN.decode("utf-8").splitlines(keepends=True),
        fixed.decode("utf-8").splitlines(keepends=True),
        fromfile="before/metrics.py", tofile="after/metrics.py"))
    case = validator.new_case()
    case.update({
        "case_id": "streaming-metrics-recorded",
        "mapping": [{
            "id": "M1", "basis": "local_code", "evidence_ids": [],
            "local_path": "examples/streaming-metrics/metrics.py", "symbol": "summarize",
            "similarities": "The documented baseline and current implementation compute count and mean from an iterable.",
            "differences": "Only metrics.py changes; both runs use identical test and runner bytes in fresh temporary workspaces.",
            "hypothesis": "Counting during sum consumption and rejecting empty inputs will fix the observed failures while preserving the list regression.",
        }],
        "experiments": [{
            "id": "X1", "mapping_ids": ["M1"], "evidence_ids": [],
            "hypothesis": "The current implementation satisfies the same six tests that expose the documented baseline defects.",
            "change": "Only metrics.py differs; exact captured implementation change:\n" + change,
            "commands": [COMMAND], "status": "inconclusive",
        }],
        "recording": {
            "command_description": "Run python -I _record_tests.py in each fresh workspace, using the interpreter that launches record_case.py. The portable command names that interpreter as python; its version is recorded in comparison_context.",
            "reproduce": "Each runs/before and runs/after directory contains the exact source, tests and runner. Copy either directory to a fresh workspace and run its recorded command; the JSON report goes to stdout and unittest output to stderr.",
        },
    })
    case["problem"].update({
        "summary": "Two-pass summarization exhausts one-shot iterables and mishandles empty inputs.",
        "component": "streaming-metrics.summarize",
        "versions": {key: first_report[key] for key in ("python_version", "python_implementation")},
        "symptoms": ["One-shot inputs cannot be traversed twice; empty input requires ValueError."],
        "constraints": ["Keep the original test bytes and inputs unchanged; preserve built-in sum behavior."],
        "reproduction": {
            "check_id": before["check_id"], "command": COMMAND, "expected": CRITERIA,
            "observed": before["observed"], "exit_code": before["exit_code"],
            "status": before["result"],
        },
    })
    case["validation"].update({
        "status": "partial", "summary": f"Before: {before['observed']} After: {after['observed']}",
        "runs": [before, after],
        "limitations": [
            "Synthetic local example only; this recording makes no external research or upstream repair claim.",
            "The six behavioral tests do not measure peak memory or establish general performance bounds.",
            "Consistency validation does not independently prove the authenticity or causality of these recorded results.",
        ],
    })
    if before["result"] == "fail" and after["result"] == "pass":
        case["experiments"][0]["status"] = "supports"
        case["validation"]["status"] = "solved"
        if validator.validate_case(case):
            case["validation"]["status"] = "partial"
            case["experiments"][0]["status"] = "inconclusive"
            case["validation"]["limitations"].append("The recorded comparison did not pass solved consistency checks.")
    if validator.validate_case(case):
        raise RecordingError("The generated record failed consistency validation.")
    (output / "case.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
    return case


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "error: invalid arguments; use --help for usage.\n")


def main(argv=None):
    parser = SafeParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path,
                        help="New output directory; its parent must exist. Existing destinations are refused.")
    args = parser.parse_args(argv)
    try:
        case = record_case(args.output)
    except FileExistsError:
        print("error: output destination already exists; choose a new directory.", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        print("error: recording could not complete; any partial artifacts remain in the requested new directory.", file=sys.stderr)
        return 2
    print(f"Recorded a {case['validation']['status']} case and raw run artifacts in the requested directory.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
