#!/usr/bin/env python3
"""Reproducible retrieval comparisons; never run source documents as commands."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import sqlite3
import statistics
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "research-to-fix" / "scripts"))
import research_case as rc

DATASET = Path(__file__).with_name("datasets") / "retrieval_v1.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_dataset(corpus, queries):
    ids = {row["id"] for row in corpus}
    qids = {row["id"] for row in queries}
    if not corpus or not queries or len(ids) != len(corpus) or len(qids) != len(queries):
        raise ValueError("Empty dataset or duplicate IDs")
    for row in queries:
        if not set(row["relevant"]).issubset(ids) or len(set(row["relevant"])) != len(row["relevant"]):
            raise ValueError("Invalid relevance judgments")
    return corpus, queries


def load_synthetic():
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    corpus, queries = validate_dataset(dataset["corpus"], dataset["queries"])
    return corpus, queries, {"name": dataset["name"], "kind": dataset["kind"],
                             "sha256": digest(DATASET), "license": dataset["license"]}


def load_beir(directory, query_limit):
    """Consume local BEIR JSONL/TSV, or pinned HF parquet/TSV (optional pyarrow)."""
    directory = Path(directory)
    corpus_file = directory / "corpus.jsonl"
    query_file = directory / "queries.jsonl"
    if corpus_file.is_file() and query_file.is_file():
        def read(path):
            with path.open(encoding="utf-8") as handle:
                return [json.loads(line) for line in handle if line.strip()]
        qrel_file = directory / "qrels" / "test.tsv"
    else:
        import pyarrow.parquet as pq
        corpus_file, query_file = directory / "corpus.parquet", directory / "queries.parquet"
        qrel_file = directory / "test.tsv"
        def read(path):
            return pq.read_table(path).to_pylist()
    corpus = [{"id": str(row["_id"]), "title": row.get("title") or "", "text": row.get("text") or ""}
              for row in read(corpus_file)]
    judgments = defaultdict(set)
    with qrel_file.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if int(row["score"]) > 0:
                judgments[row["query-id"]].add(row["corpus-id"])
    queries = [{"id": str(row["_id"]), "text": " ".join(filter(None, (row.get("title"), row.get("text")))),
                "relevant": sorted(judgments[str(row["_id"])])} for row in read(query_file)
               if str(row["_id"]) in judgments]
    if set(judgments) != {row["id"] for row in queries}:
        raise ValueError("Qrels contain unknown queries")
    validate_dataset(corpus, queries)
    # Stable, preregistered ordering independent of labels/algorithm outputs.
    queries.sort(key=lambda row: hashlib.sha256(("r2f-eval-v1:" + row["id"]).encode()).digest())
    total_queries = len(queries)
    if query_limit:
        queries = queries[:query_limit]
    return corpus, queries, {"name": "local-beir", "kind": "external_duplicate_question_retrieval",
                             "files_sha256": {p.name: digest(p) for p in (corpus_file, query_file, qrel_file)},
                             "available_queries": total_queries, "selection": "sha256(r2f-eval-v1:query-id)"}


def legacy_scan(documents, terms):
    """Pre-upgrade scorer: original formula and full scan per query."""
    lengths = [sum(doc.values()) for _, doc in documents]
    mean = sum(lengths) / len(lengths) if lengths else 1.0
    frequencies = Counter(term for _, doc in documents for term in terms.intersection(doc))
    ranked = []
    for (identifier, doc), length in zip(documents, lengths):
        normalization = 1.5 * (0.25 + 0.75 * length / (mean or 1.0))
        contributions = {term: math.log1p((len(documents) - frequencies[term] + 0.5)
                                        / (frequencies[term] + 0.5)) * (2.5 * doc[term])
                         / (doc[term] + normalization) for term in sorted(terms.intersection(doc))}
        score = sum(contributions.values())
        if score > 0:
            ranked.append((score, identifier))
    return sorted(ranked, key=lambda pair: (-pair[0], pair[1]))


def text_fields(row):
    # Same field budget as production recall; do not select documents by qrels.
    title = rc._recall_excerpt(row["title"], 1000)
    body = rc._recall_excerpt(row["text"], 9000)
    return title, (title + "\n" + body)[:10000]


class SQLiteBaseline:
    def __init__(self, corpus):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE VIRTUAL TABLE docs USING fts5(id UNINDEXED, title, body, tokenize='unicode61')")
        self.db.executemany("INSERT INTO docs VALUES(?,?,?)",
                            ((row["id"], text_fields(row)[0], rc._recall_excerpt(row["text"], 9000)) for row in corpus))
        self.db.commit()

    def search(self, text, k):
        tokens = sorted(set(re.findall(r"[^\W_]+", text.casefold())) - rc.RECALL_STOPWORDS)
        if not tokens:
            return []
        expression = " OR ".join('"' + token.replace('"', '""') + '"' for token in tokens)
        return [row[0] for row in self.db.execute(
            "SELECT id FROM docs WHERE docs MATCH ? ORDER BY bm25(docs,0.0,2.0,1.0), id LIMIT ?",
            (expression, k))]


def metrics(ranked, relevant, k):
    relevant = set(relevant)
    ranked = ranked[:k]
    if len(ranked) != len(set(ranked)):
        raise ValueError("Duplicate result")
    if not relevant:
        return {"abstained": not ranked}
    hits = [int(identifier in relevant) for identifier in ranked]
    dcg = sum(hit / math.log2(index + 2) for index, hit in enumerate(hits))
    ideal = sum(1 / math.log2(index + 2) for index in range(min(k, len(relevant))))
    return {"mrr": next((1 / (index + 1) for index, hit in enumerate(hits) if hit), 0.0),
            "recall": sum(hits) / len(relevant), "ndcg": dcg / ideal,
            "hit": float(any(hits))}


def summarize(rankings, queries, k):
    positive = [metrics(rankings[row["id"]], row["relevant"], k) for row in queries if row["relevant"]]
    negative = [metrics(rankings[row["id"]], [], k) for row in queries if not row["relevant"]]
    return {**({f"{key}@{k}": round(statistics.mean(row[key] for row in positive), 6)
                for key in ("mrr", "recall", "ndcg", "hit")} if positive else {}),
            "negative_queries": len(negative),
            "negative_abstention": round(statistics.mean(row["abstained"] for row in negative), 6) if negative else None}


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def run(corpus, queries, metadata, k=10, repeats=3, include_scan=True):
    methods = {}
    outputs = {}
    for name in ("legacy_scan", "indexed_bm25", "technical", "sqlite_fts5"):
        if name == "legacy_scan" and not include_scan:
            continue
        start = perf_counter_ns()
        # BEIR excludes self-matches when a query ID is also a document ID.
        # Request one extra result for every engine, then remove the self-hit.
        depth = k + 1
        if name in ("legacy_scan", "indexed_bm25"):
            docs = [(row["id"], Counter(rc.recall_tokens(text_fields(row)[1]))) for row in corpus]
            if name == "legacy_scan":
                def search(text):
                    return [identifier for _, identifier in legacy_scan(docs, set(rc.recall_tokens(text)))[:depth]]
            else:
                index = rc.PostingIndex(docs)
                del docs
                def search(text):
                    return [identifier for _, identifier, _ in index.rank(rc.recall_tokens(text), depth, False)]
        elif name == "technical":
            docs = [(row["id"], rc.technical_counts(*text_fields(row))) for row in corpus]
            index = rc.PostingIndex(docs)
            del docs
            def search(text):
                return [identifier for _, identifier, _ in index.rank(rc.technical_tokens(text), depth, False)]
        else:
            try:
                sqlite = SQLiteBaseline(corpus)
            except sqlite3.OperationalError as error:
                if "no such module" in str(error).lower():
                    methods[name] = {"status": "unavailable", "reason": "SQLite FTS5 not compiled"}
                    continue
                raise
            def search(text):
                return sqlite.search(text, depth)
        build_ms = (perf_counter_ns() - start) / 1e6
        times = []
        expected = None
        for _ in range(repeats):
            rankings = {}
            for row in queries:
                start = perf_counter_ns()
                rankings[row["id"]] = [identifier for identifier in search(row["text"])
                                       if identifier != row["id"]][:k]
                times.append((perf_counter_ns() - start) / 1e6)
            if expected is not None and rankings != expected:
                raise RuntimeError("Nondeterministic rankings")
            expected = rankings
        outputs[name] = expected
        methods[name] = {"status": "completed", "build_ms": round(build_ms, 3),
                         "query_p50_ms": round(statistics.median(times), 6),
                         "query_p95_ms": round(percentile(times, .95), 6),
                         "query_total_ms_per_repeat": round(sum(times) / repeats, 3),
                         **summarize(expected, queries, k)}
        # Release each engine before building the next one.
        del search
        if name in ("technical", "indexed_bm25"):
            del index
        elif name == "legacy_scan":
            del docs
        else:
            sqlite.db.close()
    parity = (outputs.get("legacy_scan") == outputs.get("indexed_bm25")
              if include_scan else None)
    if include_scan and not parity:
        raise RuntimeError("Indexed BM25 changed legacy top-k results")
    return {"dataset": metadata, "documents": len(corpus), "queries": len(queries),
            "k": k, "repeats": repeats, "python": platform.python_version(),
            "platform": platform.platform(), "sqlite_version": sqlite3.sqlite_version,
            "legacy_indexed_top_k_exact_match": parity, "methods": methods,
            "scope": "ranking only, exclude self-ID, no relative-threshold filtering; timing includes query tokenization, excludes case validation and disk I/O",
            "notice": "Synthetic examples and duplicate-question judgments do not establish repair success or universal ranking superiority."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beir-dir", type=Path, help="Local BEIR directory; default is bundled synthetic data")
    parser.add_argument("--query-limit", type=int, default=0, help="Stable hash sample for BEIR; 0 uses all")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--no-scan", action="store_true", help="Skip costly legacy scan (no parity claim)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.k <= 100 or not 1 <= args.repeats <= 10 or args.query_limit < 0:
        parser.error("invalid benchmark limits")
    corpus, queries, meta = (load_beir(args.beir_dir, args.query_limit)
                             if args.beir_dir else load_synthetic())
    report = run(corpus, queries, meta, args.k, args.repeats, not args.no_scan)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
