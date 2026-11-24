#!/usr/bin/env python3
"""Exact v1.1.0 full-explanation reference versus bounded explanation.

Generated workload, no relevance labels; timing excludes tokenization and
index construction. Measure both low and high posting coverage, never claim
repair accuracy. Run the same queries and compare complete public results.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import random
import statistics
from time import perf_counter_ns
import tracemalloc

import retrieval
rc = retrieval.rc


def legacy(index, terms, limit, threshold):
    ranked = index.rank(terms)
    best = ranked[0][0] if ranked else 0.
    retained = [row for row in ranked if row[0] >= threshold * best]
    return len(retained), retained[:limit]


def evaluate(documents=5000, queries=48, repeats=3):
    rng = random.Random(411913)
    rare = [f"rare{i}" for i in range(8192)]
    common = [f"common{i}" for i in range(24)]
    docs = [(f"doc{i:06d}", Counter(rng.choices(common, k=4) + rng.choices(rare, k=12)),
             Counter(rng.choices(common, k=18) + rng.choices(rare, k=36)))
            for i in range(documents)]
    scenarios = {
        "sparse": [rng.sample(rare, 5) for _ in range(queries)],
        "mixed": [rng.sample(common, 2) + rng.sample(rare, 5) for _ in range(queries)],
        "dense": [rng.sample(common, 12) for _ in range(queries)],
    }
    result = {}
    for name, build in (("bm25", lambda: rc.PostingIndex([(key, a + b) for key, a, b in docs])),
                        ("field", lambda: rc.FieldIndex(docs))):
        index = build()
        for scenario, terms_list in scenarios.items():
            threshold = rc.RECALL_RELATIVE_THRESHOLD
            limit = 5
            old = lambda terms: legacy(index, terms, limit, threshold)
            new = lambda terms: index.rank_relative(terms, limit, threshold)
            expected = [old(terms) for terms in terms_list]
            if expected != [new(terms) for terms in terms_list]:
                raise RuntimeError("exact threshold/top-k/explanation parity lost")
            timings = {"full": [], "bounded": []}
            methods = [("full", old), ("bounded", new)]
            for iteration in range(repeats):
                for label, run in (methods if iteration % 2 == 0 else methods[::-1]):
                    for terms in terms_list:
                        start = perf_counter_ns()
                        run(terms)
                        timings[label].append((perf_counter_ns() - start) / 1e6)
            # Separate allocation tracing from timing; identical fixed query.
            peaks = {}
            for label, run in methods:
                tracemalloc.start()
                try:
                    run(terms_list[0])
                    peaks[label] = tracemalloc.get_traced_memory()[1]
                finally:
                    tracemalloc.stop()
            summary = {label: {"p50_ms": statistics.median(times),
                               "p95_ms": retrieval.percentile(times, .95),
                               "sample_query_peak_bytes": peaks[label]}
                       for label, times in timings.items()}
            result[name + "_" + scenario] = {
                "exact_count_scores_ids_explanations": True,
                "median_retained_candidates": statistics.median(row[0] for row in expected),
                "methods": summary,
                "p50_speedup": summary["full"]["p50_ms"] / summary["bounded"]["p50_ms"],
                "p95_speedup": summary["full"]["p95_ms"] / summary["bounded"]["p95_ms"],
                "sample_query_peak_reduction": 1 - peaks["bounded"] / peaks["full"],
            }
    return {"documents": documents, "queries_per_scenario": queries, "repeats": repeats,
            "exact_parity_queries": 2 * len(scenarios) * queries, "limit": 5,
            "relative_threshold": rc.RECALL_RELATIVE_THRESHOLD,
            "python": platform.python_version(), "platform": platform.platform(),
            "scenarios": result,
            "scope": "Generated prepared-token warm-index recall, including threshold count and explanations; not index build, end-to-end file I/O, relevance or repair accuracy. Single fixed query allocation sample per scenario."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate()
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print("RELATIVE_RECALL", json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
