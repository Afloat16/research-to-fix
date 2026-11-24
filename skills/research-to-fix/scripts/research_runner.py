#!/usr/bin/env python3
"""One reviewed research round, optionally federated, with explicit output files.

This is not an autonomous crawler. No network by default; no source execution.
The output bundle is a set of local observations, not a proof of truth.
"""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

import paper_catalog as catalog
import public_discovery as d
import research_case as core
import research_session as session
import research_workflow as w

MAX_INPUTS = 8
MAX_CATALOG_QUERIES = 3


def run_round(plan, output, inputs=None, database=None, approve_public=False,
              query_ids=None, requests=8, per_query=8, workers=3, limit=12,
              ranking="bm25", transport=d.request_metadata):
    plan = w.validate_plan(plan)
    binding = w.plan_fingerprint(plan)
    queries = {q["id"]: q for q in plan["queries"]}
    if query_ids is not None:
        if not isinstance(query_ids, list) or not query_ids or len(query_ids) != len(set(query_ids)):
            w.fail("invalid_query_selection")
        if not all(qid in queries for qid in query_ids):
            w.fail("unknown_query")
    selected = [queries[qid] for qid in (query_ids if query_ids is not None else list(queries))]
    w.integer(requests, 1, d.MAX_REQUESTS)
    w.integer(per_query, 1, d.MAX_PER_QUERY)
    w.integer(workers, 1, d.MAX_WORKERS)
    w.integer(limit, 1, w.MAX_SHORTLIST)
    if ranking not in ("bm25", "facet", "fusion"):
        w.fail("invalid_ranking")
    if type(approve_public) is not bool:
        w.fail("invalid_approval")
    inputs = [] if inputs is None else inputs
    if not isinstance(inputs, list) or len(inputs) > MAX_INPUTS:
        w.fail("invalid_round_inputs")
    # Preflight every supplied payload before any network call. Preserve
    # exact reviewed plan binding, including status records.
    for item in inputs:
        if not isinstance(item, dict) or item.get("plan_id") != binding:
            w.fail("results_plan_mismatch")
    if inputs:
        session.aggregate([{"plan": plan, "inputs": inputs}], limit, ranking)
    if not inputs and database is None and not approve_public:
        w.fail("no_enabled_research_source")
    catalog_queries = [q for q in selected if q["provider"] == "paperswithcode"][:MAX_CATALOG_QUERIES]
    if database is not None and not catalog_queries:
        w.fail("catalog_query_required")
    # One explicitly named new directory; no implicit scanning or overwrite.
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    w.write_json(plan, output / "plan.json")
    payloads = list(inputs)
    files = []
    for i, payload in enumerate(inputs, 1):
        name = f"host-{i:02d}.json"
        w.write_json(payload, output / name)
        files.append(name)
    if database is not None:
        with catalog.Catalog(database) as db:
            for i, query in enumerate(catalog_queries, 1):
                result = db.observations(plan, query["id"], limit=min(limit, catalog.MAX_PAPERS))
                name = f"catalog-{i:02d}.json"
                w.write_json(result, output / name)
                files.append(name)
                payloads.append(result)
    # Check combined local evidence limits before making an approved request.
    if payloads:
        session.aggregate([{"plan": plan, "inputs": payloads}], limit, ranking)
    if approve_public:
        result = d.discover(plan, True, max_requests=requests, per_query=per_query,
                            query_ids=query_ids, workers=workers, transport=transport)
        w.write_json(result, output / "api.json")
        files.append("api.json")
        payloads.append(result)
    report = session.aggregate([{"plan": plan, "inputs": payloads}], limit, ranking)
    w.write_json(report["triage"], output / "shortlist.json")
    w.write_json(report["next_plan"], output / "next-plan.json")
    w.write_json(report, output / "session.json")
    summary = {"schema_version": 1, "scope": "research_round_bundle", "plan_id": binding,
               "session_id": report["session_id"], "result_files": files,
               "network_enabled": approve_public,
               "unique_identities": report["triage"]["unique_identities"],
               "shortlisted": len(report["triage"]["shortlist"]),
               "family_gaps": report["triage"]["family_gaps"],
               "next_query_ids": report["next_query_ids"],
               "suggested_action": report["suggested_action"],
               "review_required": True,
               "notice": "Review originals before use. No automatic next round, code execution, or repair."}
    w.write_json(summary, output / "summary.json")
    return summary


def main(argv=None):
    parser = core.SafeArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input", type=Path, action="append", default=[])
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--approve-public", action="store_true")
    parser.add_argument("--query-id", action="append")
    parser.add_argument("--max-requests", type=int, default=8)
    parser.add_argument("--per-query", type=int, default=8)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--ranking", choices=("bm25", "facet", "fusion"), default="bm25")
    args = parser.parse_args(argv)
    try:
        if len(args.input) > MAX_INPUTS:
            w.fail("invalid_round_inputs")
        report = run_round(w.read_json(args.plan), args.output,
                           [w.read_json(path) for path in args.input], args.catalog,
                           args.approve_public, args.query_id, args.max_requests,
                           args.per_query, args.workers, args.limit, args.ranking)
        w.write_json(report, None)
        return 0
    except (w.WorkflowError, OSError, ValueError, TypeError, RecursionError, sqlite3.Error) as error:
        code = str(error) if isinstance(error, w.WorkflowError) else "round_input_or_file_operation"
        print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
