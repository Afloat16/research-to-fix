#!/usr/bin/env python3
"""Parity-only performance diagnostic, never use relevance labels for tuning."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
from time import perf_counter_ns

from retrieval import load_beir, percentile
import research_case as rc
from numpy_rank import NumpyRanker


def run(data):
    corpus, queries, meta = load_beir(data, 0)
    start = perf_counter_ns()
    index = rc.FieldIndex([(row["id"], *rc.field_counts(rc._recall_excerpt(row["title"], 1000),
                         rc._recall_excerpt(row["text"], 9000), "precision")) for row in corpus])
    build_ms = (perf_counter_ns() - start) / 1e6
    start = perf_counter_ns()
    vector = NumpyRanker(index)
    wrapper_ms = (perf_counter_ns() - start) / 1e6
    prepared = [rc.precision_tokens(row["text"]) for row in queries]
    # Check exact scores and ID sequence, not only metrics or approximate sums.
    for terms in prepared:
        if vector.rank(terms, 11, False) != index.rank(terms, 11, False):
            raise RuntimeError("Vector scorer differs from reference")
    timings = {"python": [], "numpy": []}
    for repeat in range(3):
        methods = (("python", index), ("numpy", vector))
        for name, ranker in methods if repeat % 2 == 0 else methods[::-1]:
            for terms in prepared:
                start = perf_counter_ns()
                ranker.rank(terms, 11, False)
                timings[name].append((perf_counter_ns() - start) / 1e6)
    stats = {name: {"p50_ms": statistics.median(times), "p95_ms": percentile(times, .95),
                    "total_ms_per_repeat": sum(times) / 3} for name, times in timings.items()}
    return {"dataset_sha256": meta["files_sha256"], "documents": len(corpus), "queries": len(queries),
            "repeats": 3, "exact_top11_scores_and_ids": True, "index_build_ms": build_ms,
            "vector_wrapper_ms": wrapper_ms, "methods": stats,
            "p50_speedup": stats["python"]["p50_ms"] / stats["numpy"]["p50_ms"],
            "p95_speedup": stats["python"]["p95_ms"] / stats["numpy"]["p95_ms"],
            "scope": "Prepared-token score-only query path; same postings and exact Top-K, not full retrieval/build speed. Optional NumPy, O(document count) scratch."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.data)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print("VECTOR_SUMMARY", json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
