#!/usr/bin/env python3
"""Frozen same-model comparisons of R2F, no skill, and other installable skills.

Offline evaluator artifact importer; no model runs or repair claims.
"""
import argparse
import json
import math
from pathlib import Path
import re
import statistics

from agent_trials import (ArtifactLedger, artifact_summary, canonical, check_expected_digest, collect_arm, commit, fail, normalize_protocol,
                          outcome_breakdown, paired_interval, read_json, sha256)


def normalize(value):
    if not isinstance(value, dict) or set(value) != {"schema_version", "base_protocol", "arms"}:
        fail("Invalid comparison protocol")
    if type(value["schema_version"]) is not int or value["schema_version"] != 2:
        fail("Expected comparison protocol schema 2")
    shared = normalize_protocol(value["base_protocol"])
    arms = value["arms"]
    if not isinstance(arms, list) or not 2 <= len(arms) <= 8:
        fail("Declare 2–8 arms before generation")
    normalized = {}
    digests = set()
    for arm in arms:
        if not isinstance(arm, dict) or set(arm) != {"id", "repository", "commit", "skill_path", "intervention_sha256"}:
            fail("Invalid arm")
        name = arm["id"]
        if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", name)
                or name in normalized or re.fullmatch(r"con|prn|aux|nul|com[1-9]|lpt[1-9]", name)):
            fail("Invalid or duplicate arm ID")
        if name == "baseline":
            if any(arm[k] is not None for k in arm if k != "id"):
                fail("Baseline must have no intervention")
        else:
            repo, path, digest = arm["repository"], arm["skill_path"], arm["intervention_sha256"]
            if (not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
                    or any(part in (".", "..") for part in repo.split("/"))):
                fail("Expected owner/repository")
            commit(arm["commit"])
            if (not isinstance(path, str) or not path or len(path) > 300
                    or not re.fullmatch(r"[A-Za-z0-9_./-]+", path)
                    or any(part in ("", ".", "..") for part in path.split("/"))):
                fail("Unsafe skill path")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or digest in digests:
                fail("Expected distinct SHA-256 of exact installed intervention")
            digests.add(digest)
        normalized[name] = dict(arm)
    if "baseline" not in normalized or "skill" not in normalized:
        fail("Require baseline and skill arms")
    target = normalized["skill"]
    if target["repository"].lower() != "afloat16/research-to-fix" or target["commit"] != shared["skill_commit"]:
        fail("Target intervention must match frozen R2F commit")
    return {"schema_version": 2, "base_protocol": shared,
            "arms": [normalized[name] for name in sorted(normalized)]}


def freeze(value):
    protocol = normalize(value)
    return {"schema_version": 2, "scope": "matched_multi_arm_protocol",
            "protocol": protocol, "protocol_sha256": sha256(canonical(protocol))}


def validate_lock(lock, expected_protocol_sha256=None):
    if not isinstance(lock, dict) or lock != freeze(lock.get("protocol")):
        fail("Protocol lock mismatch")
    check_expected_digest(lock, expected_protocol_sha256)
    return lock["protocol"]


def sign_p(wins, losses):
    """Two-sided exact sign test of task-level directions, excluding ties."""
    n = wins + losses
    return min(1., 2 * sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / (2 ** n)) if n else 1.


def holm(values):
    """Step-down familywise adjustment across all predeclared comparisons."""
    adjusted, running = {}, 0.
    names = sorted(values, key=lambda name: (values[name], name))
    for i, name in enumerate(names):
        running = max(running, min(1., (len(names) - i) * values[name]))
        adjusted[name] = running
    return adjusted


