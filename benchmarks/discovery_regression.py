#!/usr/bin/env python3
"""Release gates for fixed, source-linked development retrieval fixtures."""
import argparse
import json
import math
import sys
from pathlib import Path

ORIGINAL = "aca6072e8aee51a4f0448d28a715f41ea07f00d648e4aad4324906a4fccd6899"
TRANSFER = "bf6be74c670d50667b6d68e5d15a296e34aaa5d74001427143de594e5c967286"
EXPECTED = {
    "original": (ORIGINAL, None, 16, 32, 44, 0.96, 0.95),
    "transfer": (TRANSFER, ORIGINAL, 18, 56, 68, 0.94, 0.92),
}
METRICS = ("recall", "complete_pair_recall", "ndcg", "mrr", "paper_and_code")


def check(original, transfer):
    errors = []
    for name, report in (("original", original), ("transfer", transfer)):
        sha, background, count, identities, observations, recall_floor, pair_floor = EXPECTED[name]
        expected = {"dataset_sha256": sha, "background_sha256": background,
                    "queries": count, "unique_sources": identities, "observations": observations, "k": 6}
        for key, value in expected.items():
            if report.get(key) != value:
                errors.append(f"{name}: {key} changed")
        try:
            methods = report["methods"]
            per_query = report["per_query"]
            if len(per_query) != count or len({(q["task"], q["formulation"]) for q in per_query}) != count:
                errors.append(f"{name}: incomplete or duplicated query evaluation")
            for q in per_query:
                if q["unique_identities"] != identities or q["duplicates_collapsed"] != observations - identities:
                    errors.append(f"{name}: identity accounting changed")
                for method, ranking in q["rankings"].items():
                    if len(ranking) > 6 or len(set(ranking)) != len(ranking):
                        errors.append(f"{name}: invalid ranking in {method}")
            for method in ("stemmed_bm25", "sqlite_porter", "evidence_shortlist", "paired_rank"):
                for metric in METRICS:
                    value = methods[method]["overall"][metric]
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                        errors.append(f"{name}: invalid {method}/{metric}")
            base = methods["stemmed_bm25"]["overall"]
            default = methods["evidence_shortlist"]["overall"]
            paired = methods["paired_rank"]["overall"]
            if any(default[m] + 1e-6 < base[m] for m in ("recall", "ndcg", "complete_pair_recall")):
                errors.append(f"{name}: default evidence ranking regressed below lexical baseline")
            if paired["recall"] < recall_floor or paired["complete_pair_recall"] < pair_floor:
                errors.append(f"{name}: paired quality below release floor")
            for baseline in ("stemmed_bm25", "sqlite_porter"):
                if any(paired[m] + 1e-6 < methods[baseline]["overall"][m] for m in ("recall", "complete_pair_recall", "ndcg")):
                    errors.append(f"{name}: paired quality below {baseline}")
        except (KeyError, TypeError, ValueError, AttributeError):
            errors.append(f"{name}: malformed report")
    return {"passed": not errors, "failures": errors,
            "scope": "Frozen curated development fixtures, not held-out or live provider accuracy."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--transfer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(json.loads(args.original.read_text(encoding="utf-8")),
                   json.loads(args.transfer.read_text(encoding="utf-8")))
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
