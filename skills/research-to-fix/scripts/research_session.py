#!/usr/bin/env python3
"""Aggregate explicitly supplied research rounds, audit gaps and suggest next queries.

No network, persistent hidden state, source text execution or automatic retry.
Each payload must bind to the exact reviewed plan it was produced for.
"""
import json
from collections import Counter
from pathlib import Path
import sys

import research_case as core
import research_workflow as w

MAX_ROUNDS = 6
MAX_FILES = 24
INTENT_FIELDS = ("symptom", "task", "component", "version", "repo", "focus")
ATTEMPTED = {"completed", "partial", "access_blocked", "rate_limited",
             "unavailable", "invalid_response"}
NOTICE = ("Coverage and novelty describe supplied observations, not completeness of the literature. "
          "No query is executed. Read original sources, verify identities and compare viable local experiments.")


def query_key(query):
    return (query["source"], query["provider"], query["query"], query["native_query"])


def aggregate(rounds, limit=12, ranking="bm25"):
    if not isinstance(rounds, list) or not 1 <= len(rounds) <= MAX_ROUNDS:
        w.fail("invalid_round_count")
    w.integer(limit, 1, w.MAX_SHORTLIST)
    plans, payloads, stats = [], [], []
    queries, unique_queries = {}, {}
    observed = []
    all_requested = set()
    input_count = 0
    seen_payloads = set()
    total_observations = 0
    for idx, entry in enumerate(rounds, 1):
        entry = w.object_(entry)
        plan = w.validate_plan(entry.get("plan"))
        if plans and any(plan["problem"][field] != plans[0]["problem"][field]
                         for field in INTENT_FIELDS):
            w.fail("session_intent_changed")
        plans.append(plan)
        all_requested.update(plan["requested_sources"])
        binding = w.plan_fingerprint(plan)
        inputs = entry.get("inputs")
        if not isinstance(inputs, list) or not inputs or input_count + len(inputs) > MAX_FILES:
            w.fail("invalid_round_inputs")
        input_count += len(inputs)
        mapping = {}
        repeated = 0
        for query in plan["queries"]:
            key = query_key(query)
            if key not in unique_queries:
                global_id = f"R{idx:02d}-{query['id']}"
                unique_queries[key] = global_id
                queries[global_id] = dict(query, id=global_id)
            else:
                repeated += 1
            mapping[query["id"]] = unique_queries[key]
        round_results, round_searches, digests = [], [], []
        for payload in inputs:
            payload = w.object_(payload)
            if payload.get("plan_id") != binding:
                w.fail("results_plan_mismatch")
            fingerprint = w.plan_fingerprint({"payload": payload})
            if fingerprint in seen_payloads:
                w.fail("duplicate_round_payload")
            seen_payloads.add(fingerprint)
            digests.append(fingerprint)
            results = payload.get("results", [])
            searches = payload.get("searches", [])
            if not isinstance(results, list) or not isinstance(searches, list) or len(searches) > w.MAX_QUERIES:
                w.fail("invalid_results")
            total_observations += len(results)
            if total_observations > w.MAX_RESULTS:
                w.fail("result_limit")
            for row in results:
                row = w.object_(row)
                qid = row.get("query_id")
                if not isinstance(qid, str) or qid not in mapping:
                    w.fail("unknown_query")
                updated = dict(row, query_id=mapping[qid])
                round_results.append(updated)
                try:
                    normalized = w.normalize_result(updated, queries)
                except w.WorkflowError:
                    continue
                observed.append(dict(normalized, round=idx))
            for row in searches:
                row = w.object_(row)
                qid = row.get("query_id")
                if not isinstance(qid, str) or qid not in mapping or row.get("status") not in w.STATUSES:
                    w.fail("invalid_search_status")
                round_searches.append(dict(row, query_id=mapping[qid]))
        # Collapse repeated statuses within each round, but preserve their
        # complete set. One plan may have both API and host results.
        seen_status = {(row["query_id"], row["status"]) for row in round_searches}
        payloads.append({"results": round_results,
                         "searches": [{"query_id": key, "status": status}
                                      for key, status in sorted(seen_status)]})
        stats.append({"round": idx, "plan_id": binding, "payload_fingerprints": digests,
                      "planned_queries": len(plan["queries"]),
                      "repeated_query_definitions": repeated,
                      "attempted_unique_queries": len({key for key, status in seen_status if status in ATTEMPTED}),
                      "successful_queries": len({key for key, status in seen_status if status in {"completed", "partial"}}),
                      "observations": len(round_results),
                      "statuses": dict(sorted(Counter(status for _, status in seen_status).items())),
                      "first_seen_identities": 0})
    # Determine novelty using the same conservative identity grouping over
    # the complete supplied session, rather than comparing unstable IDs
    # or counting mirrored URLs as new independent publications.
    for group in w.group_results(observed):
        first = min(row["round"] for row in group)
        stats[first - 1]["first_seen_identities"] += 1
    combined = {"schema_version": 2, "scope": "internal_session_plan",
                "problem": plans[-1]["problem"], "queries": list(queries.values()),
                "requested_sources": [source for source in w.SOURCE_SPECS if source in all_requested],
                "omitted_sources": [source for source in w.SOURCE_SPECS if source in all_requested
                                    and source not in {q["source"] for q in queries.values()}]}
    # The internal combined plan is built only after validating every
    # constituent plan and payload binding. It is never sent to an API.
    report = w._rank_results(combined, payloads, limit, ranking)
    by_query = {row["query_id"]: row for row in report["coverage"]}
    attempted = {key for key, row in by_query.items() if set(row["status"]) & ATTEMPTED}
    successful = {key for key, row in by_query.items() if set(row["status"]) & {"completed", "partial"}}
    incomplete = [{"query_id": key, "source": queries[key]["source"], "status": row["status"]}
                  for key, row in by_query.items() if key not in successful]
    # Compute gap actions from the reviewed fingerprint, never source text.
    candidate_plan = w.make_plan(plans[-1]["problem"], w.MAX_QUERIES,
                                 combined["requested_sources"],
                                 "focused" if plans[-1]["schema_version"] == 3 else "comprehensive")
    stage_order = {"counterevidence": 0, "alternatives": 1, "implementation": 2,
                   "verification": 3, "mechanism": 4, "exact": 5}
    followup = []
    for query in candidate_plan["queries"]:
        existing = unique_queries.get(query_key(query))
        if existing in attempted:
            continue
        score = (0 if query["family"] in report["family_gaps"] else 1,
                 stage_order[query["stage"]], query["id"])
        followup.append((score, query))
    followup.sort(key=lambda pair: pair[0])
    read_families = sorted({row["family"] for row in report["shortlist"]
                            if any(source["access"] == "read" for source in row["provenance"])})
    saturated = (len(stats) >= 3 and all(row["successful_queries"] > 0
                 and row["first_seen_identities"] == 0 for row in stats[-2:]))
    if not report["shortlist"]:
        action = "reframe_or_read_missing_sources"
    elif not {"paper", "code"}.issubset(read_families):
        action = "read_and_verify_originals"
    elif saturated:
        action = "reframe_or_compare_locally"
    else:
        action = "review_alternatives_and_counterevidence"
    return {"schema_version": 1, "scope": "research_session", "notice": NOTICE,
            "session_id": w.plan_fingerprint({"rounds": [{"plan_id": row["plan_id"],
                "payload_fingerprints": row["payload_fingerprints"]} for row in stats]}),
            "rounds": stats, "unique_queries": len(queries), "attempted_queries": len(attempted),
            "successful_or_partial_queries": len(successful),
            "incomplete_queries": incomplete,
            "read_shortlist_families": read_families,
            "two_round_novelty_saturation": saturated,
            "suggested_action": action, "next_query_candidates": [row for _, row in followup[:12]],
            "next_plan": candidate_plan,
            "next_query_ids": [row["id"] for _, row in followup[:12]],
            "review_required": True, "triage": report}


def load_rounds(groups):
    if not 1 <= len(groups) <= MAX_ROUNDS:
        w.fail("invalid_round_count")
    rounds = []
    count = 0
    for group in groups:
        if len(group) < 2:
            w.fail("invalid_round_inputs")
        plan_path, *result_paths = group
        count += len(result_paths)
        if count > MAX_FILES:
            w.fail("invalid_round_inputs")
        plan = w.validate_plan(w.read_json(plan_path))
        rounds.append({"plan": plan, "inputs": [w.read_json(path) for path in result_paths]})
    return rounds


def main(argv=None):
    parser = core.SafeArgumentParser(description=__doc__)
    parser.add_argument("--round", action="append", nargs="+", metavar="PLAN_OR_RESULTS",
                        required=True, help="One plan followed by one or more result files; repeat per round")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--ranking", choices=("bm25", "facet", "fusion"), default="bm25")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        w.write_json(aggregate(load_rounds(args.round), args.limit, args.ranking), args.output)
        return 0
    except (w.WorkflowError, OSError, ValueError, TypeError, RecursionError) as error:
        code = str(error) if isinstance(error, w.WorkflowError) else "invalid_input_or_file_operation"
        print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