def summarize(lock, root, *, expected_protocol_sha256=None, expected_artifacts_sha256=None):
    protocol = validate_lock(lock, expected_protocol_sha256)
    shared = protocol["base_protocol"]
    tasks = [r["instance_id"] for r in shared["instances"]]
    seeds = shared["seeds"]
    expected = [(task, seed) for task in tasks for seed in seeds]
    all_ids, all_rows, all_values, summaries = set(), {}, {}, {}
    ledgers = {arm["id"]: ArtifactLedger(root / arm["id"]) for arm in protocol["arms"]}
    for arm in protocol["arms"]:
        name = arm["id"]
        ids, rows = collect_arm(shared, lock["protocol_sha256"], root / name, name,
                                arm["commit"], intervention_digest=arm["intervention_sha256"],
                                require_digest=True, ledger=ledgers[name])
        if ids & all_ids:
            fail("Evaluator run IDs reused across arms")
        all_ids.update(ids)
        all_rows[name] = rows
        values = [statistics.mean(int(rows[(task, seed)]["resolved"]) for seed in seeds)
                  for task in tasks]
        all_values[name] = values
        statuses = {key: sum(row["status"] == key for row in rows.values())
                    for key in ("resolved", "unresolved", "empty_patch", "not_submitted",
                                "evaluation_missing_or_error", "usage_missing", "budget_exceeded")}
        measured = [row["usage"] for row in rows.values() if "usage" in row]
        summaries[name] = {"resolved_rate": statistics.mean(values), "statuses": statuses,
                           "outcome_breakdown": outcome_breakdown(rows),
                           "usage_records": len(measured), "usage_coverage": len(measured) / len(expected),
                           "recorded_usage_sum": {key: sum(row[key] for row in measured)
                                                  for key in ("tokens", "tool_calls", "seconds")}}
    artifacts = artifact_summary(lock["protocol_sha256"], ledgers, expected_artifacts_sha256)
    comparisons = {}
    for name in sorted(all_values):
        if name != "skill":
            interval = paired_interval(all_values["skill"], all_values[name])
            comparisons[name] = {**interval, "sign_p": sign_p(interval["win"], interval["loss"])}
    adjusted = holm({name: row["sign_p"] for name, row in comparisons.items()})
    for name, row in comparisons.items():
        row["holm_adjusted_sign_p"] = adjusted[name]
        row["positive_direction_at_fwer_0_05"] = (
            row["win"] > row["loss"] and adjusted[name] <= .05 and row["ci95_low"] > 0)
    return {"scope": "matched_multi_arm_external_agent_evaluation",
            "protocol_sha256": lock["protocol_sha256"], "tasks": len(tasks),
            "expected_protocol_digest_checked": expected_protocol_sha256 is not None,
            "seeds": len(seeds), "trials_per_arm": len(expected), "arms": summaries,
            "consumed_artifacts": artifacts,
            "skill_vs_predeclared_arms": comparisons,
            "pairs": [{"instance_id": task, "seed": seed,
                       "arms": {name: rows[(task, seed)] for name, rows in all_rows.items()}}
                      for task, seed in expected],
            "notice": "All tasks/replicates stay in denominator; missing or over-budget outcomes are not successes. "
                      "Bootstrap intervals are pointwise for mean task deltas; Holm-adjusted sign tests assess direction, not magnitude. "
                      "Recorded cost sums with incomplete coverage are lower bounds, not comparable full costs. "
                      "Artifact/manifest checks do not authenticate the evaluator, intervention bytes, or agent isolation. "
                      "No universal superiority conclusion follows."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze", type=Path)
    group.add_argument("--lock", type=Path)
    parser.add_argument("--arms-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", help="Independently retained pre-generation protocol digest")
    parser.add_argument("--expected-artifacts-sha256", help="Independently retained post-evaluation consumed artifact digest")
    args = parser.parse_args()
    if args.freeze:
        if args.expected_protocol_sha256 is not None or args.expected_artifacts_sha256 is not None:
            parser.error("Expected digests apply only when importing")
        result = freeze(read_json(args.freeze))
    elif args.arms_root:
        result = summarize(read_json(args.lock), args.arms_root,
                           expected_protocol_sha256=args.expected_protocol_sha256,
                           expected_artifacts_sha256=args.expected_artifacts_sha256)
    else:
        parser.error("Supply all predeclared arm artifacts")
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
