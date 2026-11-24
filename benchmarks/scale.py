#!/usr/bin/env python3
"""Measure repeated on-disk recall and memory/latency of compact postings."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
import tempfile
from time import perf_counter_ns
import tracemalloc

import retrieval as bench
rc = bench.rc


class TupleIndex:
    """Previous iteration's tuple-list posting representation, same BM25."""
    def __init__(self, documents):
        self.ids = tuple(identifier for identifier, _ in documents)
        counts = [terms for _, terms in documents]
        lengths = [sum(terms.values()) for terms in counts]
        mean = sum(lengths) / len(lengths)
        frequencies = Counter(term for terms in counts for term in terms)
        inverse = {term: math.log1p((len(counts) - count + .5) / (count + .5))
                   for term, count in frequencies.items()}
        self.postings = {}
        for index, (terms, length) in enumerate(zip(counts, lengths)):
            norm = 1.5 * (.25 + .75 * length / (mean or 1))
            for term, freq in terms.items():
                self.postings.setdefault(term, []).append((index, inverse[term] * 2.5 * freq / (freq + norm)))


def synthetic_case(row, variant):
    # A fabricated structurally valid test fixture, not a real solved claim.
    case = rc.new_case()
    case["case_id"] = f"synthetic-{row['id']}-{variant}"
    case["problem"].update(summary=row["title"], component="synthetic-benchmark",
                           symptoms=[row["text"]])
    case["mapping"] = [{"id": "M1", "basis": "local_code", "evidence_ids": [],
                        "local_path": "synthetic.py", "symbol": "fixture",
                        "similarities": "synthetic test", "differences": "not a real repair",
                        "hypothesis": row["text"]}]
    case["experiments"] = [{"id": "X1", "hypothesis": "synthetic fixture", "change": "generated",
                            "commands": ["fixture"], "status": "supports",
                            "mapping_ids": ["M1"], "evidence_ids": []}]
    case["validation"].update(status="solved", summary="Synthetic validation record for timing only",
                              limitations=["No actual repair or experiment claim."])
    case["validation"]["runs"] = [
        {"id": "V1", "check_id": "fixture", "phase": "before", "kind": "reproduction",
         "command": "fixture", "criteria": "synthetic", "result": "fail", "observed": "generated",
         "exit_code": 1, "evidence_ids": []},
        {"id": "V2", "check_id": "fixture", "phase": "after", "kind": "reproduction",
         "command": "fixture", "criteria": "synthetic", "result": "pass", "observed": "generated",
         "exit_code": 0, "evidence_ids": []}]
    if rc.validate_case(case):
        raise RuntimeError("Invalid fixture")
    return case


def elapsed(call):
    start = perf_counter_ns()
    result = call()
    return (perf_counter_ns() - start) / 1e6, result


def batch_bench(corpus, queries, repeats=3):
    errors = [row["text"] for row in queries[:32]]
    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        for row in corpus:
            for variant in range(3):
                case = synthetic_case(row, variant)
                (directory / (case["case_id"] + ".json")).write_text(
                    json.dumps(case, ensure_ascii=False), encoding="utf-8")
        single, batch = [], []
        for _ in range(repeats):
            duration, expected = elapsed(lambda: [rc.recall_cases(directory, error) for error in errors])
            single.append(duration)
            duration, actual = elapsed(lambda: rc.recall_batch(directory, errors)["results"])
            batch.append(duration)
            if actual != expected:
                raise RuntimeError("Batch differs from one-shot retrieval")
    single_ms, batch_ms = statistics.median(single), statistics.median(batch)
    return {"documents": len(corpus) * 3, "queries": len(errors), "repeats": repeats,
            "one_shot_total_median_ms": round(single_ms, 3), "batch_total_median_ms": round(batch_ms, 3),
            "speedup": round(single_ms / batch_ms, 3), "identical_reports": True,
            "scope": "full file reads, validation, tokenization and recall, warmed OS filesystem cache"}


def memory_bench():
    rng = random.Random(84721)
    vocab = [f"token{i}" for i in range(8192)]
    docs = [(f"doc{i:05d}", Counter(rng.choices(vocab, k=48))) for i in range(5000)]
    result = {}
    for name, builder in (("tuple_postings", TupleIndex), ("packed_postings", rc.PostingIndex)):
        # The input corpus is allocated before tracemalloc starts. Build once
        # without tracing for timing; measure a separate allocation run.
        build_ms, instance = elapsed(lambda: builder(docs))
        del instance
        tracemalloc.start()
        instance = builder(docs)
        retained, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result[name] = {"build_ms": round(build_ms, 3), "retained_bytes": retained,
                        "peak_allocated_bytes": peak}
        del instance
    ratio = result["tuple_postings"]["retained_bytes"] / result["packed_postings"]["retained_bytes"]
    index = rc.PostingIndex(docs)
    queries = [set(rng.sample(vocab, 8)) for _ in range(64)]
    scan_ms, expected = elapsed(lambda: [bench.legacy_scan(docs, terms)[:10] for terms in queries])
    index_ms, actual = elapsed(lambda: [[(score, identifier) for score, identifier, _
                                       in index.rank(terms, 10, False)] for terms in queries])
    if expected != actual:
        raise RuntimeError("Packed posting scores differ from legacy")
    return {"documents": len(docs), "terms_per_document": 48, "queries": len(queries),
            "index_memory": result, "retained_memory_reduction_factor": round(ratio, 3),
            "scan_total_ms": round(scan_ms, 3), "index_total_ms": round(index_ms, 3),
            "warm_query_speedup": round(scan_ms / index_ms, 3),
            "exact_top_10_scores": True, "scope": "generated sparse vocabulary; allocation tracing excludes input corpus"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    corpus, queries, metadata = bench.load_synthetic()
    result = {"dataset": metadata, "batch_recall": batch_bench(corpus, queries),
              "index_scale": memory_bench(), "python": sys.version.split()[0]}
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
