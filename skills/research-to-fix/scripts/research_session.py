#!/usr/bin/env python3
"""Bounded offline multi-round research ledger; never searches automatically."""
import argparse
import copy
import json
import sys
from pathlib import Path

import research_case as core
import research_workflow as w

MAX_ROUNDS = 4
MAX_QUERIES = 64
MAX_PAYLOADS = 12
ANCHORS = ("symptom", "task", "component", "version", "repo", "focus")
NOTICE = ("This ledger binds observations to their declared search plans and preserves history. "
          "It does not authenticate search results, perform searches, or establish repair success.")


def signature(query):
    # Include both query dialects. Case and whitespace normalization prevents
    # duplicate suggestions but is not a semantic equivalence judgment.
    return (query["source"], " ".join(query["query"].casefold().split()),
            " ".join(query["native_query"].casefold().split()))


def start(problem, query_budget=48, max_rounds=3):
    return {"schema_version": 1, "scope": "research_session", "problem": w.normalize_problem(problem),
            "query_budget": w.integer(query_budget, 1, MAX_QUERIES),
            "max_rounds": w.integer(max_rounds, 1, MAX_ROUNDS), "rounds": []}


def checked_problem(root, value):
    candidate = w.normalize_problem(value)
    if any(root[key] != candidate[key] for key in ANCHORS):
        w.fail("problem_anchor_changed_start_new_session")
    return candidate


def checked_payload(payload, plan, permitted):
    payload = w.object_(payload)
    digest = w.plan_digest(plan)
    if "plan_sha256" in payload and payload["plan_sha256"] != digest:
        w.fail("result_plan_mismatch")
    observations, searches = payload.get("results", []), payload.get("searches", [])
    if not isinstance(observations, list) or not isinstance(searches, list) or len(observations) > w.MAX_RESULTS or len(searches) > w.MAX_QUERIES:
        w.fail("invalid_results")
    queries = {row["id"]: row for row in plan["queries"]}
    for row in observations:
        row = w.object_(row)
        qid = row.get("query_id")
        if not isinstance(qid, str) or qid not in permitted:
            w.fail("result_outside_round_selection")
        # Strict session ingestion prevents silently losing malformed evidence.
        w.normalize_result(row, queries)
    for row in searches:
        row = w.object_(row)
        qid = row.get("query_id")
        if not isinstance(qid, str) or qid not in queries or row.get("status") not in w.STATUSES:
            w.fail("invalid_search_status")
        # Discovery adapter reports skipped-budget rows for unselected queries;
        # retain actual selected records only, never count unexecuted queries.
        if qid not in permitted and row["status"] != "skipped_budget":
            w.fail("status_outside_round_selection")
    return {**payload, "plan_sha256": digest,
            "searches": [row for row in searches if row["query_id"] in permitted]}


def _validate(value):
    value = w.object_(value)
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1 or value.get("scope") != "research_session":
        w.fail("invalid_session")
    root = w.normalize_problem(value.get("problem"))
    budget = w.integer(value.get("query_budget"), 1, MAX_QUERIES)
    max_rounds = w.integer(value.get("max_rounds"), 1, MAX_ROUNDS)
    rounds = value.get("rounds")
    if not isinstance(rounds, list) or len(rounds) > max_rounds:
        w.fail("round_limit")
    used, total, payload_count = set(), 0, 0
    normalized_rounds = []
    for number, round_ in enumerate(rounds, 1):
        round_ = w.object_(round_)
        plan = w.validate_plan(round_.get("plan"))
        checked_problem(root, plan["problem"])
        if round_.get("number") != number or round_.get("plan_sha256") != w.plan_digest(plan):
            w.fail("round_plan_mismatch")
        qids = round_.get("query_ids")
        if not isinstance(qids, list) or not qids or len(qids) > w.MAX_QUERIES or any(not isinstance(qid, str) for qid in qids) or len(set(qids)) != len(qids):
            w.fail("invalid_round_selection")
        by_id = {row["id"]: row for row in plan["queries"]}
        if any(qid not in by_id for qid in qids):
            w.fail("unknown_query")
        signatures = {signature(by_id[qid]) for qid in qids}
        if signatures & used or len(signatures) != len(qids):
            w.fail("repeated_query_across_rounds")
        used.update(signatures)
        if len(used) > budget:
            w.fail("session_budget_exceeded")
        payloads = round_.get("payloads")
        if not isinstance(payloads, list) or not payloads:
            w.fail("missing_round_results")
        payload_count += len(payloads)
        if payload_count > MAX_PAYLOADS:
            w.fail("payload_limit")
        payloads = [checked_payload(payload, plan, set(qids)) for payload in payloads]
        total += sum(len(payload["results"]) if "results" in payload else 0 for payload in payloads)
        if total > w.MAX_RESULTS:
            w.fail("result_limit")
        normalized_rounds.append({"number": number, "plan": plan, "plan_sha256": w.plan_digest(plan),
                                  "query_ids": qids, "payloads": payloads})
    return {"schema_version": 1, "scope": "research_session", "problem": root,
            "query_budget": budget, "max_rounds": max_rounds, "rounds": normalized_rounds}, used


