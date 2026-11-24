#!/usr/bin/env python3
"""Freeze and record trusted local before/after unittest snapshots.

No source is executed by freeze. Record requires an explicit approval flag
and executes only the fixed Python runner over explicitly selected local files.
The fresh workspaces and stripped environment are NOT a security sandbox.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time

import case_bundle as bundle
import research_case as core

RUNNER = "_r2f_capture_runner.py"
PLAN = "_r2f_frozen_plan.json"
MAX_FILES = 48
MAX_SOURCE_BYTES = 1024 * 1024
MAX_TOTAL_SOURCE_BYTES = 12 * 1024 * 1024
MAX_STDERR = 1024 * 1024
MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
NOTICE = ("Trusted local code only; not a sandbox, model runner, or authenticity check. "
          "A solved record is conditional on the frozen declared tests, not general correctness.")


def fail(code):
    raise bundle.BundleError(code)


def local_text(value, maximum):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(c) < 32 for c in value)):
        fail("invalid_spec_text")
    return value


def unique_paths(value):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_FILES:
        fail("invalid_spec_paths")
    paths = [bundle.portable_path(path) for path in value]
    if any(len(path) > 200 for path in paths):
        fail("invalid_spec_paths")
    if len({path.casefold() for path in paths}) != len(paths):
        fail("duplicate_spec_path")
    return sorted(paths)


def normalize_spec(value):
    fields = {"schema_version", "case_id", "summary", "component", "hypothesis",
              "implementation_files", "comparison_files", "test_modules",
              "original_test_ids", "timeout_seconds"}
    if not isinstance(value, dict) or set(value) != fields or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        fail("invalid_spec")
    impl = unique_paths(value["implementation_files"])
    comparison = unique_paths(value["comparison_files"])
    paths = {path.casefold() for path in impl + comparison}
    if len(impl) + len(comparison) > MAX_FILES or len(paths) != len(impl) + len(comparison):
        fail("duplicate_or_excessive_paths")
    # Reject directory aliases too: A/x.py and a/y.py are different trees
    # on case-sensitive hosts but merge into one on case-insensitive hosts.
    spellings = {}
    for path in impl + comparison:
        parts = path.split("/")
        for end in range(1, len(parts)):
            prefix = "/".join(parts[:end])
            if spellings.setdefault(prefix.casefold(), prefix) != prefix:
                fail("ambiguous_directory_case")
    for name in paths:
        if name in {RUNNER.casefold(), PLAN.casefold()} or any(
                "/".join(name.split("/")[:n]) in paths for n in range(1, len(name.split("/")))):
            fail("reserved_or_conflicting_path")
        if name.startswith(RUNNER.casefold() + "/") or name.startswith(PLAN.casefold() + "/"):
            fail("reserved_or_conflicting_path")
    modules = value["test_modules"]
    if (not isinstance(modules, list) or not 1 <= len(modules) <= 24
            or any(not isinstance(m, str) or len(m) > 120 or not MODULE.fullmatch(m) for m in modules)
            or len(set(modules)) != len(modules)):
        fail("invalid_test_modules")
    for name in modules:
        prefix = name.replace(".", "/")
        if sum(path in comparison for path in (prefix + ".py", prefix + "/__init__.py")) != 1:
            fail("test_module_not_explicit")
    originals = value["original_test_ids"]
    if (not isinstance(originals, list) or not 1 <= len(originals) <= 64
            or any(not isinstance(t, str) or len(t) > 500 or not MODULE.fullmatch(t) for t in originals)
            or len(set(originals)) != len(originals)):
        fail("invalid_original_test_ids")
    timeout = value["timeout_seconds"]
    if type(timeout) is not int or not 1 <= timeout <= 120:
        fail("invalid_timeout")
    return {"schema_version": 1, "case_id": local_text(value["case_id"], 128),
            "summary": local_text(value["summary"], 1000), "component": local_text(value["component"], 200),
            "hypothesis": local_text(value["hypothesis"], 1000), "implementation_files": impl,
            "comparison_files": comparison, "test_modules": modules, "original_test_ids": sorted(originals),
            "timeout_seconds": timeout}


def read_json(path):
    raw, issue = core._read_regular_file(Path(path), core.VALIDATE_MAX_FILE_BYTES)
    if issue:
        fail("invalid_input_file")
    return core.decode_case_bytes(raw)[0]


def canonical(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def prepare(spec, before, after, tests):
    spec = normalize_spec(spec)
    source_bytes = {}
    total = 0
    for role, directory, paths in (("before", before, spec["implementation_files"]),
                                    ("after", after, spec["implementation_files"]),
                                    ("comparison", tests, spec["comparison_files"])):
        root = bundle.checked_root(directory)
        members = {}
        for name in paths:
            data = bundle.read_member(root, name, min(MAX_SOURCE_BYTES, MAX_TOTAL_SOURCE_BYTES - total))
            members[name] = data
            total += len(data)
        source_bytes[role] = members
    runner = Path(__file__).with_name(RUNNER)
    raw, issue = core._read_regular_file(runner, MAX_SOURCE_BYTES)
    if issue:
        fail("capture_runner_unreadable")
    lock = {"schema_version": 1, "scope": "frozen_local_unittest",
            "spec": spec, "source_sha256": {role: {name: bundle.digest(data) for name, data in members.items()}
                                           for role, members in source_bytes.items()},
            "runner_sha256": bundle.digest(raw), "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation()}
    return lock, source_bytes, raw


def freeze(spec, before, after, tests):
    return prepare(spec, before, after, tests)[0]


def write_members(root, members):
    for name, data in members.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def run_bounded(workspace, modules, timeout, destination):
    command = [sys.executable, "-I", "-S", "-B", "-X", "utf8", RUNNER, *modules]
    # Do not inherit credential or proxy environment variables. This does not
    # prevent trusted code from accessing the host filesystem/network.
    env = {key: str(workspace) for key in ("TMP", "TEMP", "TMPDIR")}
    if os.name == "nt" and "SystemRoot" in os.environ:
        env["SystemRoot"] = os.environ["SystemRoot"]
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, cwd=workspace, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, env=env, shell=False)
        deadline = time.monotonic() + timeout
        reason = None
        try:
            while process.poll() is None:
                if (os.fstat(stdout.fileno()).st_size > bundle.CAPTURE_REPORT_MAX
                        or os.fstat(stderr.fileno()).st_size > MAX_STDERR):
                    reason = "capture_output_limit"
                    break
                if time.monotonic() >= deadline:
                    reason = "capture_timeout"
                    break
                time.sleep(.02)
        finally:
            if process.poll() is None:
                process.kill()
            code = process.wait()
        stdout.seek(0)
        stderr.seek(0)
        raw, err = stdout.read(bundle.CAPTURE_REPORT_MAX + 1), stderr.read(MAX_STDERR + 1)
        (destination / "stdout.log").write_bytes(raw[:bundle.CAPTURE_REPORT_MAX])
        (destination / "stderr.log").write_bytes(err[:MAX_STDERR])
    if reason:
        fail(reason)
    if len(raw) > bundle.CAPTURE_REPORT_MAX or len(err) > MAX_STDERR:
        fail("capture_output_limit")
    try:
        report = core.decode_case_bytes(raw)[0]
        outcomes = bundle.validate_unittest_report(report)
    except (ValueError, RecursionError):
        fail("capture_incomplete_report")
    if code != (0 if report["successful"] else 1):
        fail("capture_exit_result_mismatch")
    return code, report, outcomes


def capture_phase(destination, phase, lock, source, runner):
    spec = lock["spec"]
    directory = destination / "runs" / phase
    directory.mkdir(parents=True)
    comparison = {**source["comparison"], RUNNER: runner, PLAN: canonical(lock)}
    snapshots = {**source[phase], **comparison}
    captured = directory / "workspace"
    write_members(captured, snapshots)
    with tempfile.TemporaryDirectory(prefix="r2f-unittest-") as tmp:
        workspace = Path(tmp)
        write_members(workspace, snapshots)
        code, report, outcomes = run_bounded(workspace, spec["test_modules"], spec["timeout_seconds"], directory)
    if any(report[key] != lock[key] for key in ("python_version", "python_implementation")):
        fail("capture_environment_mismatch")
    (directory / "results.json").write_bytes(canonical(report))
    prefix = "runs/" + phase + "/"
    file_paths = {name: prefix + "workspace/" + name for name in snapshots}
    context = {name + ".sha256": bundle.digest(data) for name, data in comparison.items()}
    context.update(python_version=lock["python_version"], python_implementation=lock["python_implementation"])
    artifacts = {"snapshot-" + str(i): path for i, path in enumerate(file_paths.values())}
    artifacts.update({name: prefix + name for name in ("stdout.log", "stderr.log", "results.json")})
    counts = Counter(outcomes.values())
    observed = str(len(outcomes)) + " methods: " + ", ".join(k + "=" + str(v) for k, v in sorted(counts.items())) + "; exit " + str(code)
    result = "pass" if code == 0 and all(v == "pass" for v in outcomes.values()) else "fail"
    return {"id": "V1" if phase == "before" else "V2", "check_id": "frozen-unittest", "kind": "reproduction",
            "phase": phase, "command": "python -I -S -B -X utf8 " + RUNNER + " " + " ".join(spec["test_modules"]),
            "criteria": "Every frozen test method passes; separately verify declared original failure IDs.",
            "observed": observed, "result": result, "exit_code": code, "expected_exit_code": 0,
            "evidence_ids": [], "test_results": outcomes, "comparison_context": context, "artifacts": artifacts,
            "capture": {"schema_version": 1, "format": "unittest-json-v1", "report": prefix + "results.json",
                        "stdout": prefix + "stdout.log", "stderr": prefix + "stderr.log",
                        "implementation_files": {file_paths[name]: bundle.digest(data) for name, data in source[phase].items()},
                        "comparison_files": {name + ".sha256": file_paths[name] for name in comparison}}}


def record(lock, before, after, tests, output, *, approved=False, expected_digest=None):
    if approved is not True:
        fail("local_execution_approval_required")
    if not isinstance(lock, dict) or "spec" not in lock:
        fail("invalid_frozen_plan")
    if expected_digest is not None and (not bundle.valid_digest(expected_digest) or bundle.digest(canonical(lock)) != expected_digest):
        fail("frozen_plan_digest_mismatch")
    actual, source, runner = prepare(lock["spec"], before, after, tests)
    if canonical(actual) != canonical(lock):
        fail("frozen_plan_changed")
    output = Path(output)
    output.mkdir()
    first = capture_phase(output, "before", lock, source, runner)
    final = capture_phase(output, "after", lock, source, runner)
    spec = lock["spec"]
    original = set(spec["original_test_ids"])
    left, right = first["test_results"], final["test_results"]
    if not original <= set(left) or not original <= set(right):
        fail("original_test_ids_missing")
    changed = lock["source_sha256"]["before"] != lock["source_sha256"]["after"]
    reasons = []
    if not any(left[name] in ("fail", "error") for name in original):
        reasons.append("original_failure_not_reproduced")
    if set(left) != set(right):
        reasons.append("test_id_set_changed")
    if "skipped" in left.values():
        reasons.append("baseline_skipped_tests")
    if final["result"] != "pass":
        reasons.append("candidate_checks_not_all_passed")
    if not changed:
        reasons.append("implementation_not_changed")
    solved = not reasons
    case = core.new_case()
    case["case_id"] = spec["case_id"]
    case["problem"].update(summary=spec["summary"], component=spec["component"],
                           symptoms=[spec["summary"]], versions={"python": lock["python_version"]},
                           constraints=["Use the frozen comparison files and original test IDs."],
                           reproduction={"check_id": first["check_id"], "command": first["command"],
                                         "expected": first["criteria"], "observed": first["observed"],
                                         "exit_code": first["exit_code"], "status": first["result"],
                                         "test_results": left, "comparison_context": first["comparison_context"]})
    case["mapping"] = [{"id": "M1", "basis": "local_code", "evidence_ids": [],
                        "local_path": spec["implementation_files"][0], "symbol": "",
                        "similarities": "Same declared test modules and frozen comparison files.",
                        "differences": "Only explicitly selected implementation files may differ between snapshots.",
                        "hypothesis": spec["hypothesis"]}]
    case["experiments"] = [{"id": "X1", "hypothesis": spec["hypothesis"],
                            "change": "Compare frozen implementation snapshots; inspect their sealed byte digests.",
                            "commands": [first["command"]], "status": "supports" if solved else "inconclusive",
                            "mapping_ids": ["M1"], "evidence_ids": []}]
    case["validation"].update(status="solved" if solved else "partial",
                              summary="Before: " + first["observed"] + " After: " + final["observed"],
                              runs=[first, final], limitations=[NOTICE,
                              "No external research or performance measurement was performed by this recorder.", *reasons])
    case["recording"] = {"scope": "frozen_local_unittest", "plan_sha256": bundle.digest(canonical(lock)),
                         "original_test_ids": spec["original_test_ids"], "transition_findings": reasons}
    if core.validate_case(case):
        fail("record_consistency_failed")
    (output / "case.json").write_bytes(canonical(case))
    seal = bundle.seal(output)
    audit = bundle.audit_capture(output, seal["manifest_sha256"])
    return {"ok": True, "declared_status": case["validation"]["status"], "transition_findings": reasons,
            "plan_sha256": bundle.digest(canonical(lock)), "manifest_sha256": seal["manifest_sha256"],
            "capture_audit": audit, "notice": NOTICE}


def main(argv=None):
    parser = core.SafeArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True, parser_class=core.SafeArgumentParser)
    for name in ("freeze", "record"):
        sub = subs.add_parser(name)
        sub.add_argument("--spec" if name == "freeze" else "--plan", required=True, type=Path)
        for option in ("before", "after", "tests", "output"):
            sub.add_argument("--" + option, required=True, type=Path)
        if name == "record":
            sub.add_argument("--approve-local-execution", action="store_true")
            sub.add_argument("--expected-plan-sha256")
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            lock = freeze(read_json(args.spec), args.before, args.after, args.tests)
            with args.output.open("xb") as out:
                out.write(canonical(lock))
            result = {"ok": True, "plan_sha256": bundle.digest(canonical(lock)), "notice": NOTICE}
        else:
            if not args.approve_local_execution:
                fail("local_execution_approval_required")
            result = record(read_json(args.plan), args.before, args.after, args.tests, args.output,
                            approved=True, expected_digest=args.expected_plan_sha256)
        status = 0
    except bundle.BundleError as error:
        result, status = {"ok": False, "error": str(error), "notice": NOTICE}, error.exit_code
    except (OSError, ValueError, TypeError, RecursionError, KeyError, subprocess.SubprocessError):
        result, status = {"ok": False, "error": "invalid_input_or_capture_operation", "notice": NOTICE}, 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return status


if __name__ == "__main__":
    sys.exit(main())
