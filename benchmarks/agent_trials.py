#!/usr/bin/env python3
"""Offline, paired scoring of actual SWE-bench evaluator outputs.

This does not run a model, download a task, execute a patch, or certify the
authenticity of externally supplied reports. Missing/blocked tasks stay in
the original denominator. Never expose gold patches or evaluator logs to agents.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

from independent_retrieval import paired_interval
import research_case as rc

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}")
SHA = re.compile(r"[0-9a-f]{40}")
MAX_FILE = 16 * 1024 * 1024
MAX_TASKS = 1000


def fail(message):
    raise ValueError(message)


def read(path, maximum=MAX_FILE):
    # Reject symlinks along the explicit path beneath the provided root.
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            fail("Linked evaluation input")
    raw, error = rc._read_regular_file(path, maximum)
    if error:
        fail("Nonregular or oversized evaluation input")
    return raw


def read_json(path):
    return rc.decode_case_bytes(read(path))[0]


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


class ArtifactLedger:
    """Digest exact bytes consumed by one importer arm, without reading extras.

    Caller controls the artifact directory during import. The digest is not a
    signature, authenticity check, or proof of absent unconsumed files.
    """

    def __init__(self, root):
        self.root = Path(root)
        self.files = {}

    def read(self, path):
        key = Path(path).relative_to(self.root).as_posix()
        raw = read(path)
        row = {"bytes": len(raw), "sha256": sha256(raw)}
        if key in self.files and self.files[key] != row:
            fail("Evaluation input changed while reading")
        self.files[key] = row
        return raw

    def read_json(self, path):
        return rc.decode_case_bytes(self.read(path))[0]

    def summary(self):
        return {"sha256": sha256(canonical(self.files)), "files": len(self.files),
                "bytes": sum(row["bytes"] for row in self.files.values())}


def artifact_summary(protocol_digest, ledgers, expected=None):
    arms = {name: ledger.summary() for name, ledger in sorted(ledgers.items())}
    digest = sha256(canonical({"scope": "consumed_agent_evaluation_artifacts_v1",
                               "protocol_sha256": protocol_digest, "arms": arms}))
    if expected is not None and (not isinstance(expected, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected) or digest != expected):
        fail("Independent artifact digest mismatch")
    return {"scope": "consumed_agent_evaluation_artifacts_v1", "sha256": digest,
            "arms": arms, "expected_digest_checked": expected is not None}


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        fail("Invalid identifier")
    return value


def label(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 300 or any(ord(c) < 32 for c in value):
        fail("Invalid protocol label")
    return value


def positive(value, upper):
    if type(value) is not int or not 1 <= value <= upper:
        fail("Invalid budget")
    return value


def commit(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        fail("Expected full commit SHA")
    return value


def normalize_protocol(value):
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        fail("Invalid protocol")
    fields = {"schema_version", "dataset", "dataset_revision", "split", "evaluator_commit",
              "scaffold_commit", "skill_commit", "model", "model_revision", "environment",
              "network_policy", "generation_config", "max_tokens", "max_tool_calls",
              "max_seconds", "seeds", "instances"}
    if set(value) != fields:
        fail("Unexpected protocol fields")
    out = {"schema_version": 1}
    for key in ("dataset", "split", "model", "model_revision", "environment", "network_policy", "generation_config"):
        out[key] = label(value[key])
    for key in ("dataset_revision", "evaluator_commit", "scaffold_commit", "skill_commit"):
        out[key] = commit(value[key])
    out["max_tokens"] = positive(value["max_tokens"], 10**8)
    out["max_tool_calls"] = positive(value["max_tool_calls"], 10**6)
    out["max_seconds"] = positive(value["max_seconds"], 86400)
    seeds = value["seeds"]
    if (not isinstance(seeds, list) or not 1 <= len(seeds) <= 8 or any(type(s) is not int or not 0 <= s <= 2**32 - 1 for s in seeds)
            or len(set(seeds)) != len(seeds)):
        fail("Invalid replicate seeds")
    out["seeds"] = sorted(seeds)
    instances = value["instances"]
    if not isinstance(instances, list) or not 1 <= len(instances) <= MAX_TASKS:
        fail("Invalid task list")
    ids = []
    for row in instances:
        if not isinstance(row, dict) or set(row) != {"instance_id", "base_commit", "repo"}:
            fail("Invalid task")
        ids.append({"instance_id": identifier(row["instance_id"]), "base_commit": commit(row["base_commit"]),
                    "repo": label(row["repo"])})
    if len({row["instance_id"] for row in ids}) != len(ids):
        fail("Duplicate task")
    out["instances"] = sorted(ids, key=lambda row: row["instance_id"])
    return out


def freeze(value):
    protocol = normalize_protocol(value)
    return {"schema_version": 1, "scope": "paired_agent_protocol",
            "protocol": protocol, "protocol_sha256": sha256(canonical(protocol))}


def check_expected_digest(lock, expected):
    """Optionally compare against a digest retained independently before generation."""
    if expected is not None and (not isinstance(expected, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected)
            or expected != lock["protocol_sha256"]):
        fail("Independent protocol digest mismatch")


def validate_lock(lock, expected_protocol_sha256=None):
    if not isinstance(lock, dict) or lock != freeze(lock.get("protocol")):
        fail("Protocol lock mismatch")
    check_expected_digest(lock, expected_protocol_sha256)
    return lock["protocol"]


def parse_predictions(path, expected, *, ledger=None):
    value = (ledger.read_json if ledger is not None else read_json)(path)
    if not isinstance(value, list) or len(value) > len(expected):
        fail("Invalid official predictions")
    predictions = {}
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get("instance_id"), str):
            fail("Invalid prediction")
        task = identifier(row["instance_id"])
        if (task not in expected or task in predictions or "model_patch" not in row
                or (row["model_patch"] is not None and not isinstance(row["model_patch"], str))):
            fail("Unexpected prediction or patch")
        label(row.get("model_name_or_path"))
        patch = row["model_patch"]
        predictions[task] = None if patch is None else patch.encode("utf-8")
    return predictions


def report_outcome(value, task):
    """Accept legacy minimal reports; cross-check official flags when supplied."""
    if (not isinstance(value, dict) or set(value) != {task}
            or not isinstance(value[task], dict) or type(value[task].get("resolved")) is not bool):
        fail("Invalid official per-instance evaluation report")
    row = value[task]
    names = ("patch_is_None", "patch_exists", "patch_successfully_applied", "infra_failure")
    flags = {name: row[name] for name in names if name in row}
    if any(type(flag) is not bool for flag in flags.values()):
        fail("Invalid official evaluation flag")
    # This function only receives reports for submitted nonempty patches.
    if (flags.get("patch_is_None") is True or flags.get("patch_exists") is False
            or (row["resolved"] and (flags.get("patch_successfully_applied") is False
                                    or flags.get("infra_failure") is True))):
        fail("Contradictory official evaluation flags")
    return row["resolved"], flags


def usage_record(value, protocol):
    if not isinstance(value, dict) or set(value) != {"tokens", "tool_calls", "seconds"}:
        fail("Invalid usage record")
    tokens, calls, seconds = value["tokens"], value["tool_calls"], value["seconds"]
    if (type(tokens) is not int or tokens < 0 or type(calls) is not int or calls < 0
            or type(seconds) not in (int, float) or seconds < 0 or not math.isfinite(seconds)):
        fail("Invalid usage numbers")
    return (tokens <= protocol["max_tokens"] and calls <= protocol["max_tool_calls"]
            and seconds <= protocol["max_seconds"])


def collect(lock, root, arm, *, ledger=None):
    p = validate_lock(lock)
    return collect_arm(p, lock["protocol_sha256"], root, arm,
                       p["skill_commit"] if arm == "skill" else None, ledger=ledger)


def collect_arm(p, protocol_digest, root, arm, skill_commit, *, intervention_digest=None, require_digest=False, ledger=None):
    """Shared artifact checks for paired and multi-arm trials."""
    reader = ledger.read if ledger is not None else read
    json_reader = ledger.read_json if ledger is not None else read_json
    manifest = json_reader(root / "manifest.json")
    fields = {"protocol_sha256", "arm", "applied_skill_commit", "run_ids"}
    if require_digest:
        fields.add("intervention_sha256")
    if not isinstance(manifest, dict) or set(manifest) != fields:
        fail("Invalid run manifest")
    if (manifest["protocol_sha256"] != protocol_digest or manifest["arm"] != arm
            or manifest["applied_skill_commit"] != skill_commit
            or (require_digest and manifest["intervention_sha256"] != intervention_digest)):
        fail("Run does not match frozen intervention")
    expected = {row["instance_id"] for row in p["instances"]}
    run_ids = manifest["run_ids"]
    if not isinstance(run_ids, dict) or set(run_ids) != {str(seed) for seed in p["seeds"]}:
        fail("Missing replicate run ID")
    ids = {identifier(value) for value in run_ids.values()}
    if len(ids) != len(p["seeds"]):
        fail("Reused evaluator run ID")
    rows = {}
    for seed in p["seeds"]:
        directory = root / ("seed-" + str(seed))
        predictions = parse_predictions(directory / "predictions.json", expected, ledger=ledger)
        usage = json_reader(directory / "usage.json")
        if not isinstance(usage, dict) or not set(usage) <= expected:
            fail("Invalid usage task IDs")
        for task, measurement in usage.items():
            usage_record(measurement, p)
        for task in sorted(expected):
            submitted = task in predictions
            patch = predictions.get(task)
            record = {"instance_id": task, "seed": seed, "resolved": False,
                      "prediction_status": ("missing" if not submitted else
                                            "empty" if patch is None or not patch.strip() else "nonempty"),
                      "evaluation_status": "not_applicable",
                      "budget_status": ("usage_missing" if task not in usage else
                                        "within_budget" if usage_record(usage[task], p) else "budget_exceeded")}
            if patch is not None:
                record["prediction_sha256"] = sha256(patch)
            if not submitted:
                record["status"] = "not_submitted"
            elif patch is None or not patch.strip():
                record["status"] = "empty_patch"
                if patch is None:
                    record["prediction_is_null"] = True
            else:
                location = directory / "reports" / task
                report_path = location / "report.json"
                if report_path.exists() or report_path.is_symlink():
                    if reader(location / "patch.diff") != patch:
                        fail("Evaluator patch differs from prediction")
                    raw = reader(report_path)
                    report = rc.decode_case_bytes(raw)[0]
                    resolved, flags = report_outcome(report, task)
                    record["report_sha256"] = sha256(raw)
                    record["status"] = "resolved" if resolved else "unresolved"
                    record["resolved"] = resolved
                    if flags:
                        record["evaluation_flags"] = flags
                else:
                    record["status"] = "evaluation_missing_or_error"
                record["evaluation_status"] = record["status"]
            if submitted:
                if task not in usage:
                    record.update(status="usage_missing", resolved=False)
                elif not usage_record(usage[task], p):
                    record.update(status="budget_exceeded", resolved=False)
            if task in usage:
                record["usage"] = usage[task]
            rows[(task, seed)] = record
    return ids, rows


def outcome_breakdown(rows):
    """Orthogonal counts retain evaluator outcomes even when budget gates override them."""
    return {axis: {state: sum(row[axis] == state for row in rows.values()) for state in states}
            for axis, states in (
                ("prediction_status", ("missing", "empty", "nonempty")),
                ("evaluation_status", ("not_applicable", "resolved", "unresolved", "evaluation_missing_or_error")),
                ("budget_status", ("usage_missing", "within_budget", "budget_exceeded")))}


def summarize(lock, baseline_root, skill_root, *, expected_protocol_sha256=None, expected_artifacts_sha256=None):
    p = validate_lock(lock, expected_protocol_sha256)
    ledgers = {"baseline": ArtifactLedger(baseline_root), "skill": ArtifactLedger(skill_root)}
    base_ids, base = collect(lock, baseline_root, "baseline", ledger=ledgers["baseline"])
    skill_ids, skill = collect(lock, skill_root, "skill", ledger=ledgers["skill"])
    artifacts = artifact_summary(lock["protocol_sha256"], ledgers, expected_artifacts_sha256)
    if base_ids & skill_ids:
        fail("Evaluator run IDs reused between arms")
    expected = sorted(base)
    # Cluster at task level: repeated seeds are not independent tasks.
    tasks = sorted({task for task, _ in expected})
    per_task = lambda rows: [statistics.mean(int(rows[(task, seed)]["resolved"]) for seed in p["seeds"]) for task in tasks]
    base_values, skill_values = per_task(base), per_task(skill)
    status = lambda rows: {key: sum(row["status"] == key for row in rows.values())
                           for key in ("resolved", "unresolved", "empty_patch", "not_submitted",
                                       "evaluation_missing_or_error", "usage_missing", "budget_exceeded")}
    usage = lambda rows: {key: sum(row.get("usage", {}).get(key, 0) for row in rows.values())
                          for key in ("tokens", "tool_calls", "seconds")}
    return {"scope": "matched_external_agent_evaluation",
            "protocol_sha256": lock["protocol_sha256"], "tasks": len(tasks), "seeds": len(p["seeds"]),
            "trials_per_arm": len(expected), "expected_protocol_digest_checked": expected_protocol_sha256 is not None,
            "consumed_artifacts": artifacts,
            "baseline": {"resolved_rate": statistics.mean(base_values),
                "statuses": status(base), "recorded_usage_sum": usage(base), "outcome_breakdown": outcome_breakdown(base),
                "usage_coverage": sum("usage" in row for row in base.values()) / len(expected)},
            "skill": {"resolved_rate": statistics.mean(skill_values),
                "statuses": status(skill), "recorded_usage_sum": usage(skill), "outcome_breakdown": outcome_breakdown(skill),
                "usage_coverage": sum("usage" in row for row in skill.values()) / len(expected)},
            "paired_task_interval": paired_interval(skill_values, base_values),
            "pairs": [{"instance_id": task, "seed": seed, "baseline": base[(task, seed)],
                       "skill": skill[(task, seed)]} for task, seed in expected],
            "notice": "All frozen tasks/replicates remain in denominator; missing, failed or over-budget trials are not successes. "
                      "The tool validates supplied artifacts and protocol consistency, not evaluator authenticity, model isolation or causality. "
                      "Use independent agent processes and hide gold patches/tests from agent generation."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze", type=Path)
    group.add_argument("--lock", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--skill", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", help="Independently retained pre-generation protocol digest")
    parser.add_argument("--expected-artifacts-sha256", help="Independently retained post-evaluation consumed artifact digest")
    args = parser.parse_args()
    if args.freeze:
        if args.expected_protocol_sha256 is not None or args.expected_artifacts_sha256 is not None:
            parser.error("Expected digests apply only when importing")
        result = freeze(read_json(args.freeze))
    elif args.baseline and args.skill:
        result = summarize(read_json(args.lock), args.baseline, args.skill,
                           expected_protocol_sha256=args.expected_protocol_sha256,
                           expected_artifacts_sha256=args.expected_artifacts_sha256)
    else:
        parser.error("Both actual evaluation artifact roots are required")
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
