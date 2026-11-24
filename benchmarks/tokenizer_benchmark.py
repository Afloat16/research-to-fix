#!/usr/bin/env python3
"""Paired timing of a semantics-preserving tokenizer improvement."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
from time import perf_counter_ns
import unicodedata

from retrieval import load_beir, text_fields
import research_case as rc

def legacy_tokens(text):
    """Exact v1.0.0 tokenizer, retained for parity and timing comparison."""
    text = unicodedata.normalize("NFKC", text).casefold()
    tokens = []
    for word in re.findall(r"[^\W_]+(?:_[^\W_]+)*", text):
        for part in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+|[^\u3400-\u4dbf\u4e00-\u9fff]+", word):
            if re.fullmatch(r"[\u3400-\u4dbf\u4e00-\u9fff]+", part):
                tokens.extend(part[index:index + 2] for index in range(max(1, len(part) - 1)))
            elif part not in rc.RECALL_STOPWORDS:
                tokens.append(part)
    return tokens


def compare(texts, repeats=5):
    timings = {"v1": [], "optimized": []}
    total = 0
    for text in texts:
        old = legacy_tokens(text)
        if old != rc.recall_tokens(text):
            raise RuntimeError("Tokenizer semantic regression")
        total += len(old)
    for repeat in range(repeats):
        methods = (("v1", legacy_tokens), ("optimized", rc.recall_tokens))
        for label, tokenize in methods if repeat % 2 == 0 else methods[::-1]:
            start = perf_counter_ns()
            count = sum(len(tokenize(text)) for text in texts)
            timings[label].append((perf_counter_ns() - start) / 1e6)
            if count != total:
                raise RuntimeError("Tokenizer count regression")
    old_ms = statistics.median(timings["v1"])
    new_ms = statistics.median(timings["optimized"])
    return {"documents": len(texts), "tokens": total, "repetitions": repeats,
            "exact_token_sequence_parity": True, "v1_median_ms": old_ms,
            "optimized_median_ms": new_ms, "speedup": old_ms / new_ms,
            "scope": "Tokenization only, paired same-run timings; excludes I/O, index construction and retrieval."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    corpus, _, meta = load_beir(args.data, 0)
    corpus.sort(key=lambda row: hashlib.sha256(("r2f-tokenizer-v1:" + row["id"]).encode()).digest())
    result = compare([text_fields(row)[1] for row in corpus[:4096]])
    result["data_sha256"] = meta["files_sha256"]
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print("TOKENIZER_SUMMARY", json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
