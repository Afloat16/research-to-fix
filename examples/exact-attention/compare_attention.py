#!/usr/bin/env python3
"""Matched CPU/Python experiment for exact attention workspace reduction."""
import argparse
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys
from time import perf_counter_ns
import tracemalloc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "research-to-fix" / "scripts"))
import research_workflow as w
import solution_compare as sc

SEEDS = (11, 23, 37, 41, 59)
QUERY_COUNT = 96
KEY_COUNT = 192
DIM = 16
VALUE_DIM = 8
TOL = 1e-10
BLOCK = 24
# These are leads from bibliographic records, not a claim of full-text or
# third-party implementation reproduction. All methods here are local.
EVIDENCE = [
    {"id": "E1", "url": "https://arxiv.org/abs/2112.05682", "access": "metadata",
     "claim": "The abstract describes memory-efficient exact attention without quadratic workspace.",
     "conditions": "Attention computation; the article addresses accelerator memory and differentiation.",
     "limitations": "This example is forward-only scalar Python, not a reproduction of reported GPU results."},
    {"id": "E2", "url": "https://arxiv.org/abs/2205.14135", "access": "metadata",
     "claim": "The abstract describes tiled exact attention and reducing GPU memory traffic.",
     "conditions": "IO-aware GPU implementation and associated hardware assumptions.",
     "limitations": "No GPU kernel, autograd or external source code is used in this example."},
    {"id": "E3", "url": "https://arxiv.org/abs/1805.02867", "access": "metadata",
     "claim": "The abstract discusses online computation of a softmax normalizer.",
     "conditions": "Softmax normalization.",
     "limitations": "The recurrence below is derived locally from the softmax definition; not a paper reproduction."},
]


def dot(q, k):
    return math.fsum(a * b for a, b in zip(q, k)) / math.sqrt(len(q))


def validate(q, k, v, causal=False):
    if not q or not k or len(k) != len(v) or not q[0] or not v[0]:
        raise ValueError("invalid dimensions")
    if any(len(row) != len(q[0]) for row in q + k) or any(len(row) != len(v[0]) for row in v):
        raise ValueError("invalid dimensions")
    if causal and len(q) != len(k):
        raise ValueError("causal fixture requires equal sequence lengths")


def normalized_row(scores, values):
    maximum = max(scores)
    weights = [math.exp(score - maximum) for score in scores]
    denom = math.fsum(weights)
    return [math.fsum(weight * value[col] for weight, value in zip(weights, values)) / denom
            for col in range(len(values[0]))]


def materialized(q, k, v, causal=False):
    """Dense baseline, stable row softmax; stores every score and weight row."""
    validate(q, k, v, causal)
    scores = [[dot(query, key) for key in k[:i + 1] if causal] if causal
              else [dot(query, key) for key in k] for i, query in enumerate(q)]
    return [normalized_row(row, v[:len(row)]) for row in scores]


def rowwise(q, k, v, causal=False):
    """Exact stable attention with one score row retained."""
    validate(q, k, v, causal)
    output = []
    for i, query in enumerate(q):
        n = i + 1 if causal else len(k)
        scores = [dot(query, k[j]) for j in range(n)]
        output.append(normalized_row(scores, v[:n]))
    return output


def blocked(q, k, v, causal=False):
    """Merge stable block summaries, without materializing a full score row."""
    validate(q, k, v, causal)
    output = []
    for i, query in enumerate(q):
        n = i + 1 if causal else len(k)
        max_so_far, total = -math.inf, 0.0
        sums = [0.0] * len(v[0])
        for start in range(0, n, BLOCK):
            end = min(n, start + BLOCK)
            scores = [dot(query, k[j]) for j in range(start, end)]
            m = max(max_so_far, max(scores))
            prior = math.exp(max_so_far - m)
            weights = [math.exp(score - m) for score in scores]
            total = total * prior + math.fsum(weights)
            for col in range(len(sums)):
                sums[col] = sums[col] * prior + math.fsum(
                    weights[j - start] * v[j][col] for j in range(start, end))
            max_so_far = m
        output.append([value / total for value in sums])
    return output


def online(q, k, v, causal=False):
    """Stable one-key recurrence; O(value dimension) extra per-row state."""
    validate(q, k, v, causal)
    output = []
    for i, query in enumerate(q):
        n = i + 1 if causal else len(k)
        maximum, total = -math.inf, 0.0
        sums = [0.0] * len(v[0])
        for j in range(n):
            score = dot(query, k[j])
            m = max(maximum, score)
            a, b = math.exp(maximum - m), math.exp(score - m)
            total = total * a + b
            for col, value in enumerate(v[j]):
                sums[col] = sums[col] * a + b * value
            maximum = m
        output.append([value / total for value in sums])
    return output


METHODS = {"materialized": materialized, "rowwise": rowwise, "blocked": blocked, "online": online}


def oracle(q, k, v, causal=False):
    # Independent direct definition, using math.fsum and a separate stable
    # normalization. We explicitly compare every output element.
    scale = len(q[0]) ** -.5
    result = []
    for i, query in enumerate(q):
        n = i + 1 if causal else len(k)
        logits = [math.fsum(query[d] * k[j][d] for d in range(len(query))) * scale for j in range(n)]
        shift = max(logits)
        weights = [math.exp(x - shift) for x in logits]
        denom = math.fsum(weights)
        result.append([math.fsum((weights[j] / denom) * v[j][col] for j in range(n))
                       for col in range(len(v[0]))])
    return result


def error(result, expected):
    if len(result) != len(expected) or any(len(a) != len(b) for a, b in zip(result, expected)):
        return 1e100
    diffs = [abs(a - b) for row, ref in zip(result, expected) for a, b in zip(row, ref)]
    return max(diffs) if diffs and all(math.isfinite(x) for x in diffs) else 1e100