def next_round(session, problem=None, budget=16):
    state, used = _validate(session)
    if len(state["rounds"]) >= state["max_rounds"]:
        w.fail("round_limit")
    budget = min(w.integer(budget, 1, w.MAX_QUERIES), state["query_budget"] - len(used))
    if not budget:
        w.fail("session_budget_exceeded")
    latest = state["rounds"][-1]["plan"]["problem"] if state["rounds"] else state["problem"]
    p = checked_problem(state["problem"], problem if problem is not None else latest)
    # Generate the complete bounded plan first; only distinct untouched
    # queries consume the session budget. No silent automatic retry.
    plan = w.make_plan(p, w.MAX_QUERIES)
    fresh = [row for row in plan["queries"] if signature(row) not in used]
    if not fresh:
        w.fail("no_new_queries_review_fingerprint")
    if state["rounds"]:
        previous = review(state, limit=12)
        gaps = set(previous["triage"]["family_gaps"])
        # Resolve source gaps first, then explore alternatives/counterevidence.
        fresh.sort(key=lambda row: (row["family"] not in gaps,
                   row["stage"] not in ("alternatives", "counterevidence"),
                   row["id"]))
    chosen = fresh[:budget]
    return {"schema_version": 1, "scope": "research_round_proposal",
            "session_sha256": w.plan_digest(state), "number": len(state["rounds"]) + 1,
            "plan_sha256": w.plan_digest(plan), "plan": plan,
            "query_ids": [row["id"] for row in chosen],
            "selected_queries": chosen, "remaining_query_budget": state["query_budget"] - len(used) - len(chosen),
            "review_required": True, "notice": NOTICE}


def append(session, proposal, payloads):
    state, _ = _validate(session)
    proposal = w.object_(proposal)
    if proposal.get("scope") != "research_round_proposal" or proposal.get("session_sha256") != w.plan_digest(state):
        w.fail("stale_round_proposal")
    plan = w.validate_plan(proposal.get("plan"))
    qids = proposal.get("query_ids")
    if not isinstance(qids, list) or not qids:
        w.fail("invalid_round_selection")
    expected = next_round(state, plan["problem"], len(qids))
    if proposal != expected:
        w.fail("round_proposal_changed")
    if not isinstance(payloads, list) or not payloads:
        w.fail("missing_round_results")
    state["rounds"].append({"number": proposal["number"], "plan": plan,
                            "plan_sha256": proposal["plan_sha256"], "query_ids": qids,
                            "payloads": [checked_payload(p, plan, set(qids)) for p in payloads]})
    return _validate(state)[0]


def review(session, limit=12, ranking="bm25"):
    state, used = _validate(session)
    if not state["rounds"]:
        return {"scope": "research_session_review", "rounds": 0,
                "remaining_query_budget": state["query_budget"], "notice": NOTICE}
    queries, inputs = [], []
    for round_ in state["rounds"]:
        prefix = f"R{round_['number']:02d}-"
        selected = set(round_["query_ids"])
        for row in round_["plan"]["queries"]:
            if row["id"] in selected:
                queries.append({**row, "id": prefix + row["id"]})
        for payload in round_["payloads"]:
            inputs.append({key: [{**row, "query_id": prefix + row["query_id"]} for row in payload.get(key, [])]
                           for key in ("results", "searches")})
    latest = state["rounds"][-1]["plan"]["problem"]
    combined = {"problem": latest, "queries": queries,
                "omitted_sources": [s for s in w.SOURCE_SPECS if s not in {q["source"] for q in queries}]}
    triage = w._rank_validated(combined, inputs, limit, ranking)
    completed = sum("completed" in row["status"] for row in triage["coverage"])
    attempted = sum(any(status not in ("not_recorded", "not_relevant", "skipped_budget") for status in row["status"])
                    for row in triage["coverage"])
    return {"scope": "research_session_review", "rounds": len(state["rounds"]),
            "planned_distinct_queries": len(used), "attempted_queries": attempted,
            "completed_queries": completed, "remaining_query_budget": state["query_budget"] - len(used),
            "remaining_rounds": state["max_rounds"] - len(state["rounds"]),
            "triage": triage, "notice": NOTICE}


def main(argv=None):
    parser = core.SafeArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=core.SafeArgumentParser)
    init = commands.add_parser("start")
    init.add_argument("--problem", required=True, type=Path)
    init.add_argument("--query-budget", type=int, default=48)
    init.add_argument("--max-rounds", type=int, default=3)
    init.add_argument("--output", required=True, type=Path)
    propose = commands.add_parser("next")
    propose.add_argument("--session", required=True, type=Path)
    propose.add_argument("--problem", type=Path)
    propose.add_argument("--budget", type=int, default=16)
    propose.add_argument("--output", required=True, type=Path)
    record = commands.add_parser("append")
    record.add_argument("--session", required=True, type=Path)
    record.add_argument("--proposal", required=True, type=Path)
    record.add_argument("--results", action="append", required=True, type=Path)
    record.add_argument("--output", required=True, type=Path)
    inspect = commands.add_parser("review")
    inspect.add_argument("--session", required=True, type=Path)
    inspect.add_argument("--limit", type=int, default=12)
    inspect.add_argument("--ranking", choices=("bm25", "facet"), default="bm25")
    inspect.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            result = start(w.read_json(args.problem), args.query_budget, args.max_rounds)
        elif args.command == "next":
            result = next_round(w.read_json(args.session), w.read_json(args.problem) if args.problem else None, args.budget)
        elif args.command == "append":
            result = append(w.read_json(args.session), w.read_json(args.proposal), [w.read_json(path) for path in args.results])
        else:
            result = review(w.read_json(args.session), args.limit, args.ranking)
        # A session must remain readable under the same bounded input policy.
        if len((json.dumps(result, ensure_ascii=True, indent=2) + "\n").encode()) > w.MAX_INPUT:
            w.fail("session_output_limit")
        w.write_json(result, args.output)
        return 0
    except (w.WorkflowError, OSError, ValueError, TypeError, RecursionError) as error:
        code = str(error) if isinstance(error, w.WorkflowError) else "invalid_input_or_file_operation"
        print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
