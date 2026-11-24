#!/usr/bin/env python3
"""Explicit public benchmark: source-labeled paper-to-code lookup.

Only a fixed public dataset viewer endpoint and the approved public metadata
adapters are contacted. No repository secrets, private problems or code.
The archive is frozen by its publisher; exact responses are hashed and
retained as an artifact. Network failure is reported, never fabricated.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/research-to-fix/scripts"))
import public_discovery as discovery
import research_workflow as w
import research_case as core
from retrieval import SQLiteBaseline

DATASET = "pwc-archive/links-between-paper-and-code"
DATASET_URL = "https://huggingface.co/datasets/" + DATASET
LICENSE = "CC-BY-SA-4.0"
ARCHIVE_ENDPOINT = "https://datasets-server.huggingface.co/rows"
OFFSETS = (1000, 100000, 200000)
LENGTH = 100
K = 10
MAX_LIVE_QUERIES = 4


def archive_request(offset):
    params = {"dataset": DATASET, "config": "default", "split": "train",
              "offset": offset, "length": LENGTH}
    url = ARCHIVE_ENDPOINT + "?" + urllib.parse.urlencode(params)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), discovery.NoRedirect())
    request = urllib.request.Request(url, headers={"User-Agent": discovery.USER_AGENT,
                                                  "Accept": "application/json"})
    with opener.open(request, timeout=15) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("response_too_large")
    value, _ = core.decode_case_bytes(raw)
    if not isinstance(value, dict) or not isinstance(value.get("rows"), list):
        raise ValueError("invalid_archive_response")
    return {"offset": offset, "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": value["rows"]}


def fetch_archive():
    records, failures = [], []
    for offset in OFFSETS:
        try:
            records.append(archive_request(offset))
        except (OSError, ValueError, TypeError, discovery.ProviderError, RecursionError) as error:
            failures.append({"offset": offset, "error_type": type(error).__name__})
    return {"dataset": DATASET, "url": DATASET_URL, "license": LICENSE,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "archive_description": "Publisher's last available snapshot, 2025-07-28; dataset-viewer slice, not revision-addressed.",
            "slices": records, "failures": failures}


def fixture(archive):
    papers, repos, labels = {}, set(), defaultdict(set)
    for block in archive["slices"]:
        for record in block["rows"]:
            row = record.get("row") if isinstance(record, dict) else None
            if not isinstance(row, dict):
                continue
            url = discovery.github_repo_url(row.get("repo_url"))
            aid = w.normalized_arxiv(row.get("paper_arxiv_id"))
            title = row.get("paper_title")
            if not url:
                continue
            repos.add(url)
            if (row.get("is_official") is not True or not aid or not isinstance(title, str)
                    or not 15 <= len(title) <= 250):
                continue
            try:
                title = w.public_text(title, 250)
            except w.WorkflowError:
                continue
            # Only the dataset's official flag is a qrel; no inferred links.
            papers.setdefault(aid, title)
            labels[aid].add(url)
    ids = sorted(papers, key=lambda key: hashlib.sha256(("r2f-pwc-archive-v1:" + key).encode()).digest())
    return [{"id": key, "title": papers[key], "relevant": sorted(labels[key])} for key in ids], sorted(repos)


def metric(ranked, relevant):
    relevant = set(relevant)
    ranked = ranked[:K]
    hits = set(ranked) & relevant
    return {"recall": len(hits) / len(relevant),
            "mrr": next((1 / (index + 1) for index, key in enumerate(ranked) if key in relevant), 0),
            "hit": float(bool(hits))}


def summary(values):
    return {key: round(statistics.mean(row[key] for row in values), 6) for key in values[0]} if values else None


def slug_benchmark(queries, repos):
    # A hard, deliberately metadata-only diagnostic. Do not insert known
    # paper titles or gold edges into the repository descriptions.
    corpus = [{"id": url, "title": url.removeprefix("https://github.com/"), "text": ""} for url in repos]
    methods = {}
    for mode in ("bm25", "technical", "stemmed", "hybrid"):
        index = core.PostingIndex([(row["id"], core.ranking_counts(row["title"], row["title"], mode))
                                  for row in corpus])
        methods[mode] = summary([metric([key for _, key, _ in index.rank(
            core.ranking_tokens(row["title"], mode), K, False)], row["relevant"]) for row in queries])
    try:
        sqlite = SQLiteBaseline(corpus, porter=True)
    except Exception as error:
        methods["sqlite_porter"] = {"unavailable": type(error).__name__}
    else:
        methods["sqlite_porter"] = summary([metric(sqlite.search(row["title"], K), row["relevant"]) for row in queries])
        sqlite.db.close()
    return methods


def live_lookup(queries):
    rows = []
    # Fixed hash-selected queries, no repo labels or answers in outgoing text.
    for item in queries[:MAX_LIVE_QUERIES]:
        title = item["title"]
        # Full title stays in the public fingerprint. Task and query seed
        # are bounded; avoid repeating the title in the native query.
        short_title = title if len(title) <= 120 else title[:120].rsplit(" ", 1)[0]
        problem = {"symptom": "find original public implementation for " + title,
                   "task": short_title, "focus": "algorithm"}
        try:
            plan = w.make_plan(problem, 2, ["github_repositories", "paperswithcode"], "comprehensive")
        except w.WorkflowError:
            rows.append({"paper_id": item["id"], "status": "invalid_public_fingerprint"})
            continue
        found = discovery.discover(plan, True, max_requests=2, per_query=5, workers=2)
        triage = w.rank_results(plan, [found], limit=K)
        per_provider = {}
        for source in ("github_repositories", "paperswithcode"):
            statuses = [row["status"] for row in found["searches"] if row["provider"] == source]
            codes = list(dict.fromkeys(w.canonical_url(row["url"]) for row in found["results"]
                                      if row["origin"] == source and row["kind"] == "repository"))
            per_provider[source] = {"status": statuses, "returned_codes": len(codes),
                                    "metrics": metric(codes, item["relevant"])
                                    if "completed" in statuses or "partial" in statuses else None}
        shortlist_codes = [row["url"] for row in triage["shortlist"] if row["family"] == "code"]
        rows.append({"paper_id": item["id"], "providers": per_provider,
                     "all_provider_statuses": found["searches"], "gold_repositories": item["relevant"],
                     "shortlist_codes": shortlist_codes,
                     "union_metrics": metric(shortlist_codes, item["relevant"])
                     if any(v["metrics"] is not None for v in per_provider.values()) else None})
    return rows


def exact_lookup(queries, archive_fallback=False):
    # This is a different information condition from title-only search:
    # the paper identifier is known. Never pool the results as if equally hard.
    rows = []
    plan = w.make_plan({"symptom": "find published paper implementation",
                        "task": "paper code lookup", "focus": "algorithm"},
                       1, ["paperswithcode"], "comprehensive")
    selected = queries[:MAX_LIVE_QUERIES]
    if not selected:
        return []
    result = discovery.resolve_papers(plan, [row["id"] for row in selected],
                                      plan["queries"][0]["id"], True, archive_fallback=archive_fallback, max_requests=8)
    by_id = defaultdict(set)
    for row in result["results"]:
        if row["kind"] != "repository":
            continue
        for link in row.get("links", []):
            match = w.canonical_url(link["url"])
            if match.startswith("https://arxiv.org/abs/"):
                by_id[match.split("/abs/", 1)[1]].add(w.canonical_url(row["url"]))
    labels = {row["id"]: row["relevant"] for row in selected}
    for key in labels:
        attempts = [row for row in result["lookups"] if row["arxiv_id"] == key]
        found = sorted(by_id[key])
        success = any(row["status"] in ("completed", "partial") for row in attempts)
        rows.append({"paper_id": key, "status": "completed" if success else "unavailable",
                     "returned_codes": len(found), "attempts": attempts,
                     "metrics": metric(found, labels[key]) if success else None,
                     "gold_repositories": labels[key], "returned_repositories": found,
                     "elapsed_ms": sum(row.get("elapsed_ms", 0) for row in attempts)})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-public", action="store_true", help="Approve fixed public archive and lookup requests")
    parser.add_argument("--input", type=Path, help="Replay a previously saved archive JSON; no network")
    parser.add_argument("--live", action="store_true", help="Also evaluate up to four public title queries via fixed APIs")
    parser.add_argument("--exact", action="store_true", help="Also evaluate up to four known arXiv IDs (different information condition)")
    parser.add_argument("--archive-fallback", action="store_true", help="Evaluate exact-ID catalog plus historical archive fallback")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (not args.input or args.live or args.exact or args.archive_fallback) and not args.approve_public:
        parser.error("explicit public approval required")
    args.output.mkdir(parents=True, exist_ok=False)
    archive = w.read_json(args.input) if args.input else fetch_archive()
    w.write_json(archive, args.output / "archive.json")
    queries, repos = fixture(archive)
    result = {"dataset": DATASET, "dataset_url": DATASET_URL, "license": LICENSE,
              "offsets": list(OFFSETS), "slice_failures": archive.get("failures", []),
              "queries": len(queries), "repository_candidates": len(repos), "k": K,
              "status": "completed" if queries and repos and not archive.get("failures") else
                        "partial" if queries and repos else "unavailable",
              "scope": "Archive-labeled title-to-slug lookup, not semantic source applicability or repair success. "
                       "Official flags are archive labels, not independently verified code quality. "
                       "Live catalog may share this archive; the online evaluation is not independent of that provider.",
              "offline_slug_methods": slug_benchmark(queries, repos) if queries and repos else None,
              "live": live_lookup(queries) if args.live and queries else [],
              "known_id_lookup": exact_lookup(queries, args.archive_fallback) if args.exact and queries else [],
              "known_id_archive_fallback": args.archive_fallback,
              "sample_selection": "fixed row offsets; all valid official arXiv labels; SHA-256 order for at most four live lookups"}
    w.write_json(result, args.output / "report.json")
    # The archive itself is not printed to logs.
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
