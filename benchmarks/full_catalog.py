#!/usr/bin/env python3
"""Import the pinned public PWC archive; benchmark a full local catalog.

The archive remains external (CC-BY-SA-4.0), not part of the MIT code.
PyArrow is an optional importer dependency, not a skill dependency.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/research-to-fix/scripts"))
import paper_catalog as catalog
import research_workflow as w

DATASET = "pwc-archive/links-between-paper-and-code"
REVISION = "56cc5c1938678c33dedebf5f74fc4e62e2c35381"
SHA256 = "c845ff642112a345f6271bf954d007c6698088d7de525f3f8d5f7d975f142c76"
URL = ("https://huggingface.co/datasets/" + DATASET + "/resolve/" + REVISION
       + "/data/train-00000-of-00001.parquet")
MAX_DOWNLOAD = 50_000_000
SAMPLE = 256
K = 10


class FixedPublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        host = target.hostname or ""
        if (target.scheme != "https" or target.username or target.password
                or target.port not in (None, 443)
                or not (host == "huggingface.co" or host.endswith(".huggingface.co")
                        or host.endswith(".hf.co"))):
            raise ValueError("unapproved_download_redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verify_archive(path):
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            if size > MAX_DOWNLOAD:
                raise ValueError("archive_size_limit")
            digest.update(chunk)
    if digest.hexdigest() != SHA256:
        raise ValueError("archive_sha256_mismatch")
    return size


def download(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), FixedPublicRedirect())
    request = urllib.request.Request(URL, headers={"User-Agent": "research-to-fix-public-benchmark/1.0"})
    start = time.monotonic()
    size = 0
    with opener.open(request, timeout=30) as response, open(path, "xb") as out:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            size += len(chunk)
            if size > MAX_DOWNLOAD or time.monotonic() - start > 180:
                raise ValueError("archive_download_limit")
            out.write(chunk)
    return verify_archive(path)


def convert(parquet, output):
    import pyarrow.parquet as pq
    source = pq.ParquetFile(parquet)
    wanted = ["repo_url", "paper_arxiv_id", "paper_url_abs", "paper_title",
              "paper_abstract", "abstract", "is_official", "mentioned_in_paper",
              "mentioned_in_github"]
    columns = [name for name in wanted if name in source.schema_arrow.names]
    if not {"repo_url", "paper_title", "paper_arxiv_id"} <= set(columns):
        raise ValueError("archive_schema_changed")
    rows = 0
    with open(output, "x", encoding="utf-8", newline="\n") as out:
        for batch in source.iter_batches(batch_size=4096, columns=columns):
            for row in batch.to_pylist():
                # Keep only explicitly selected metadata fields.
                out.write(json.dumps(row, ensure_ascii=True, allow_nan=False) + "\n")
                rows += 1
    return rows


def percentiles(values):
    ordered = sorted(values)
    return {"p50_ms": round(statistics.median(ordered), 6),
            "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * .95))], 6)}


def benchmark(path):
    with catalog.Catalog(path) as db:
        # Exact-title/ID self-lookup measures index integrity/latency only.
        # It is not a held-out relevance or generalization test.
        rows = [dict(row) for row in db.db.execute(
            "SELECT id,title FROM papers WHERE id LIKE 'arxiv:%' ORDER BY id")]
        chosen = sorted(rows, key=lambda row: hashlib.sha256(
            ("r2f-full-index-v1:" + row["id"]).encode()).digest())[:SAMPLE]
        if not chosen:
            raise ValueError("empty_arxiv_index")
        index_times, scan_times, fts_times, title_times, reverse_times = [], [], [], [], []
        hits = link_hits = title_hits = reverse_hits = 0
        for item in chosen:
            start = time.perf_counter_ns()
            exact = db.lookup(item["id"].removeprefix("arxiv:"))
            index_times.append((time.perf_counter_ns() - start) / 1e6)
            start = time.perf_counter_ns()
            linear = next((row for row in rows if row["id"] == item["id"]), None)
            scan_times.append((time.perf_counter_ns() - start) / 1e6)
            if not exact or not linear or exact["id"] != linear["id"]:
                raise ValueError("exact_lookup_parity_failed")
            links = db.links(exact["id"])
            if not links:
                raise ValueError("missing_link")
            link_hits += 1
            start = time.perf_counter_ns()
            reverse = db.papers_for_repository(links[0]["repo_url"], 20)
            reverse_times.append((time.perf_counter_ns() - start) / 1e6)
            reverse_hits += any(row["id"] == item["id"] for row in reverse)
            try:
                start = time.perf_counter_ns()
                exact_title = db.lookup_title(item["title"], K)
                title_times.append((time.perf_counter_ns() - start) / 1e6)
                title_hits += any(row["id"] == item["id"] for row in exact_title)
            except w.WorkflowError:
                pass
            try:
                start = time.perf_counter_ns()
                results = db.search(item["title"], K)
                fts_times.append((time.perf_counter_ns() - start) / 1e6)
                hits += any(row["id"] == item["id"] for row in results)
            except w.WorkflowError:
                # Input safety restrictions are counted as misses.
                pass
        return {"sample": len(chosen), "arxiv_papers": len(rows),
                "exact_id_and_link_hits": link_hits, "exact_id_parity": True,
                "indexed_id": percentiles(index_times),
                "python_linear_scan": percentiles(scan_times),
                "exact_title_hit_at_10": round(hits / len(chosen), 6),
                "title_queries_timed": len(fts_times),
                "indexed_exact_title_hit_at_10": round(title_hits / len(chosen), 6),
                "indexed_exact_title": percentiles(title_times) if title_times else None,
                "reverse_repository_hit_at_20": round(reverse_hits / len(chosen), 6),
                "reverse_repository": percentiles(reverse_times),
                "fts_title": percentiles(fts_times) if fts_times else None,
                "scope": "Known-item self-lookup on the complete imported archive, not held-out source relevance or repair success."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-public", action="store_true")
    parser.add_argument("--parquet", type=Path, help="Local copy of the exact pinned archive")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.parquet and not args.approve_public:
        parser.error("explicit public approval required for download")
    args.output.mkdir(parents=True, exist_ok=False)
    parquet = args.parquet or args.output / "archive.parquet"
    size = verify_archive(parquet) if args.parquet else download(parquet)
    metadata = args.output / "metadata.jsonl"
    count = convert(parquet, metadata)
    if count != 300161:
        raise ValueError("unexpected_archive_row_count")
    database = args.output / "catalog.sqlite"
    build = catalog.build_catalog(metadata, database, DATASET, "CC-BY-SA-4.0", "2025-07-28")
    report = {"status": "completed", "dataset": DATASET, "dataset_url": URL,
              "revision": REVISION, "archive_sha256": SHA256, "archive_bytes": size,
              "archive_rows": count, "build": build, "benchmark": benchmark(database)}
    w.write_json(report, args.output / "report.json")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
