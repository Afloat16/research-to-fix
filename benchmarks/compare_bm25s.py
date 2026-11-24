#!/usr/bin/env python3
"""Post-holdout diagnostic against actual BM25S, not a new blind evaluation.

Only explicitly installed benchmark packages are used. No third-party package
is imported by the production skill. Never tune on these scored queries.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
from time import perf_counter_ns

from independent_retrieval import build, paired_interval, partition
from retrieval import load_beir, metrics, percentile, text_fields
import research_case as rc

METHODS = ("bm25s_native", "bm25s_matched", "precision_field4",
           "v1_contextual", "sqlite_porter", "sqlite_unicode4")
K = 10


def bm25s_search(corpus, mode):
    import bm25s
    import numpy as np
    # Document order is sorted by ID so a stable score sort has the same
    # deterministic tie rule as our pure-Python implementation.
    corpus = sorted(corpus, key=lambda row: row["id"])
    ids = [row["id"] for row in corpus]

    def document_text(row):
        title, text = text_fields(row)
        return title + "\n" + text  # title duplicated, as v1 Contextual

    def tokenize(text):
        if mode == "bm25s_matched":
            return rc.ranking_tokens(text, "stemmed")
        # Use actual BM25S English analyzer; Porter-style stem normalization
        # uses the same independently implemented R2F stemmer, so this path
        # does not need the optional PyStemmer package. No label-based tuning.
        tokens = bm25s.tokenize([text], stopwords="en", return_ids=False, show_progress=False)[0]
        return [rc.english_stem(word) for word in tokens]

    retriever = bm25s.BM25(k1=1.5, b=.75, method="lucene")
    retriever.index([tokenize(document_text(row)) for row in corpus], show_progress=False)

    def search(text, k):
        tokens = sorted(set(tokenize(text)))
        if not tokens or not any(token in retriever.vocab_dict for token in tokens):
            return []
        scores = retriever.get_scores(tokens)
        # Native sparse scoring plus stable NumPy top-k. Resolve all boundary
        # ties before truncation; never return zero-score filler.
        count = min(k, len(ids))
        if not count:
            return []
        boundary = np.partition(scores, len(ids) - count)[len(ids) - count]
        candidates = np.flatnonzero((scores >= boundary) & (scores > 0))
        ordered = candidates[np.argsort(-scores[candidates], kind="stable")][:count]
        return [ids[int(i)] for i in ordered]

    return search, lambda: None


def evaluate(data):
    manifest = json.loads((data / "manifest.json").read_text(encoding="utf-8"))
    corpus, queries, meta = load_beir(data, 0)
    if manifest["dataset"] not in ("scifact", "nasa"):
        raise ValueError("Diagnostic datasets are fixed to SciFact and NASA")
    if len(corpus) != manifest["expected_documents"] or len(queries) != manifest["expected_test_queries"]:
        raise ValueError("Unexpected dataset counts")
    if meta["files_sha256"] != {name: row["sha256"] for name, row in manifest["files"].items()}:
        raise ValueError("Dataset fingerprint mismatch")
    summaries, detail = {}, {}
    for method in METHODS:
        start = perf_counter_ns()
        search, close = bm25s_search(corpus, method) if method.startswith("bm25s_") else build(corpus, method)
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
        summaries[method] = {**{key + "@10": statistics.mean(row[key] for row in scores)
                                for key in ("mrr", "ndcg", "recall", "hit")},
                             "build_ms": build_ms, "query_p50_ms": statistics.median(timings),
                             "query_p95_ms": percentile(timings, .95), "total_query_ms": sum(timings)}
        detail[method] = {"scores": scores, "rankings": rankings}
        print("DIAGNOSTIC_METHOD", manifest["dataset"], method, json.dumps(summaries[method]), flush=True)
    comparisons = {}
    for method in ("precision_field4", "v1_contextual"):
        for baseline in ("bm25s_native", "bm25s_matched"):
            comparisons[method + "_vs_" + baseline] = paired_interval(
                [row["ndcg"] for row in detail[method]["scores"]],
                [row["ndcg"] for row in detail[baseline]["scores"]])
    return {"scope": "Post-holdout diagnostic, not blind test or agent repair evaluation.",
            "dataset": manifest, "documents": len(corpus), "queries": len(queries),
            "methods": summaries, "paired_ndcg": comparisons,
            "environment": {"python": platform.python_version(), "platform": platform.platform(),
                            **{name: importlib.metadata.version(name) for name in ("bm25s", "numpy", "scipy", "tqdm")}},
            "detail": detail}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.data)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print("DIAGNOSTIC_SUMMARY", json.dumps({key: value for key, value in result.items() if key != "detail"}), flush=True)


if __name__ == "__main__":
    main()