def sample(seed):
    rng = random.Random(seed)
    # Include scale variation to exercise stable exponentiation.
    q = [[rng.uniform(-2, 2) * (1 + seed % 3) for _ in range(DIM)] for _ in range(QUERY_COUNT)]
    k = [[rng.uniform(-2, 2) for _ in range(DIM)] for _ in range(KEY_COUNT)]
    v = [[rng.uniform(-1, 1) for _ in range(VALUE_DIM)] for _ in range(KEY_COUNT)]
    return q, k, v


def regressions(method):
    q, k, v = [[1000.0], [-1000.0]], [[1000.0], [-1000.0]], [[1.0], [3.0]]
    if error(method(q, k, v, True), [[1.0], [3.0]]) > TOL:
        return False
    if error(method([[0.0]], [[0.0], [0.0]], [[1.0], [3.0]]), [[2.0]]) > TOL:
        return False
    try:
        method([[1.0]], [], [])
    except ValueError:
        return True
    return False


def measure(method, q, k, v, expected):
    durations = []
    for _ in range(3):
        start = perf_counter_ns()
        result = method(q, k, v)
        durations.append((perf_counter_ns() - start) / 1e6)
    tracemalloc.start()
    try:
        traced = method(q, k, v)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    if result != traced:
        raise RuntimeError("nondeterministic candidate")
    maximum_error = error(result, expected)
    return {"max_abs_error": maximum_error, "latency_ms": statistics.median(durations),
            "peak_bytes": peak}, {"original": "pass" if maximum_error <= TOL else "fail",
            "regression": "pass" if regressions(method) else "fail"}, f"max_abs_error={maximum_error:.17g}"


def experiment(output):
    output.mkdir(parents=True, exist_ok=False)
    context = {"dataset": f"seeded uniform matrices Q={QUERY_COUNT}, K={KEY_COUNT}, D={DIM}, V={VALUE_DIM}",
               "python": platform.python_version(), "hardware": platform.system() + " " + platform.machine(),
               "dtype": "Python binary64 floats", "scope": "unmasked forward CPU; inputs excluded, output included in traced allocation",
               "timing": "median of 3 calls, separate allocation measurement"}
    protocol = {"id": "exact-attention-v1", "context": context, "command": "compare_attention.measure",
                "replicates": [str(seed) for seed in SEEDS],
                "objectives": [{"id": "max_abs_error", "direction": "min", "unit": "absolute", "threshold": TOL,
                                "resolution": TOL},
                               {"id": "latency_ms", "direction": "min", "unit": "ms", "resolution": .1},
                               {"id": "peak_bytes", "direction": "min", "unit": "B", "resolution": 64}],
                "checks": [{"id": "original", "kind": "original", "description": "every output matches stable reference within fixed tolerance"},
                           {"id": "regression", "kind": "regression", "description": "causal extreme logits, uniform weights, empty input"}],
                "decision_policy": "all_pairs"}
    # Persist protocol and lock before the first candidate execution.
    lock = sc.freeze_protocol(protocol)
    w.write_json(protocol, output / "protocol.json")
    w.write_json(lock, output / "protocol-lock.json")
    descriptions = {"materialized": ("Full score matrix", "dense matrix", []),
                    "rowwise": ("Row streaming", "one score row", ["E1"]),
                    "blocked": ("Block summary merge", "rescale block max, denominator and weighted values", ["E1", "E2", "E3"]),
                    "online": ("Per-key online recurrence", "update stable weighted value accumulator", ["E1", "E3"])}
    candidates = {}
    for name, (title, mechanism, refs) in descriptions.items():
        candidates[name] = {"id": name, "title": title, "basis": "baseline" if name == "materialized" else "local",
                            "state": "measured", "mechanism": mechanism, "local_target": "attention forward",
                            "hypothesis": "preserve stable exact forward results with less score workspace",
                            "change": mechanism, "evidence_ids": refs, "protocol_id": protocol["id"],
                            "context": dict(context), "runs": []}
    names = list(METHODS)
    for i, seed in enumerate(SEEDS):
        q, k, v = sample(seed)
        expected = oracle(q, k, v)
        for name in names[i % len(names):] + names[:i % len(names)]:
            metrics, checks, observed = measure(METHODS[name], q, k, v, expected)
            candidates[name]["runs"].append({"replicate": str(seed), "command": protocol["command"],
                                           "metrics": metrics, "checks": checks, "observed": observed})
    record = {"schema_version": 1, "protocol": protocol, "protocol_sha256": lock["protocol_sha256"],
              "evidence": EVIDENCE, "candidates": list(candidates.values())}
    report = sc.compare(record, lock)
    by_id = {row["id"]: row for row in report["candidates"]}
    if not all(row["eligible"] for row in by_id.values()):
        raise RuntimeError("exactness or regression check failed")
    for seed_index in range(len(SEEDS)):
        baseline = candidates["materialized"]["runs"][seed_index]["metrics"]["peak_bytes"]
        if candidates["rowwise"]["runs"][seed_index]["metrics"]["peak_bytes"] >= baseline:
            raise RuntimeError("rowwise workspace did not decrease")
    w.write_json(record, output / "comparison.json")
    w.write_json(report, output / "report.json")
    return {"protocol": report["protocol_id"], "replicates": report["replicates"],
            "decision": report["decision"], "frontier": report["pareto_frontier"],
            "median_frontier": report["median_frontier"], "all_pairs_frontier": report["all_pairs_frontier"],
            "lock_checked": report["protocol_lock_checked"],
            "candidates": {name: {"eligible": row["eligible"], "metrics": row["metrics"]} for name, row in by_id.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(experiment(args.output), indent=2))


if __name__ == "__main__":
    main()
