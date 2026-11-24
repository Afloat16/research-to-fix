#!/usr/bin/env python3
"""Paired capture-consistency fault injection using real subprocess evidence.

This is a deterministic diagnostic, not a representative attack distribution,
a repair-success benchmark, or proof of authenticity. Each named perturbation
starts with the same genuine capture and regenerates the unpinned manifest.
"""
import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/research-to-fix/scripts"))
import case_bundle as bundle


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mutate(root, kind):
    if kind == "clean":
        return
    case_path = root / "case.json"
    case = load(case_path)
    before, after = case["validation"]["runs"]
    report_path = root / after["capture"]["report"]
    stdout_path = root / after["capture"]["stdout"]
    report = load(report_path)
    if kind == "report_only":
        report["python_version"] = "diagnostic-mismatch"
        save(report_path, report)
    elif kind == "environment_labels":
        report["python_version"] = "diagnostic-mismatch"
        save(report_path, report)
        save(stdout_path, report)
    elif kind == "omitted_test":
        del report["test_results"][sorted(report["test_results"])[0]]
        report["tests_run"] -= 1
        save(report_path, report)
        save(stdout_path, report)
    elif kind == "changed_outcome":
        report["test_results"][sorted(report["test_results"])[0]] = "fail"
        report["successful"] = False
        save(report_path, report)
        save(stdout_path, report)
    elif kind == "changed_exit":
        before["exit_code"] = 7
        case["problem"]["reproduction"]["exit_code"] = 7
        save(case_path, case)
    elif kind == "incomplete_report":
        report["tests_run"] -= 1
        save(report_path, report)
        save(stdout_path, report)
    elif kind == "report_success_flag":
        report["successful"] = False
        save(report_path, report)
        save(stdout_path, report)
    elif kind == "implementation_snapshot":
        name = next(iter(after["capture"]["implementation_files"]))
        with (root / name).open("ab") as out:
            out.write(b"\n# diagnostic mutation\n")
    elif kind == "comparison_snapshot":
        name = next(iter(after["capture"]["comparison_files"].values()))
        with (root / name).open("ab") as out:
            out.write(b"\n# diagnostic mutation\n")
    elif kind == "missing_capture":
        del after["capture"]
        save(case_path, case)
    elif kind == "omitted_comparison_binding":
        key = next(iter(after["capture"]["comparison_files"]))
        del after["capture"]["comparison_files"][key]
        save(case_path, case)
    elif kind == "aliased_reports":
        after["capture"]["stdout"] = after["capture"]["report"]
        save(case_path, case)
    elif kind == "unsealed_capture_member":
        source = after["capture"]["report"]
        target = "unlisted.json"
        shutil.copyfile(root / source, root / target)
        after["capture"]["report"] = target
        save(case_path, case)
    elif kind == "consistent_log_edit":
        # Negative control: stderr is not interpreted. A coherent rewrite
        # can pass an unpinned audit; an independent pin must catch it.
        with (root / after["capture"]["stderr"]).open("ab") as out:
            out.write(b"\ncoherent but untrusted edit\n")
    else:
        raise ValueError("unknown diagnostic")


FAULTS = (
    "report_only", "environment_labels", "omitted_test", "changed_outcome",
    "changed_exit", "incomplete_report", "report_success_flag",
    "implementation_snapshot", "comparison_snapshot", "missing_capture",
    "omitted_comparison_binding", "aliased_reports", "unsealed_capture_member",
)


def check(fn, *args):
    start = perf_counter_ns()
    try:
        fn(*args)
        return {"accepted": True, "error": None, "elapsed_ms": (perf_counter_ns() - start) / 1e6}
    except bundle.BundleError as exc:
        return {"accepted": False, "error": str(exc), "elapsed_ms": (perf_counter_ns() - start) / 1e6}


def evaluate():
    with tempfile.TemporaryDirectory(prefix="r2f-capture-diagnostic-") as temporary:
        root = Path(temporary)
        source = root / "original"
        subprocess.run([sys.executable, str(ROOT / "examples/streaming-metrics/record_case.py"),
                        "--output", str(source)], check=True, timeout=60, capture_output=True)
        pin = bundle.seal(source)["manifest_sha256"]
        baseline = bundle.audit_capture(source, pin)
        rows = []
        for kind in ("clean", *FAULTS, "consistent_log_edit"):
            target = root / kind
            shutil.copytree(source, target)
            (target / "manifest.json").unlink()
            mutate(target, kind)
            try:
                bundle.seal(target)
            except bundle.BundleError as exc:
                rows.append({"case": kind, "seal": False, "seal_error": str(exc)})
                continue
            rows.append({"case": kind, "seal": True,
                         "verify_unpinned": check(bundle.verify, target),
                         "audit_unpinned": check(bundle.audit_capture, target),
                         "verify_pinned": check(bundle.verify, target, pin),
                         "audit_pinned": check(bundle.audit_capture, target, pin)})
        faults = [row for row in rows if row["case"] in FAULTS]
        controls = [row for row in rows if row["case"] not in FAULTS]
        counts = {name: sum(not row["seal"] or not row[name]["accepted"] for row in faults)
                  for name in ("verify_unpinned", "audit_unpinned", "verify_pinned", "audit_pinned")}
        clean, coherent = controls
        if (not clean["seal"] or not all(clean[k]["accepted"] for k in counts)
                or not coherent["seal"] or not coherent["audit_unpinned"]["accepted"]
                or coherent["audit_pinned"]["accepted"]
                or counts["audit_unpinned"] != len(FAULTS)):
            raise RuntimeError("diagnostic regression")
        return {"scope": "Named synthetic perturbations of genuine local subprocess evidence; not general attack detection",
                "python": platform.python_version(), "platform": platform.platform(),
                "executed_runs": baseline["executed_runs_audited"],
                "actual_test_outcomes": baseline["test_outcomes_audited"],
                "fault_types": len(FAULTS), "clean_controls": 1, "coherent_edit_controls": 1,
                "rejected_faults": counts, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate()
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print("CAPTURE_AUDIT_SUMMARY", json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
