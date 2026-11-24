#!/usr/bin/env python3
"""Fetch only pinned public BEIR files, never user data; benchmark-only."""
import argparse
import hashlib
import gzip
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


# Standard-library fallback: pinned Tevatron repackaging of the same BEIR
# collections, and original BEIR qrels. Verify publisher file digests before
# decompressing; do not download or execute the dataset loader scripts.
TEV_CORPUS = "https://huggingface.co/datasets/Tevatron/beir-corpus/resolve/b593902224034c884d791b8ab357e4dc10ff98bb/"
TEV_QUERIES = "https://huggingface.co/datasets/Tevatron/beir/resolve/da4d656f2c8fbcac8810e4ea016ff3bf8b289c4e/"
TEV = {
    "programmers": ("cqadupstack-programmers",
                    "2779027fdaaa5f578d9b8fe6488937bc3a042e387e927f20dbd0135ac1edf90d",
                    "fcecbac2e3f7d86be8cc463f1bb49fa35d276f35e3a294bbec84c79c1f7a3065"),
    "stats": ("cqadupstack-stats",
              "c3ce74fe9bf8024deb09f1dd6c1812daa1674a3faf0a9a5fce219b2d21c90077",
              "4937ef43aedc8539581d663b715079d59f88f2ce7948d18de839c2d81bdb0204"),
    "scifact": ("scifact",
                "8dd268826be9694e5e369bcc426551e1ae8cc6651a8fa69186475e20effae841",
                "6066e4eae863e603cca3379f2da04812b092c2b689b321c80a0491c02a37647d"),
}


def download_bytes(url, limit, expected=None):
    with urllib.request.urlopen(url, timeout=90) as response:
        if not response.url.startswith("https://"):
            raise ValueError("Non-HTTPS response")
        data = response.read(limit + 1)
    if not data or len(data) > limit:
        raise ValueError("Dataset file missing or exceeds budget")
    digest = hashlib.sha256(data).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError("Pinned publisher digest mismatch")
    return data, {"url": url, "sha256": digest, "bytes": len(data)}


def fetch_jsonl(dataset, output):
    _, qbase, docs, queries = DATASETS[dataset]
    stem, corpus_sha, query_sha = TEV[dataset]
    output.mkdir(parents=True, exist_ok=False)
    corpus, cm = download_bytes(TEV_CORPUS + stem + ".jsonl.gz", 64 * 1024 * 1024, corpus_sha)
    query, qm = download_bytes(TEV_QUERIES + stem + ".jsonl", 4 * 1024 * 1024, query_sha)
    qrel, rm = download_bytes(qbase + "test.tsv", 1024 * 1024)
    if not qrel.startswith(b"query-id\tcorpus-id\tscore"):
        raise ValueError("Invalid qrels header")
    # Gzip is bounded on decompression as well as the wire.
    import io
    with gzip.GzipFile(fileobj=io.BytesIO(corpus)) as handle:
        raw = handle.read(256 * 1024 * 1024 + 1)
    if len(raw) > 256 * 1024 * 1024:
        raise ValueError("Decompressed corpus exceeds budget")
    files = {}
    for name, data, id_key, text_key in (("corpus.jsonl", raw, "docid", "text"),
                                          ("queries.jsonl", query, "query_id", "query")):
        target = output / name
        count = 0
        with target.open("x", encoding="utf-8", newline="\n") as out:
            for line in data.splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                row = {"_id": str(item[id_key]), "title": item.get("title") or "", "text": item[text_key]}
                if not isinstance(row["title"], str) or not isinstance(row["text"], str):
                    raise ValueError("Unexpected dataset fields")
                out.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
                count += 1
        if name == "corpus.jsonl" and count != docs:
            raise ValueError("Unexpected complete corpus count")
        files[name] = {"sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "rows": count}
        print(dataset, name, count, files[name]["sha256"], flush=True)
    (output / "qrels").mkdir()
    (output / "qrels" / "test.tsv").write_bytes(qrel)
    files["test.tsv"] = rm
    manifest = {"dataset": dataset, "license": "CC-BY-SA-4.0", "source": "BEIR via Tevatron repackaging; official BEIR qrels",
                "expected_documents": docs, "expected_test_queries": queries, "files": files,
                "original_downloads": {"corpus.jsonl.gz": cm, "queries.jsonl": qm, "test.tsv": rm}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("jsonl", "parquet"), default="jsonl")
    args = parser.parse_args()
    (fetch_jsonl if args.format == "jsonl" else fetch)(args.dataset, args.output)


if __name__ == "__main__":
    main()
