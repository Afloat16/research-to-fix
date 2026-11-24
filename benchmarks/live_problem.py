#!/usr/bin/env python3
"""Explicit live public metadata discovery on three fixed diagnostic problems.

The small, development-selected qrels list known source identities. Unjudged
results may be useful. Never send qrels or repository/paper IDs as queries.
Do not infer repair quality or comprehensive literature recall from this test.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/research-to-fix/scripts"))
import research_workflow as w
import public_discovery as d

TASK_IDS = ("attention", "adaptation", "neighbors")
DATASET = ROOT / "benchmarks/datasets/algorithm_discovery_v1.json"


def identity_keys(row):
    keys = {"url:" + w.canonical_url(row["url"])}
    doi = w.normalized_doi(row.get("doi"))
    aid = w.normalized_arxiv(row.get("arxiv_id"))
    if doi:
        keys.add("doi:" + doi)
    if aid:
        keys.add("arxiv:" + aid)
    return keys


def evaluate(task, documents, transport=d.request_metadata):
    relevant = set(task["relevant"])
    labels = {key: set() for key in relevant}
    for row in documents:
        if row["id"] in labels:
            labels[row["id"]].update(identity_keys(row))
    plan = w.make_plan(task["problem"], 20, strategy="comprehensive")
    start = time.monotonic()
    response = d.discover(plan, True, max_requests=8, per_query=8, workers=3, transport=transport)
    elapsed = time.monotonic() - start
    queries = {row["id"]: row for row in plan["queries"]}
    normalized = []
    for row in response["results"]:
        try:
            normalized.append(w.normalize_result(row, queries))
        except w.WorkflowError:
            continue

    def matched(rows):
        keys = set()
        for row in rows:
            keys.update(row.get("identities") or row.get("keys") or
                        {"url:" + w.canonical_url(row["url"])})
        return sorted(key for key, aliases in labels.items() if keys & aliases)

    def metrics(hits):
        ids = set(hits)
        return {"known_hits": len(ids), "known_recall": round(len(ids) / len(relevant), 6),
                "complete_known_pairs": sum(set(pair) <= ids for pair in task["pairs"]),
                "known_pairs": len(task["pairs"]), "matched_label_ids": sorted(ids)}

    methods = {}
    for mode in ("bm25", "facet", "fusion"):
        report = w.rank_results(plan, [response], 12, mode)
        shortlist = report["shortlist"]
        linked = report["linked_followups"]
        methods[mode] = {"shortlisted": len(shortlist), "linked_followups": len(linked),
                         "shortlist": metrics(matched(shortlist)),
                         "shortlist_plus_linked": metrics(matched(shortlist + linked)),
                         "identity_conflicts": report["identity_conflict_count"]}
    by_provider = {}
    for status in response["searches"]:
        name = status["provider"]
        if name not in by_provider:
            observations = [row for row in normalized if row["origin"] == name]
            by_provider[name] = {"statuses": [], "observations": len(observations),
                                 **metrics(matched(observations))}
        by_provider[name]["statuses"].append(status["status"])
    return {"task_id": task["id"], "plan_id": w.plan_fingerprint(plan), "elapsed_seconds": round(elapsed, 3),
            "requests": response["requests"], "known_sources": len(relevant),
            "observations": len(response["results"]), "valid_observations": len(normalized),
            "provider_statuses": response["searches"], "providers": by_provider,
            "raw_union": metrics(matched(normalized)), "methods": methods}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-public", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.approve_public:
        parser.error("explicit public approval required")
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    tasks = {row["id"]: row for row in dataset["tasks"]}
    rows = [evaluate(tasks[key], dataset["documents"]) for key in TASK_IDS]
    report = {"scope": "live discovery on three fixed public diagnostic problems",
              "qrels": "known positive source identities; unjudged results are not negative labels",
              "tasks": rows, "total_known_sources": sum(row["known_sources"] for row in rows),
              "raw_union_known_hits": sum(row["raw_union"]["known_hits"] for row in rows),
              "notice": "Live provider availability changes. No general research or agent repair success claim."}
    w.write_json(report, args.output)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
