#!/usr/bin/env python3
"""Exact top-k vector search: measured alternative mechanisms under a locked protocol."""
import argparse
import heapq
import json
from pathlib import Path
import platform
import random
import statistics
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/research-to-fix/scripts"))
import solution_compare as sc
import research_workflow as w

SEEDS = (11, 23, 37, 41, 59)
N, D, K, BLOCK = 8192, 16, 10, 256
COMMAND = "compare_methods.measure(vectors, query, method)"


def distances(vectors, query):
    for i, vector in enumerate(vectors):
        yield sum((a-b) * (a-b) for a, b in zip(vector, query)), i


def full_sort(vectors, query, k):
    return sorted(distances(vectors, query))[:k]


def heap_select(vectors, query, k):
    return heapq.nsmallest(k, distances(vectors, query))


def blocked_select(vectors, query, k):
    if k <= 0:
        return []
    best, block = [], []
    for entry in distances(vectors, query):
        block.append(entry)
        if len(block) == BLOCK:
            best = sorted(best + block)[:k]
            block.clear()
    return sorted(best + block)[:k]


METHODS = {"full_sort": full_sort, "heap_select": heap_select, "blocked_select": blocked_select}


def oracle(vectors, query, k):
    # Independent integer algebra for the same squared Euclidean metric.
    q2 = sum(x*x for x in query)
    return sorted((sum(x*x for x in v) + q2 - 2*sum(a*b for a, b in zip(v, query)), i)
                  for i, v in enumerate(vectors))[:max(0, k)]


def inputs(seed):
    rng = random.Random(seed)
    vectors = [tuple(rng.randrange(-32, 33) for _ in range(D)) for _ in range(N)]
    query = tuple(rng.randrange(-32, 33) for _ in range(D))
    # Force equal-distance ties at the boundary without relying on RNG.
    vectors[0] = vectors[1] = query
    return vectors, query


def regression(method):
    for vectors, query, k in (([], (0, 0), 2),
                               ([(0, 0), (0, 0), (1, 0)], (0, 0), 1),
                               ([(1, 0), (-1, 0), (0, 1)], (0, 0), 2),
                               ([(2, 1), (0, 1)], (0, 0), 0),
                               ([(2, 1), (0, 1)], (0, 0), 20)):
        if method(vectors, query, k) != oracle(vectors, query, k):
            return False
    return True


def measure(vectors, query, method, expected):
    times = []
    for _ in range(3):
        start = time.perf_counter_ns()
        result = method(vectors, query, K)
        times.append((time.perf_counter_ns() - start) / 1e6)
        if result != expected:
            raise RuntimeError("exact_topk_mismatch")
    tracemalloc.start()
    try:
        measured = method(vectors, query, K)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return ({"latency_ms": statistics.median(times), "peak_bytes": peak},
            {"exact_topk": "pass" if measured == expected else "fail",
             "edge_cases": "pass" if regression(method) else "fail"},
            "Exact squared distances and deterministic index tie-breaking checked against integer oracle")


def experiment(output):
    context = {"dataset": "8192 fixed-seed integer vectors, 16 dimensions, range -32..32, duplicate ties",
               "metric": "squared Euclidean distance; order by (distance,index); k=10",
               "python": platform.python_version(), "machine": platform.machine(),
               "timing": "median of 3 calls; separate tracemalloc run, input allocation excluded"}
    protocol = {"id": "exact-topk-v2", "context": context, "command": COMMAND,
                "replicates": [f"seed-{seed}" for seed in SEEDS], "minimum_replicates": 5,
                "dominance_mode": "paired_conservative",
                "objectives": [{"id": "latency_ms", "direction": "min", "unit": "ms",
                                "minimum_improvement": .1},
                               {"id": "peak_bytes", "direction": "min", "unit": "B",
                                "minimum_improvement": 1024}],
                "checks": [{"id": "exact_topk", "kind": "original",
                            "description": "exact output equals independent integer oracle"},
                           {"id": "edge_cases", "kind": "regression",
                            "description": "empty, ties, k=0 and k>n preserved"}]}
    lock = sc.protocol_lock(protocol)
    w.write_json(protocol, output / "protocol.json")
    w.write_json(lock, output / "protocol-lock.json")
    evidence = [{"id": "E1", "url": "https://docs.python.org/3/library/heapq.html#heapq.nsmallest",
                 "access": "read", "claim": "nsmallest selects the requested number of smallest elements; suited to small k.",
                 "conditions": "Python stdlib; comparable tuple entries; finite input.",
                 "limitations": "No claim about vector search speed; tested locally."},
                {"id": "E2", "url": "https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index",
                 "access": "read", "claim": "Exhaustive search is an exact baseline; partitioned searches may be combined.",
                 "conditions": "Faiss index guidance; our implementation is independent pure Python.",
                 "limitations": "Not a Faiss runtime comparison; no ANN or GPU speed claim."}]
    descriptions = {
        "full_sort": ("Exhaustive sorting", "baseline", [], "Sort all distances"),
        "heap_select": ("Bounded heap selection", "mixed", ["E1"], "Keep k smallest pairs"),
        "blocked_select": ("Blockwise exact merge", "mixed", ["E2"], "Keep exact k-best after each block"),
    }
    candidates = {}
    for name, (title, basis, refs, mechanism) in descriptions.items():
        row = {"id": name, "title": title, "basis": basis, "evidence_ids": refs,
               "support_ids": refs, "variant_id": name, "protocol_id": protocol["id"],
               "protocol_sha256": lock["protocol_sha256"], "context": dict(context),
               "state": "measured", "mechanism": mechanism, "local_target": "exact top-k selection",
               "hypothesis": "Reduce selection memory while preserving exact output",
               "change": mechanism, "runs": []}
        if basis == "mixed":
            row.update(applicability="adapted", applicability_note="Same exact ordered distance semantics; tested",
                       license_status="not_copied", license_note="Independent implementation using stdlib API")
        candidates[name] = row
    names = list(METHODS)
    for i, seed in enumerate(SEEDS):
        vectors, query = inputs(seed)
        expected = oracle(vectors, query, K)
        for name in names[i % len(names):] + names[:i % len(names)]:
            metrics, checks, observed = measure(vectors, query, METHODS[name], expected)
            candidates[name]["runs"].append({"replicate": f"seed-{seed}", "variant_id": name,
                                             "command": COMMAND, "exit_code": 0,
                                             "metrics": metrics, "checks": checks, "observed": observed})
    comparison = {"schema_version": 2, "protocol": protocol, "evidence": evidence,
                  "candidates": list(candidates.values())}
    report = sc.compare(comparison, lock)
    if not all(row["eligible"] for row in report["candidates"]):
        raise RuntimeError("exact_topk_regression")
    w.write_json(comparison, output / "comparison.json")
    w.write_json(report, output / "report.json")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = experiment(args.output)
    print(json.dumps({"experiment": "exact-topk-v2", "replicates": report["replicates"],
                      "protocol_lock_checked": report["protocol_lock_checked"],
                      "frontier": report["pareto_frontier"], "decision": report["decision"],
                      "candidates": {row["id"]: row["metrics"] for row in report["candidates"]}}, indent=2))


if __name__ == "__main__":
    main()
