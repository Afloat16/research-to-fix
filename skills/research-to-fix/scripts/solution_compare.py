#!/usr/bin/env python3
"""Compare locally measured alternative repairs under a fixed experiment protocol."""
import json
import math
import re
import statistics
import sys
from pathlib import Path

import research_case as core
import research_workflow as w

NOTICE = ("Conditional comparison of supplied local measurements, not execution, authentication, "
          "statistical significance, proof of causality or globally optimal repair. Keep source "
          "verification, case validation and actual test artifacts separate.")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
MAX_CANDIDATES = 12
MAX_REPLICATES = 64
MAX_OBJECTIVES = 12
MAX_CHECKS = 24
MAX_ABS = 1e100
STATES = ("planned", "blocked", "measured")
BASIS = ("baseline", "local", "external", "mixed")


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        w.fail("invalid_identifier")
    return value


def rows(value, maximum, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        w.fail("invalid_rows")
    return [w.object_(row) for row in value]


def unique_ids(values, maximum, minimum=0):
    if not isinstance(values, list) or not minimum <= len(values) <= maximum:
        w.fail("invalid_identifiers")
    result = [identifier(value) for value in values]
    if len(result) != len(set(result)):
        w.fail("duplicate_identifier")
    return result


def finite(value):
    if type(value) not in (int, float) or abs(value) > MAX_ABS or not math.isfinite(value):
        w.fail("invalid_measurement")
    return float(value)


def context(value):
    value = w.object_(value)
    if not 1 <= len(value) <= 24:
        w.fail("invalid_comparison_context")
    return {identifier(key): w.text(val, 300) for key, val in value.items()}


def protocol(value):
    value = w.object_(value)
    ctx = context(value.get("context"))
    command = w.text(value.get("command"), 1000)
    replicate_ids = unique_ids(value.get("replicates"), MAX_REPLICATES, 1)
    objectives = {}
    for row in rows(value.get("objectives"), MAX_OBJECTIVES, 1):
        key = identifier(row.get("id"))
        if key in objectives:
            w.fail("duplicate_objective")
        direction = row.get("direction")
        if direction not in ("min", "max"):
            w.fail("invalid_direction")
        item = {"unit": w.text(row.get("unit"), 40), "direction": direction}
        if "threshold" in row:
            item["threshold"] = finite(row["threshold"])
        objectives[key] = item
    checks = {}
    for row in rows(value.get("checks"), MAX_CHECKS, 1):
        key = identifier(row.get("id"))
        if key in checks:
            w.fail("duplicate_check")
        kind = row.get("kind")
        if kind not in ("original", "regression", "constraint"):
            w.fail("invalid_check_kind")
        checks[key] = {"kind": kind, "description": w.text(row.get("description"), 300)}
    if not any(row["kind"] == "original" for row in checks.values()):
        w.fail("original_check_required")
    priorities = unique_ids(value.get("priority", []), MAX_OBJECTIVES)
    if priorities and set(priorities) != set(objectives):
        w.fail("priority_must_cover_objectives")
    return {"id": identifier(value.get("id")), "context": ctx, "command": command,
            "replicates": replicate_ids, "objectives": objectives, "checks": checks, "priority": priorities}


def evidence_records(value):
    evidence = {}
    for row in rows(value, 60):
        key = identifier(row.get("id"))
        if key in evidence:
            w.fail("duplicate_evidence")
        access = row.get("access")
        if access not in w.ACCESS:
            w.fail("invalid_access")
        evidence[key] = {"url": w.canonical_url(row.get("url")), "access": access,
                         "claim": w.text(row.get("claim"), 600),
                         "conditions": w.text(row.get("conditions"), 500),
                         "limitations": w.text(row.get("limitations"), 500)}
    return evidence


def measure_summary(values):
    return {"median": statistics.median(values), "min": min(values), "max": max(values),
            "n": len(values)}


def candidate(row, spec, evidence):
    key = identifier(row.get("id"))
    basis = row.get("basis")
    state = row.get("state")
    if basis not in BASIS or state not in STATES:
        w.fail("invalid_candidate_state")
    refs = unique_ids(row.get("evidence_ids", []), 20)
    if any(ref not in evidence for ref in refs):
        w.fail("unknown_evidence")
    if basis in ("external", "mixed") and not refs:
        w.fail("external_evidence_required")
    title = w.text(row.get("title"), 200)
    if basis != "baseline":
        # A distinct mechanism, local target and falsifiable hypothesis, not
        # merely three names for one approach.
        for field in ("mechanism", "local_target", "hypothesis", "change"):
            w.text(row.get(field), 600)
    reasons = []
    if state != "measured":
        reasons.append("not_measured" if state == "planned" else "blocked")
        if state == "blocked":
            w.text(row.get("blocker"), 500)
    if basis in ("external", "mixed") and not any(evidence[ref]["access"] == "read" for ref in refs):
        reasons.append("original_evidence_not_read")
    same_protocol = row.get("protocol_id") == spec["id"] and row.get("context") == spec["context"]
    if state == "measured" and not same_protocol:
        reasons.append("comparison_context_mismatch")
    observed = {}
    for run in rows(row.get("runs", []), MAX_REPLICATES):
        rep = identifier(run.get("replicate"))
        if rep not in spec["replicates"] or rep in observed:
            w.fail("invalid_replicate")
        metrics = w.object_(run.get("metrics"))
        checks = w.object_(run.get("checks"))
        if set(metrics) != set(spec["objectives"]) or set(checks) != set(spec["checks"]):
            w.fail("measurement_fields_mismatch")
        normalized = {key: finite(val) for key, val in metrics.items()}
        if any(status not in ("pass", "fail", "not_run") for status in checks.values()):
            w.fail("invalid_check_outcome")
        command = w.text(run.get("command"), 1000)
        w.text(run.get("observed"), 800)
        if command != spec["command"]:
            same_protocol = False
            if "comparison_context_mismatch" not in reasons:
                reasons.append("comparison_context_mismatch")
        observed[rep] = {"metrics": normalized, "checks": checks}
    if state != "measured" and observed:
        w.fail("unmeasured_candidate_has_runs")
    complete = state == "measured" and set(observed) == set(spec["replicates"]) and same_protocol
    if state == "measured" and set(observed) != set(spec["replicates"]):
        reasons.append("missing_replicates")
    failures = []
    thresholds = []
    for rep, run in observed.items():
        failures.extend({"replicate": rep, "check": check, "status": status}
                        for check, status in run["checks"].items() if status != "pass")
        for key_, metric in spec["objectives"].items():
            if "threshold" not in metric:
                continue
            value = run["metrics"][key_]
            threshold = metric["threshold"]
            if (metric["direction"] == "min" and value > threshold) or (
                    metric["direction"] == "max" and value < threshold):
                thresholds.append({"replicate": rep, "objective": key_})
    if failures:
        reasons.append("hard_checks_not_passed")
    if thresholds:
        reasons.append("objective_threshold_not_met")
    summaries = {key_: measure_summary([observed[rep]["metrics"][key_] for rep in spec["replicates"]])
                 for key_ in spec["objectives"]} if complete else {}
    return {"id": key, "title": title, "basis": basis, "state": state,
            "evidence_ids": refs, "comparable": complete, "eligible": complete and not reasons,
            "reasons": reasons, "replicates_observed": len(observed), "metrics": summaries,
            "failed_checks": failures, "threshold_failures": thresholds}, observed


def dominance(a, b, objectives):
    """Exact median dominance under declared units/directions (no hidden weights)."""
    good = []
    for key, obj in objectives.items():
        left, right = a["metrics"][key]["median"], b["metrics"][key]["median"]
        good.append((left > right) - (left < right) if obj["direction"] == "max"
                    else (left < right) - (left > right))
    return all(value >= 0 for value in good) and any(value > 0 for value in good)


def paired_delta(base, other, spec):
    result = {}
    for key, obj in spec["objectives"].items():
        differences = []
        for rep in spec["replicates"]:
            before, after = base[rep]["metrics"][key], other[rep]["metrics"][key]
            differences.append(after - before if obj["direction"] == "max" else before - after)
        result[key] = {**measure_summary(differences),
                       "improved_pairs": sum(value > 0 for value in differences),
                       "tied_pairs": sum(value == 0 for value in differences),
                       "worse_pairs": sum(value < 0 for value in differences),
                       "positive_is_improvement": True}
    return result


def compare(value):
    value = w.object_(value)
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        w.fail("invalid_comparison_schema")
    spec = protocol(value.get("protocol"))
    evidence = evidence_records(value.get("evidence", []))
    candidates, runs = [], {}
    for row in rows(value.get("candidates"), MAX_CANDIDATES, 2):
        result, observations = candidate(row, spec, evidence)
        if result["id"] in runs:
            w.fail("duplicate_candidate")
        candidates.append(result)
        runs[result["id"]] = observations
    bases = [row for row in candidates if row["basis"] == "baseline"]
    if len(bases) != 1:
        w.fail("one_baseline_required")
    baseline = bases[0]
    for row in candidates:
        if row is not baseline and baseline["comparable"] and row["comparable"]:
            row["paired_improvement"] = paired_delta(runs[baseline["id"]], runs[row["id"]], spec)
    eligible = [row for row in candidates if row["eligible"] and baseline["comparable"]]
    frontier = [row for row in eligible if not any(dominance(other, row, spec["objectives"])
                                                   for other in eligible if other is not row)]
    frontier.sort(key=lambda row: row["id"])
    decision, selected = "tradeoffs_require_choice", None
    if not baseline["comparable"]:
        decision = "baseline_not_comparable"
    elif not frontier:
        decision = "no_eligible_measured_candidate"
    elif len(frontier) == 1:
        selected = frontier[0]["id"]
        decision = "unique_measured_frontier"
    elif spec["priority"]:
        def key(row):
            return tuple(row["metrics"][metric]["median"] * (1 if spec["objectives"][metric]["direction"] == "min" else -1)
                         for metric in spec["priority"])
        ordered = sorted(frontier, key=lambda row: (key(row), row["id"]))
        if key(ordered[0]) != key(ordered[1]):
            selected = ordered[0]["id"]
            decision = "declared_lexicographic_preference"
    if selected == baseline["id"]:
        decision, selected = "baseline_preferred", None
    warnings = []
    if len(spec["replicates"]) < 3:
        warnings.append("fewer_than_three_replicates_descriptive_only")
    if not any(row["kind"] == "regression" for row in spec["checks"].values()):
        warnings.append("no_explicit_regression_check")
    if any(row["state"] != "measured" for row in candidates):
        warnings.append("unmeasured_options_remain")
    return {"schema_version": 1, "scope": "conditional_measured_comparison", "notice": NOTICE,
            "protocol_id": spec["id"], "replicates": len(spec["replicates"]),
            "objectives": spec["objectives"], "declared_priority": spec["priority"],
            "baseline": baseline["id"], "decision": decision, "selected_candidate": selected,
            "pareto_frontier": [row["id"] for row in frontier],
            "candidates": sorted(candidates, key=lambda row: row["id"]),
            "warnings": warnings, "review_required": True}


def main(argv=None):
    parser = core.SafeArgumentParser(description=__doc__)
    parser.add_argument("--comparison", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        w.write_json(compare(w.read_json(args.comparison)), args.output)
        return 0
    except (w.WorkflowError, OSError, ValueError, TypeError, RecursionError) as error:
        code = str(error) if isinstance(error, w.WorkflowError) else "invalid_input_or_file_operation"
        print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
