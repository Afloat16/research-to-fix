#!/usr/bin/env python3
"""Independent BEIR retrieval: frozen v1.0.0 modes and native SQLite baselines.

Select the development/holdout partition without inspecting labels or results.
Benchmark metadata only; do not redistribute CC BY-SA corpus text.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import sqlite3
import statistics
import sys
from time import perf_counter_ns

from retrieval import load_beir, text_fields, SQLiteBaseline, metrics, percentile
import research_case as rc

METHODS = ("v1_bm25", "v1_technical", "v1_stemmed", "v1_hybrid", "v1_contextual",
           "sqlite_unicode", "sqlite_porter", "field2", "field4", "field8", "title_only")
K = 10
SEED = "r2f-independent-v1:2026-11-24:"
BOOTSTRAPS = 2000


def partition(queries, split):
    # Fixed 20% of programmer queries (hash bucket); no qrel-driven selection.
    def development(row):
        return int(hashlib.sha256((SEED + row["id"]).encode()).hexdigest()[:8], 16) % 5 == 0
    if split == "development":
        return [row for row in queries if development(row)]
    if split == "holdout":
        return [row for row in queries if not development(row)]
    return list(queries)


def paired_interval(left, right, resamples=BOOTSTRAPS):
    if len(left) != len(right) or not left:
        raise ValueError("paired sample required")
    deltas = [a - b for a, b in zip(left, right)]
    rng = random.Random(764291)
    samples = sorted(statistics.mean(rng.choices(deltas, k=len(deltas))) for _ in range(resamples))
    return {"mean_delta": statistics.mean(deltas),
            "ci95_low": samples[int(.025 * (len(samples) - 1))],
            "ci95_high": samples[int(.975 * (len(samples) - 1))],
            "win": sum(d > 0 for d in deltas), "tie": sum(d == 0 for d in deltas),
            "loss": sum(d < 0 for d in deltas), "resamples": resamples,
            "method": "paired percentile bootstrap, fixed seed; query-level descriptive interval"}


def build(corpus, method):
    if method.startswith("sqlite_"):
        sqlite = SQLiteBaseline(corpus, porter=method == "sqlite_porter")
        return sqlite.search, sqlite.db.close
    if method in ("field2", "field4", "field8", "title_only"):
        weights = {"field2": (2., 1.), "field4": (4., 1.), "field8": (8., 1.), "title_only": (1., 0.)}
        docs = [(row["id"], *rc.field_counts(rc._recall_excerpt(row["title"], 1000),
                                             rc._recall_excerpt(row["text"], 9000))) for row in corpus]
        index = rc.FieldIndex(docs, *weights[method])
        del docs
        def search(text, k):
            return [identifier for _, identifier, _ in index.rank(rc.ranking_tokens(text, "stemmed"), k, False)]
        return search, lambda: None
    mode = method.removeprefix("v1_")
    if mode not in rc.RANKING_MODES:
        raise ValueError("Unknown method")
    documents = [(row["id"], rc.ranking_counts(*text_fields(row), mode)) for row in corpus]
    index = rc.PostingIndex(documents)
    del documents
    def search(text, k):
        return [identifier for _, identifier, _ in index.rank(rc.ranking_tokens(text, mode), k, False)]
    return search, lambda: None


def evaluate(corpus, queries, metadata, methods=METHODS):
    results, per_method = {}, {}
    for method in methods:
        start = perf_counter_ns()
        search, close = build(corpus, method)
        build_ms = (perf_counter_ns() - start) / 1e6
        timings, rankings, scores = [], {}, []
        try:
            for row in queries:
                start = perf_counter_ns()
                ids = [i for i in search(row["text"], K + 1) if i != row["id"]][:K]
                timings.append((perf_counter_ns() - start) / 1e6)
                rankings[row["id"]] = ids
                scores.append(metrics(ids, row["relevant"], K))
        finally:
            close()
            del search
        per_method[method] = {"rankings": rankings, "scores": scores}
        results[method] = {**{key + "@10": statistics.mean(s[key] for s in scores)
                              for key in ("mrr", "ndcg", "recall", "hit")},
                           "build_ms": build_ms, "query_p50_ms": statistics.median(timings),
                           "query_p95_ms": percentile(timings, .95), "total_query_ms": sum(timings)}
        print("METHOD", method, json.dumps(results[method]), flush=True)
    comparisons = {}
    for method in methods:
        if method == "sqlite_porter" or "sqlite_porter" not in per_method:
            continue
        comparisons[method + "_vs_sqlite_porter"] = paired_interval(
            [s["ndcg"] for s in per_method[method]["scores"]],
            [s["ndcg"] for s in per_method["sqlite_porter"]["scores"]])
    return {"dataset": metadata, "documents": len(corpus), "queries": len(queries),
            "k": K, "methods": results, "paired_ndcg": comparisons,
            "environment": {"python": platform.python_version(), "platform": platform.platform(),
                            "sqlite": sqlite3.sqlite_version},
            "scope": "Full external corpus, binary official qrels, self-ID excluded, same capped document fields. "
                     "Ranking only; not end-to-end repair or live-search accuracy.",
            "query_ids": [row["id"] for row in queries],
            "rankings": {name: data["rankings"] for name, data in per_method.items()},
            "per_query": {name: data["scores"] for name, data in per_method.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "holdout", "all"), required=True)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.data / "manifest.json").read_text(encoding="utf-8"))
    corpus, queries, meta = load_beir(args.data, 0)
    if len(corpus) != manifest["expected_documents"] or len(queries) != manifest["expected_test_queries"]:
        raise ValueError("Unexpected official dataset size")
    if meta["files_sha256"] != {name: row["sha256"] for name, row in manifest["files"].items()}:
        raise ValueError("Dataset integrity mismatch")
    if args.split != "all" and manifest["dataset"] != "programmers":
        raise ValueError("Only programmers is partitioned")
    selected = partition(queries, args.split)
    result = evaluate(corpus, selected, {**manifest, "split": args.split,
                                       "partition_rule": SEED + "sha256 first 32 bits mod 5 == 0"}, args.methods)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print("INDEPENDENT_SUMMARY", json.dumps({k: v for k, v in result.items()
                                           if k not in ("rankings", "query_ids", "per_query")}), flush=True)


if __name__ == "__main__":
    main()
