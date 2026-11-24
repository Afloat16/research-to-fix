#!/usr/bin/env python3
"""Quality and identity gates for fixed source-linked development replay.

The qrels are deliberately incomplete and the gate does not certify live
retrieval, source validity, or repair success. Timings remain observations.
"""
import argparse
import json
import math
from pathlib import Path
import sys

EXPECTED_SHA = "aca6072e8aee51a4f0448d28a715f41ea07f00d648e4aad4324906a4fccd6899"
EXPECTED = {"tasks": 8, "queries": 16, "unique_sources": 32, "observations": 44, "k": 6}
MINIMUM = {"recall": .90, "mrr": .95, "paper_and_code": 1.0, "complete_pair_recall": .85}


def check(report):
    failures = []
    if not isinstance(report, dict):
        return {"passed": False, "failures": ["invalid report"]}
    if report.get("dataset_sha256") != EXPECTED_SHA:
        failures.append("dataset fingerprint changed")
    for key, expected in EXPECTED.items():
        if type(report.get(key)) is not int or report[key] != expected:
            failures.append("fixture shape changed: " + key)
    methods = report.get("methods")
    if not isinstance(methods, dict):
        failures.append("missing ranking methods")
        methods = {}
    for name in ("fixed_order", "stemmed_bm25", "sqlite_porter", "facet_rank", "evidence_shortlist"):
        overall = methods.get(name, {}).get("overall", {}) if isinstance(methods.get(name), dict) else {}
        for key in MINIMUM:
            value = overall.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                failures.append("invalid metric: " + name + "." + key)
            elif name == "evidence_shortlist" and value < MINIMUM[key]:
                failures.append("shortlist quality regression: " + key)
    per_query = report.get("per_query")
    if not isinstance(per_query, list) or len(per_query) != EXPECTED["queries"]:
        failures.append("missing per-query audit")
    elif any(not isinstance(row, dict) or row.get("unique_identities") != EXPECTED["unique_sources"]
             or row.get("duplicates_collapsed") != EXPECTED["observations"] - EXPECTED["unique_sources"]
             for row in per_query):
        failures.append("identity collapse regression")
    return {"passed": not failures, "failures": failures, "minimum": MINIMUM,
            "scope": "fixed development replay; not independent live search or repair-success certification"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = check(json.loads(args.report.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
