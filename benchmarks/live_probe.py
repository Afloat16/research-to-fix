#!/usr/bin/env python3
"""Explicit, small known-item public API probe; never run on user records."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "research-to-fix" / "scripts"))
import public_discovery as d
import research_workflow as w

PROBLEM = {"symptom": "Exact attention memory grows with sequence length",
           "task": "FlashAttention",
           "concepts": ["FlashAttention", "memory efficient attention"], "focus": "algorithm"}
SOURCES = ["github_repositories", "arxiv", "crossref", "semantic_scholar", "openalex", "dblp"]
KNOWN = {"https://github.com/dao-ailab/flash-attention", "https://arxiv.org/abs/2205.14135",
         "https://doi.org/10.52202/068431-1189"}


def probe(approve):
    if not approve:
        w.fail("explicit_public_approval_required")
    plan = w.make_plan(PROBLEM, 12, SOURCES)
    response = d.discover(plan, True, max_requests=6, per_query=5, workers=3, schedule="balanced")
    result = w.rank_results(plan, [response], 12, "paired")
    urls = {w.canonical_url(row["url"]) for row in response["results"]}
    for row in response["results"]:
        if w.normalized_arxiv(row.get("arxiv_id")):
            urls.add("https://arxiv.org/abs/" + w.normalized_arxiv(row["arxiv_id"]))
        if w.normalized_doi(row.get("doi")):
            urls.add("https://doi.org/" + w.normalized_doi(row["doi"]))
    statuses = Counter(row["status"] for row in response["searches"])
    return {"scope": "public_known_item_probe_not_relevance_benchmark",
            "queries": len(plan["queries"]), "requests": response["requests"],
            "status_counts": dict(statuses),
            "providers": [{k: row[k] for k in ("provider", "status", "returned")} for row in response["searches"]],
            "valid_observations": result["valid_observations"], "unique_identities": result["unique_identities"],
            "known_item_matches": sorted(KNOWN & urls),
            "notice": "One public known-item query, not blind retrieval accuracy. Provider errors are recorded; "
                      "no credentials or automatic retries. Full papers and code were not read by this probe."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-public", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.approve_public:
        parser.error("explicit public approval required")
    if args.output.exists() or args.output.is_symlink():
        parser.error("output must not exist")
    report = probe(args.approve_public)
    w.write_json(report, args.output)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
