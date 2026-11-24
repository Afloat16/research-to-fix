#!/usr/bin/env python3
"""Compare locally measured alternative repairs under a fixed experiment protocol."""
import json
import math
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
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
        if "resolution" in row:
            resolution = finite(row["resolution"])
            if not 1e-100 <= resolution <= MAX_ABS:
                w.fail("invalid_objective_resolution")
            item["resolution"] = resolution
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
    policy = value.get("decision_policy", "median")
    if policy not in ("median", "all_pairs"):
        w.fail("invalid_decision_policy")
    return {"id": identifier(value.get("id")), "context": ctx, "command": command,
            "replicates": replicate_ids, "objectives": objectives, "checks": checks,
            "priority": priorities, "decision_policy": policy}


def freeze_protocol(value):
    """Freeze before execution; the lock detects later drift, not chronology."""
    spec = protocol(value)
    return {"schema_version": 1, "scope": "experiment_protocol_lock",
            "protocol_sha256": w.plan_digest(spec), "protocol": spec,
            "notice": "Store this independently before measuring; hash consistency does not prove when it was created."}


def check_lock(value, spec):
    value = w.object_(value)
    if (value.get("schema_version") != 1 or value.get("scope") != "experiment_protocol_lock"
            or value.get("protocol") != spec or value.get("protocol_sha256") != w.plan_digest(spec)):
        w.fail("protocol_lock_mismatch")


def evidence_records(value):
    evidence = {}
    for row in rows(value, 60):
        key = identifier(row.get("id"))
        if key in evidence:
            w.fail("duplicate_evidence")
        access = row.get("access")
        if access not in w.ACCESS:
            w.fail("invalid_access")
        kind = row.get("source_kind", "unspecified")
        if kind not in ("paper", "repository", "issue", "documentation", "dataset", "other", "unspecified"):
            w.fail("invalid_evidence_kind")
        evidence[key] = {"url": w.canonical_url(row.get("url")), "original_url": row["url"], "access": access,
                         "claim": w.text(row.get("claim"), 600),
                         "conditions": w.text(row.get("conditions"), 500),
                         "limitations": w.text(row.get("limitations"), 500),
                         "source_kind": kind,
                         "locator": w.text(row.get("locator", ""), 300, False),
                         "revision": w.text(row.get("revision", ""), 120, False)}
    return evidence


def measure_summary(values):
    median = statistics.median(values)
    return {"median": median, "min": min(values), "max": max(values),
            "mad": statistics.median(abs(value - median) for value in values), "n": len(values)}


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
    supporting = unique_ids(row.get("supporting_evidence_ids", refs if basis in ("external", "mixed") else []), 20)
    if not set(supporting).issubset(refs) or (basis in ("external", "mixed") and not supporting):
        w.fail("invalid_supporting_evidence")
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
    if any(evidence[ref]["access"] != "read" for ref in supporting):
        reasons.append("original_evidence_not_read")
    compatibility = row.get("compatibility_review")
    if compatibility is not None:
        if compatibility not in ("compatible", "unknown", "incompatible"):
            w.fail("invalid_compatibility_review")
        if compatibility != "compatible":
            reasons.append("compatibility_not_established")
    reuse_code = row.get("reuse_external_code", False)
    if type(reuse_code) is not bool:
        w.fail("invalid_code_reuse")
    if reuse_code and row.get("license_review") != "permitted":
        reasons.append("external_code_license_not_established")
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
            "evidence_ids": refs, "supporting_evidence_ids": supporting,
            "comparable": complete, "eligible": complete and not reasons,
            "reasons": reasons, "replicates_observed": len(observed), "metrics": summaries,
            "failed_checks": failures, "threshold_failures": thresholds}, observed


def preference_value(value, objective):
    """Comparable value, lower is better; optional fixed measurement bins.

    Bins use exact decimal rounding of the supplied numeric representation.
    They are a declared resolution, not a statistical confidence interval.
    """
    if "resolution" in objective:
        with localcontext() as ctx:
            ctx.prec = 240
            value = (Decimal(str(value)) / Decimal(str(objective["resolution"]))).to_integral_value(rounding=ROUND_HALF_EVEN)
    return value if objective["direction"] == "min" else -value


def dominance(a, b, objectives):
    """Median dominance under declared directions and optional fixed bins."""
    left = [preference_value(a["metrics"][key]["median"], obj) for key, obj in objectives.items()]
    right = [preference_value(b["metrics"][key]["median"], obj) for key, obj in objectives.items()]
    return all(x <= y for x, y in zip(left, right)) and any(x < y for x, y in zip(left, right))


def paired_dominance(a, b, spec):
    """Conservative dominance: no worse on any objective in any matched run."""
    comparisons = [(preference_value(a[rep]["metrics"][key], obj),
                    preference_value(b[rep]["metrics"][key], obj))
                   for rep in spec["replicates"] for key, obj in spec["objectives"].items()]
    return all(x <= y for x, y in comparisons) and any(x < y for x, y in comparisons)

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


