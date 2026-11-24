#!/usr/bin/env python3
"""Matched status-only simulation of legacy vs outcome-aware session planning.

Public task fingerprints are reused from the two discovery fixtures. No
relevance labels, documents, API requests or model outputs are used. Fix
budgets, task forms and status functions before running; report every pair.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/research-to-fix/scripts"))
import research_session as s
import research_workflow as w

DATASETS = ("algorithm_discovery_v1.json", "algorithm_transfer_v1.json")
SCENARIOS = ("all_available", "github_blocked", "paper_apis_blocked", "hash_partial")
BUDGETS = ((4, 4, 4), (6, 4, 4))
METRICS = ("completed_stages", "completed_families", "completed_queries",
           "counterevidence_completed", "all_stages_completed", "failed_queries")


def status(query, scenario):
    source = query["source"]
    if scenario == "github_blocked" and source.startswith("github_"):
        return "rate_limited"
    if scenario == "paper_apis_blocked" and source in (
            "arxiv", "crossref", "semantic_scholar", "openalex", "dblp"):
        return "unavailable"
    if scenario == "hash_partial":
        # Query-specific, independent of planner order and policy. Same
        # query gets exactly the same status in either arm.
        seed = "r2f-session-status-v1:" + "|".join(s.signature(query))
        draw = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:4], "big") % 10
        if draw < 2:
            return "partial"
        if draw < 4:
            return "rate_limited"
    return "completed"


def fingerprints():
    tasks = []
    hashes = {}
    for filename in DATASETS:
        path = ROOT / "benchmarks/datasets" / filename
        raw = path.read_bytes()
        hashes[filename] = hashlib.sha256(raw).hexdigest()
        for task in json.loads(raw)["tasks"]:
            problem = dict(task["problem"])
            tasks.append((filename + ":" + task["id"] + ":mechanism", problem))
            symptom = dict(problem, concepts=[], alternative_concepts=[], aliases=[])
            tasks.append((filename + ":" + task["id"] + ":symptom", symptom))
            if "bilingual_problem" in task:
                tasks.append((filename + ":" + task["id"] + ":bilingual", task["bilingual_problem"]))
    return tasks, hashes


def run(problem, scenario, budgets, strategy):
    state = s.start(problem, sum(budgets), len(budgets), strategy)
    seen = set()
    stages, families = set(), set()
    outcomes, rounds = Counter(), []
    for budget in budgets:
        proposal = s.next_round(state, budget=budget)
        queries = proposal["selected_queries"]
        if len(queries) != budget:
            raise RuntimeError("Matched budget not fulfilled")
        statuses = []
        for query in queries:
            signature = s.signature(query)
            if signature in seen:
                raise RuntimeError("Repeated query")
            seen.add(signature)
            result = status(query, scenario)
            outcomes[result] += 1
            if result == "completed":
                stages.add(query["stage"])
                families.add(query["family"])
            statuses.append({"query_id": query["id"], "status": result})
        rounds.append({"sources": [query["source"] for query in queries],
                       "stages": [query["stage"] for query in queries],
                       "statuses": [row["status"] for row in statuses],
                       "completed_stages_so_far": len(stages)})
        state = s.append(state, proposal, [{"searches": statuses, "results": []}])
    if len(seen) != sum(budgets) or s.review(state)["completed_queries"] != outcomes["completed"]:
        raise RuntimeError("Ledger disagrees with simulated outcomes")
    return {"completed_stages": len(stages), "completed_families": len(families),
            "completed_queries": outcomes["completed"],
            "counterevidence_completed": int("counterevidence" in stages),
            "all_stages_completed": int(stages == set(w.STAGES)),
            "failed_queries": sum(count for key, count in outcomes.items() if key != "completed"),
            "completed_stage_names": sorted(stages), "rounds": rounds}


def summary(rows):
    arms = {}
    for strategy in ("legacy", "coverage"):
        arms[strategy] = {metric: statistics.mean(row[strategy][metric] for row in rows)
                          for metric in METRICS}
    paired = {}
    for metric in METRICS:
        delta = [(row["coverage"][metric] - row["legacy"][metric]) *
                 (-1 if metric == "failed_queries" else 1) for row in rows]
        paired[metric] = {"mean_improvement": statistics.mean(delta),
                          "win": sum(d > 0 for d in delta), "tie": sum(d == 0 for d in delta),
                          "loss": sum(d < 0 for d in delta)}
    return {"pairs": len(rows), "methods": arms, "paired": paired}


def evaluate():
    tasks, hashes = fingerprints()
    rows, groups = [], defaultdict(list)
    for task, problem in tasks:
        for budgets in BUDGETS:
            for scenario in SCENARIOS:
                row = {"task": task, "budgets": list(budgets), "scenario": scenario,
                       **{strategy: run(problem, scenario, budgets, strategy)
                          for strategy in ("legacy", "coverage")}}
                rows.append(row)
                groups[scenario + ":" + str(sum(budgets))].append(row)
    return {"scope": "Deterministic status-only simulation on public task fingerprints; no live search, relevance or repair outcomes",
            "python": platform.python_version(), "platform": platform.platform(),
            "dataset_sha256": hashes, "fingerprints": len(tasks), "scenarios": list(SCENARIOS),
            "budgets": [list(row) for row in BUDGETS], "pairs": len(rows),
            "overall": summary(rows), "by_scenario_budget": {key: summary(value) for key, value in sorted(groups.items())},
            "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate()
    # Broad deterministic regression floors on the published fixed-status suite.
    old = result["overall"]["methods"]["legacy"]
    new = result["overall"]["methods"]["coverage"]
    if (new["completed_stages"] <= old["completed_stages"]
            or new["completed_families"] <= old["completed_families"]
            or new["all_stages_completed"] <= old["all_stages_completed"]
            or new["counterevidence_completed"] < old["counterevidence_completed"]):
        raise RuntimeError("coverage strategy regression")
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print("SESSION_COVERAGE_SUMMARY", json.dumps({key: value for key, value in result.items() if key != "rows"},
                                                 sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
