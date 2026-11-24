#!/usr/bin/env python3
"""Run a reproducible floating-point variance repair comparison (no downloads)."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
import random
import statistics
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "research-to-fix" / "scripts"))
import solution_compare as sc
import research_workflow as w

SEEDS = (11, 23, 37, 41, 59)
SIZE = 8192
OFFSET = 1_000_000_000
TOLERANCE = 1e-5
COMMAND = "compare_methods.measure(values, method)"
SOURCES = {
    "E1": {"url": "https://doi.org/10.1080/00401706.1962.10490022",
           "access": "metadata", "claim": "Welford's 1962 paper is a lead for corrected sums of squares.",
           "conditions": "Historical bibliographic source.",
           "limitations": "Full text not used; the online recurrence below is locally derived."},
    "E2": {"url": "https://numpy.org/doc/stable/reference/generated/numpy.var.html",
           "access": "read", "claim": "NumPy documents mean-centered squared deviations and accumulator precision.",
           "conditions": "Population variance with ddof=0; numeric array input.",
           "limitations": "Documentation is not a performance guarantee; this demo uses a local Python implementation."},
    "E3": {"url": "https://docs.python.org/3/library/statistics.html#statistics.pvariance",
           "access": "read", "claim": "The standard library exposes population variance.",
           "conditions": "Nonempty real-valued data; population, not sample variance.",
           "limitations": "Local interpreter performance and finite-input tests only."},
}


def naive(values):
    n = len(values)
    if not n:
        raise ValueError("empty")
    mean = sum(values) / n
    return sum(value * value for value in values) / n - mean * mean


def centered(values):
    n = len(values)
    if not n:
        raise ValueError("empty")
    origin = values[0]
    # Subtract a nearby origin before averaging, then center the shifted
    # values. fsum controls accumulation error without copying the input.
    mean = math.fsum(value - origin for value in values) / n
    return math.fsum(((value - origin) - mean) ** 2 for value in values) / n


def online(values):
    # Derive the recurrence from M2=sum((x-mean)^2); no third-party code copied.
    n, mean, m2 = 0, 0.0, 0.0
    for value in values:
        n += 1
        delta = value - mean
        mean += delta / n
        m2 += delta * (value - mean)
    if not n:
        raise ValueError("empty")
    return m2 / n


METHODS = {"naive": naive, "centered": centered, "online": online,
           "stdlib": statistics.pvariance}


def inputs(seed):
    rng = random.Random(seed)
    integers = [rng.randrange(-16, 17) for _ in range(SIZE)]
    # These integer-valued floats are exactly representable. The oracle uses
    # Python integer arithmetic on the small offsets, not any tested method.
    numerator = SIZE * sum(v * v for v in integers) - sum(integers) ** 2
    expected = numerator / (SIZE * SIZE)
    return [float(OFFSET + value) for value in integers], expected


def regressions(method):
    try:
        method([])
    except (ValueError, statistics.StatisticsError):
        empty_rejected = True
    else:
        empty_rejected = False
    return (empty_rejected and method([2.0] * 10) == 0.0
            and abs(method([1.0, 2.0, 3.0]) - 2 / 3) < 1e-12)


def measure(values, expected, method):
    measured = []
    for _ in range(3):
        start = time.perf_counter_ns()
        actual = method(values)
        measured.append((time.perf_counter_ns() - start) / 1e6)
    tracemalloc.start()
    try:
        traced_actual = method(values)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    if actual != traced_actual or not math.isfinite(actual):
        raise RuntimeError("non-finite or nondeterministic variance result")
    error = abs(actual - expected) / expected
    return ({"relative_error": error, "latency_ms": statistics.median(measured),
             "peak_bytes": peak},
            {"original_accuracy": "pass" if error <= TOLERANCE and actual >= 0 else "fail",
             "regression": "pass" if regressions(method) else "fail"},
            f"variance={actual:.17g}; exact integer-moment oracle={expected:.17g}")


def experiment():
    ctx = {"dataset": f"seeded integers in [-16,16] plus {OFFSET}; n={SIZE}",
           "dtype": "Python float (binary64 on tested CPython)",
           "python": platform.python_version(),
           "platform": platform.system() + " " + platform.machine(),
           "timing": "median of 3 in-process calls; tracing separate; inputs excluded from allocation"}
    protocol = {"id": "variance-v1", "context": ctx, "command": COMMAND,
                "replicates": [f"seed-{seed}" for seed in SEEDS],
                "objectives": [{"id": "relative_error", "unit": "ratio", "direction": "min", "threshold": TOLERANCE},
                               {"id": "latency_ms", "unit": "ms", "direction": "min"},
                               {"id": "peak_bytes", "unit": "B", "direction": "min"}],
                "checks": [{"id": "original_accuracy", "kind": "original",
                            "description": "nonnegative variance with relative error <= 1e-5"},
                           {"id": "regression", "kind": "regression",
                            "description": "reject empty input and preserve constant/simple population variance"}]}
    descriptions = {
        "naive": ("Baseline raw moments", "baseline", [], "raw moments",
                  "subtract squared mean from mean square"),
        "centered": ("Shifted two-pass with fsum", "mixed", ["E2"], "centered moments and accurate summation",
                     "shift by the first value and compute two centered passes"),
        "online": ("One-pass corrected moments", "local", ["E1"], "online corrected second moment",
                   "update mean and corrected sum of squares incrementally"),
        "stdlib": ("Standard-library pvariance", "external", ["E3"], "population variance API",
                   "use the standard-library population variance function"),
    }
    candidates = {}
    for key, (title, basis, refs, mechanism, change) in descriptions.items():
        candidates[key] = {"id": key, "title": title, "basis": basis, "evidence_ids": refs,
                           "mechanism": mechanism, "local_target": "variance computation",
                           "hypothesis": "Avoid raw-moment cancellation while preserving population-variance semantics.",
                           "change": change, "protocol_id": protocol["id"], "context": dict(ctx),
                           "state": "measured", "runs": []}
    names = list(METHODS)
    for i, seed in enumerate(SEEDS):
        values, expected = inputs(seed)
        # Rotate order to reduce warm-up/order effects. All methods see the
        # same input values, same interpreter and same measurement harness.
        for key in names[i % len(names):] + names[:i % len(names)]:
            measured, checks, observation = measure(values, expected, METHODS[key])
            candidates[key]["runs"].append({"replicate": f"seed-{seed}", "command": COMMAND,
                                           "observed": observation, "metrics": measured, "checks": checks})
    record = {"schema_version": 1, "protocol": protocol,
              "evidence": [{"id": key, **value} for key, value in SOURCES.items()],
              "candidates": list(candidates.values())}
    report = sc.compare(record)
    by_id = {row["id"]: row for row in report["candidates"]}
    if by_id["naive"]["eligible"] or not all(by_id[key]["eligible"] for key in METHODS if key != "naive"):
        raise RuntimeError("accuracy/regression gate failed: expected baseline failure and viable alternatives")
    return record, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    record, report = experiment()
    w.write_json(record, args.output / "comparison.json")
    w.write_json(report, args.output / "report.json")
    print(json.dumps({"protocol": report["protocol_id"], "replicates": report["replicates"],
                      "frontier": report["pareto_frontier"], "decision": report["decision"],
                      "candidates": {row["id"]: {"eligible": row["eligible"], "metrics": row["metrics"]}
                                     for row in report["candidates"]}}, indent=2))


if __name__ == "__main__":
    main()