def design_definition(value):
    """Canonical pre-measurement design (protocol + candidates + cited evidence)."""
    value = w.object_(value)
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        w.fail("invalid_comparison_schema")
    spec = protocol(value.get("protocol"))
    evidence = evidence_records(value.get("evidence", []))
    definitions = {}
    for row in rows(value.get("candidates"), MAX_CANDIDATES, 2):
        result, _ = candidate(row, spec, evidence)
        key = result["id"]
        if key in definitions:
            w.fail("duplicate_candidate")
        if result["basis"] in ("external", "mixed"):
            if row.get("compatibility_review") != "compatible":
                w.fail("design_compatibility_review_required")
            for ref in result["supporting_evidence_ids"]:
                source = evidence[ref]
                if source["access"] != "read" or not source["locator"] or source["source_kind"] == "unspecified":
                    w.fail("design_support_locator_required")
                if source["source_kind"] == "repository" and not source["revision"]:
                    w.fail("design_code_revision_required")
        if row.get("reuse_external_code", False) and row.get("license_review") != "permitted":
            w.fail("design_code_license_required")
        static = {field: result[field] for field in ("id", "title", "basis", "evidence_ids", "supporting_evidence_ids")}
        if result["basis"] != "baseline":
            static.update({field: w.text(row[field], 600) for field in ("mechanism", "local_target", "hypothesis", "change")})
        static.update(compatibility_review=row.get("compatibility_review"),
                      reuse_external_code=row.get("reuse_external_code", False), license_review=row.get("license_review"))
        definitions[key] = static
    if sum(row["basis"] == "baseline" for row in definitions.values()) != 1:
        w.fail("one_baseline_required")
    return {"protocol": spec, "evidence": evidence, "candidates": definitions}


def freeze_design(value):
    design = design_definition(value)
    if any(row.get("state") != "planned" or row.get("runs", []) for row in value["candidates"]):
        w.fail("design_must_be_frozen_before_measurements")
    return {"schema_version": 1, "scope": "experiment_design_lock", "design_sha256": w.plan_digest(design),
            "design": design, "notice": "Store before measurement; hashes detect drift relative to the retained lock, not chronology or authenticity."}


def check_design_lock(value, comparison):
    value = w.object_(value)
    design = design_definition(comparison)
    digest = w.plan_digest(design)
    if (value.get("schema_version") != 1 or value.get("scope") != "experiment_design_lock"
            or value.get("design") != design or value.get("design_sha256") != digest):
        w.fail("design_lock_mismatch")
    return digest


def compare(value, protocol_lock=None, design_lock=None):
    value = w.object_(value)
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        w.fail("invalid_comparison_schema")
    spec = protocol(value.get("protocol"))
    if protocol_lock is not None:
        check_lock(protocol_lock, spec)
    if "protocol_sha256" in value and value["protocol_sha256"] != w.plan_digest(spec):
        w.fail("protocol_digest_mismatch")
    design_digest = check_design_lock(design_lock, value) if design_lock is not None else None
    if "design_sha256" in value and (design_digest is None or value["design_sha256"] != design_digest):
        w.fail("design_digest_requires_matching_lock")
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
    median_frontier = [row for row in eligible if not any(dominance(other, row, spec["objectives"])
                                                          for other in eligible if other is not row)]
    all_pairs_frontier = [row for row in eligible if not any(
        paired_dominance(runs[other["id"]], runs[row["id"]], spec)
        for other in eligible if other is not row)]
    frontier = median_frontier if spec["decision_policy"] == "median" else all_pairs_frontier
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
            return tuple(preference_value(row["metrics"][metric]["median"], spec["objectives"][metric])
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
    if {row["id"] for row in median_frontier} != {row["id"] for row in all_pairs_frontier}:
        warnings.append("median_and_all_pairs_frontiers_differ")
    if protocol_lock is None:
        warnings.append("protocol_not_checked_against_independent_lock")
    return {"schema_version": 1, "scope": "conditional_measured_comparison", "notice": NOTICE,
            "protocol_id": spec["id"], "protocol_sha256": w.plan_digest(spec),
            "protocol_lock_checked": protocol_lock is not None, "design_lock_checked": design_lock is not None,
            "design_sha256": design_digest, "decision_policy": spec["decision_policy"],
            "replicates": len(spec["replicates"]),
            "objectives": spec["objectives"], "declared_priority": spec["priority"],
            "baseline": baseline["id"], "decision": decision, "selected_candidate": selected,
            "pareto_frontier": [row["id"] for row in frontier],
            "median_frontier": sorted(row["id"] for row in median_frontier),
            "all_pairs_frontier": sorted(row["id"] for row in all_pairs_frontier),
            "candidates": sorted(candidates, key=lambda row: row["id"]),
            "warnings": warnings, "review_required": True}


def main(argv=None):
    parser = core.SafeArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--comparison", type=Path)
    mode.add_argument("--freeze-protocol", type=Path, help="Input is a standalone experiment protocol JSON")
    mode.add_argument("--freeze-design", type=Path, help="Freeze a complete planned comparison, including candidate definitions and sources")
    parser.add_argument("--protocol-lock", type=Path, help="Independently retained lock from before measurements")
    parser.add_argument("--design-lock", type=Path, help="Independently retained design lock from before measurements")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.freeze_protocol or args.freeze_design:
            if args.protocol_lock or args.design_lock or not args.output:
                w.fail("freeze_requires_new_output_without_lock")
            result = (freeze_protocol(w.read_json(args.freeze_protocol)) if args.freeze_protocol
                      else freeze_design(w.read_json(args.freeze_design)))
        else:
            result = compare(w.read_json(args.comparison),
                             w.read_json(args.protocol_lock) if args.protocol_lock else None,
                             w.read_json(args.design_lock) if args.design_lock else None)
        w.write_json(result, args.output)
        return 0
    except (w.WorkflowError, OSError, ValueError, TypeError, RecursionError) as error:
        code = str(error) if isinstance(error, w.WorkflowError) else "invalid_input_or_file_operation"
        print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
