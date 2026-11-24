#!/usr/bin/env python3
"""Run the frozen external holdouts. No automatic network on ordinary CI."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from independent_retrieval import METHODS

DATASETS = ("programmers", "stats", "scifact", "nasa")


def validate_selection(selection):
    r2f = selection["r2f"]
    sqlite = selection["sqlite"]
    if r2f not in METHODS or r2f.startswith("sqlite_"):
        raise ValueError("Invalid frozen R2F method")
    if sqlite not in METHODS or not sqlite.startswith("sqlite_"):
        raise ValueError("Invalid frozen SQLite method")
    methods = selection["methods"]
    if not isinstance(methods, list) or len(set(methods)) != len(methods):
        raise ValueError("Invalid frozen method list")
    if set(methods) != {r2f, sqlite, "v1_contextual", "v1_bm25", "sqlite_unicode", "sqlite_porter"}:
        raise ValueError("Frozen baseline coverage mismatch")
    if selection.get("datasets") != list(DATASETS):
        raise ValueError("Frozen dataset set changed")
    return methods


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.selection.read_bytes()
    selection = json.loads(raw)
    methods = validate_selection(selection)
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    scripts = Path(__file__).resolve().parent
    statuses = {}
    for dataset in DATASETS:
        data = output / dataset
        report = output / (dataset + ".json")
        split = "holdout" if dataset == "programmers" else "all"
        steps = [
            [sys.executable, str(scripts / "independent_data.py"),
             "--dataset", dataset, "--output", str(data)],
            [sys.executable, str(scripts / "independent_retrieval.py"),
             "--data", str(data), "--split", split, "--methods", *methods,
             "--output", str(report)],
        ]
        for phase, command in zip(("download", "evaluation"), steps):
            proc = subprocess.run(command, check=False)
            if proc.returncode:
                statuses[dataset] = {"status": "failed", "phase": phase, "exit_code": proc.returncode}
                break
        else:
            if not report.is_file():
                raise RuntimeError("Evaluation report missing")
            result = json.loads(report.read_text(encoding="utf-8"))
            statuses[dataset] = {"status": "completed", "documents": result["documents"],
                                 "queries": result["queries"],
                                 "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest()}
    summary = {"selection_sha256": hashlib.sha256(raw).hexdigest(), "datasets": statuses}
    (output / "status.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("HOLDOUT_STATUS", json.dumps(summary), flush=True)
    return 0 if all(row["status"] == "completed" for row in statuses.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
