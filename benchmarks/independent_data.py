#!/usr/bin/env python3
"""Fetch only pinned public BEIR files, never user data; benchmark-only."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

CQA = "https://huggingface.co/datasets/BeIR/cqadupstack/resolve/e84b7220ce5a4e6c49aeb568983b0ec5a7584c2c/"
CQ = "https://huggingface.co/datasets/BeIR/cqadupstack-qrels/resolve/2b9f5791698b5be7bc5e10535c8690f20043c3db/"
SCI = "https://huggingface.co/datasets/BeIR/scifact/resolve/b3b5335604bf5ee3c4447671af975ea25143d4f5/"
SQ = "https://huggingface.co/datasets/BeIR/scifact-qrels/resolve/2938d17dc3b09882fdb8c12bbbe2e2dc0e75a029/"
DATASETS = {
    "programmers": (CQA + "programmers/", CQ + "programmers/", 32176, 876),
    "stats": (CQA + "stats/", CQ + "stats/", 42269, 652),
    "scifact": (SCI, SQ, 5183, 300),
}
LIMITS = {"corpus.parquet": 64 * 1024 * 1024, "queries.parquet": 4 * 1024 * 1024, "test.tsv": 1024 * 1024}
PINNED = {"programmers": {"corpus.parquet": "b8eefa212252fe5af6ee72ba530df053740ff30c2c0bea77089f8a9271e94f75",
                          "queries.parquet": "106ba4777034ccec608a623ac93b5cfad63d89effc64d0528759ea94e276345d"}}


def fetch(dataset, output):
    base, qbase, docs, queries = DATASETS[dataset]
    output.mkdir(parents=True, exist_ok=False)
    files = {"corpus.parquet": base + "corpus/corpus-00000-of-00001.parquet",
             "queries.parquet": base + "queries/queries-00000-of-00001.parquet",
             "test.tsv": qbase + "test.tsv"}
    recorded = {}
    for name, url in files.items():
        with urllib.request.urlopen(url, timeout=90) as response:
            if not response.url.startswith("https://"):
                raise ValueError("Non-HTTPS response")
            data = response.read(LIMITS[name] + 1)
        if not data or len(data) > LIMITS[name]:
            raise ValueError("Dataset file missing or exceeds budget")
        actual = hashlib.sha256(data).hexdigest()
        expected = PINNED.get(dataset, {}).get(name)
        if expected and actual != expected:
            raise ValueError("Pinned publisher digest mismatch")
        if name.endswith(".parquet") and (data[:4] != b"PAR1" or data[-4:] != b"PAR1"):
            raise ValueError("Invalid parquet envelope")
        if name == "test.tsv" and not data.startswith(b"query-id\tcorpus-id\tscore"):
            raise ValueError("Invalid qrels header")
        (output / name).write_bytes(data)
        recorded[name] = {"url": url, "sha256": actual, "bytes": len(data)}
        print(dataset, name, len(data), actual, flush=True)
    manifest = {"dataset": dataset, "license": "CC-BY-SA-4.0", "source": "BEIR",
                "expected_documents": docs, "expected_test_queries": queries, "files": recorded}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fetch(args.dataset, args.output)


if __name__ == "__main__":
    main()
