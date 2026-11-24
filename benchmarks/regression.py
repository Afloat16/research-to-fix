#!/usr/bin/env python3
"""Deterministic regression gates for the committed development fixtures."""
import argparse
import json
from pathlib import Path
import sys

EXPECTED = {
    "synthetic": "5d88bf32d7eba9abf2f78033589d5159e5b059b29be1ba85cfcc12a83b79fe57",
    "github": "e4999d999db31a69d758bbcd9f4f7e9342524b270538b31791d7b0f34b220e1a",
}


def check(synthetic, github, scale):
    failures, warnings = [], []
    for name, report in (("synthetic", synthetic), ("github", github)):
        if report["dataset"]["sha256"] != EXPECTED[name]:
            failures.append(name + ": fixture fingerprint changed; review labels and update gates explicitly")
        if report["k"] != 5 or report["legacy_indexed_top_k_exact_match"] is not True:
            failures.append(name + ": legacy/indexed top-k parity lost")
        for method in ("legacy_scan", "indexed_bm25", "technical", "stemmed", "hybrid", "contextual"):
            if report["methods"][method]["status"] != "completed":
                failures.append(name + ": incomplete method " + method)
    if synthetic["methods"]["indexed_bm25"]["ndcg@5"] < 0.9527:
        failures.append("synthetic: legacy ranking quality regressed")
    if synthetic["methods"]["hybrid"]["ndcg@5"] < 0.97:
        failures.append("synthetic: hybrid ranking quality regressed")
    if any(synthetic["methods"][method]["negative_abstention"] != 1
           for method in ("indexed_bm25", "technical", "stemmed", "hybrid", "contextual")):
        failures.append("synthetic: unrelated-query abstention regressed")
    if github["methods"]["stemmed"]["recall@5"] < 0.83 or github["methods"]["stemmed"]["mrr@5"] < 0.70:
        failures.append("github: stemmed ranking quality regressed")
    if scale["dataset"]["sha256"] != EXPECTED["synthetic"]:
        failures.append("scale: fixture fingerprint changed")
    if scale["batch_recall"]["identical_reports"] is not True:
        failures.append("batch: report parity lost")
    if scale["index_scale"]["exact_top_10_scores"] is not True:
        failures.append("index: exact scores lost")
    if scale["index_scale"]["retained_memory_reduction_factor"] < 2:
        failures.append("index: compact allocation advantage below 2x")
    # Latency on shared CI machines is noisy. Emit wide warning bands rather
    # than brittle hard failures; investigate actual paired timings.
    if scale["batch_recall"]["speedup"] < 4:
        warnings.append("batch speedup below 4x; investigate paired timings")
    if scale["index_scale"]["warm_query_speedup"] < 5:
        warnings.append("warm query speedup below 5x; investigate paired timings")
    return {"passed": not failures, "failures": failures, "warnings": warnings,
            "scope": "fixed development fixtures; not an independent held-out benchmark or repair-success certification"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", required=True, type=Path)
    parser.add_argument("--github", required=True, type=Path)
    parser.add_argument("--scale", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    report = check(read(args.synthetic), read(args.github), read(args.scale))
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
