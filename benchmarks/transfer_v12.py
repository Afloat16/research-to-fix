#!/usr/bin/env python3
"""Predeclared full Mathematica transfer: actual libraries, fixed methods."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sqlite3
import statistics
from time import perf_counter_ns

from compare_bm25s import bm25s_search
from independent_retrieval import build, paired_interval
from retrieval import load_beir, metrics, percentile, text_fields
import research_case as rc

METHODS = ("precision_field4", "v1_contextual", "v1_bm25", "sqlite_unicode4",
           "sqlite_porter", "bm25s_native", "bm25s_matched", "rank_bm25_matched")
K = 10


def rank_bm25_search(corpus):
    from rank_bm25 import BM25Okapi
    import numpy as np
    corpus = sorted(corpus, key=lambda row: row["id"])
    ids = [row["id"] for row in corpus]

    def tokens(text):
        return rc.ranking_tokens(text, "stemmed")

    retriever = BM25Okapi([tokens("\n".join(text_fields(row))) for row in corpus],
                           k1=1.5, b=.75, epsilon=.25)

    def search(text, k):
        query = sorted(set(tokens(text)))
        if not query:
            return []
        scores = retriever.get_scores(query)
        # Same stable ties and positive-match-only convention as BM25S.
        candidates = np.flatnonzero(scores > 0)
        if len(candidates) > k:
            boundary = np.partition(scores[candidates], len(candidates) - k)[len(candidates) - k]
            candidates = candidates[scores[candidates] >= boundary]
        ordered = candidates[np.argsort(-scores[candidates], kind="stable")][:k]
        return [ids[int(i)] for i in ordered]

    return search, lambda: None


def recall_parity(corpus, queries):
    index = rc.FieldIndex([(row["id"], *rc.field_counts(rc._recall_excerpt(row["title"], 1000),
                          rc._recall_excerpt(row["text"], 9000), "precision")) for row in corpus])
    prepared = [rc.precision_tokens(row["text"]) for row in queries]
    old_ms, new_ms = [], []
    for terms in prepared:
        start = perf_counter_ns()
        ranked = index.rank(terms)
        best = ranked[0][0] if ranked else 0.
        retained = [row for row in ranked if row[0] >= rc.RECALL_RELATIVE_THRESHOLD * best]
        expected = len(retained), retained[:K]
        old_ms.append((perf_counter_ns() - start) / 1e6)
        start = perf_counter_ns()
        actual = index.rank_relative(terms, K, rc.RECALL_RELATIVE_THRESHOLD)
        new_ms.append((perf_counter_ns() - start) / 1e6)
        if actual != expected:
            raise RuntimeError("Real corpus exact recall parity lost")
    return {"queries": len(queries), "exact_count_scores_ids_explanations": True,
            "full_p50_ms": statistics.median(old_ms), "bounded_p50_ms": statistics.median(new_ms),
            "full_p95_ms": percentile(old_ms, .95), "bounded_p95_ms": percentile(new_ms, .95),
            "p50_speedup": statistics.median(old_ms) / statistics.median(new_ms),
            "scope": "One paired pass, full explanation first, prepared tokens, warm index; no relevance impact."}


def evaluate(data):
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    corpus, queries, meta = load_beir(data, 0)
    if (manifest["dataset"] != "mathematica" or len(corpus) != 16705 or len(queries) != 804
            or meta["files_sha256"] != {name: row["sha256"] for name, row in manifest["files"].items()}):
        raise ValueError("Unexpected transfer corpus or data integrity mismatch")
    methods, detail = {}, {}
    for method in METHODS:
        start = perf_counter_ns()
        if method.startswith("bm25s_"):
            search, close = bm25s_search(corpus, method)
        elif method == "rank_bm25_matched":
            search, close = rank_bm25_search(corpus)
        else:
            search, close = build(corpus, method)
        build_ms = (perf_counter_ns() - start) / 1e6
        scores, timings, rankings = [], [], {}
        try:
            for row in queries:
                start = perf_counter_ns()
                ranking = [key for key in search(row["text"], K + 1) if key != row["id"]][:K]
                timings.append((perf_counter_ns() - start) / 1e6)
                scores.append(metrics(ranking, row["relevant"], K))
                rankings[row["id"]] = ranking
        finally:
            close()
            del search
        methods[method] = {**{key + "@10": statistics.mean(row[key] for row in scores)
                             for key in ("mrr", "ndcg", "recall", "hit")},
                           "build_ms": build_ms, "query_p50_ms": statistics.median(timings),
                           "query_p95_ms": percentile(timings, .95)}
        detail[method] = {"scores": scores, "rankings": rankings}
        print("TRANSFER_METHOD", method, json.dumps(methods[method]), flush=True)
    comparisons = {name: paired_interval([s["ndcg"] for s in detail["precision_field4"]["scores"]],
                                         [s["ndcg"] for s in detail[name]["scores"]])
                   for name in METHODS if name != "precision_field4"}
    parity = recall_parity(corpus, queries)
    return {"scope": "Predeclared transfer, binary qrels, no tuning; retrieval only.",
            "dataset": manifest, "documents": len(corpus), "queries": len(queries),
            "methods": methods, "paired_ndcg_precision_vs": comparisons, "exact_recall": parity,
            "environment": {"python": platform.python_version(), "platform": platform.platform(),
                            "sqlite": sqlite3.sqlite_version,
                            **{name: importlib.metadata.version(name) for name in
                               ("bm25s", "rank-bm25", "numpy", "scipy", "tqdm")}},
            "query_ids": [row["id"] for row in queries], "detail": detail}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.data)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print("TRANSFER_SUMMARY", json.dumps({k: v for k, v in result.items() if k not in ("detail", "query_ids")}), flush=True)


if __name__ == "__main__":
    main()
