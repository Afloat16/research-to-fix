#!/usr/bin/env python3
"""Compare locally measured alternative repairs under a fixed experiment protocol."""
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path

import case_bundle as bundle
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
MAX_MEASUREMENT_BYTES = 64 * 1024
MAX_MEASUREMENT_TOTAL = 32 * 1024 * 1024
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


def command_text(value):
    # Internal spaces (including quoted strings) may change command
    # semantics. Do not collapse them when checking comparison equality.
    if not isinstance(value, str) or not value.strip() or len(value) > 1000 or w.CONTROL.search(value):
        w.fail("invalid_command")
    return value


def protocol(value):
    value = w.object_(value)
    ctx = context(value.get("context"))
    command = command_text(value.get("command"))
    replicate_ids = unique_ids(value.get("replicates"), MAX_REPLICATES, 1)
    minimum = w.integer(value.get("minimum_replicates", 1), 1, MAX_REPLICATES)
    if len(replicate_ids) < minimum:
        w.fail("too_few_declared_replicates")
    mode = value.get("dominance_mode", "median")
    if mode not in ("median", "paired_conservative"):
        w.fail("invalid_dominance_mode")
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
        margin = finite(row.get("minimum_improvement", 0))
        if margin < 0:
            w.fail("negative_practical_margin")
        item["minimum_improvement"] = margin
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
            "replicates": replicate_ids, "objectives": objectives, "checks": checks, "priority": priorities,
            "minimum_replicates": minimum, "dominance_mode": mode}


def protocol_lock(value):
    normalized = protocol(value)
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=True,
                                       separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()
    return {"schema_version": 1, "scope": "experiment_protocol_lock",
            "protocol_sha256": digest, "protocol": normalized,
            "notice": "Retain this digest independently before experiments; the hash is not proof of timing or authorship."}


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
                         "limitations": w.text(row.get("limitations"), 500),
                         "revision": w.text(row.get("revision", ""), 100, False),
                         "retraction_hint": "retracted" if row.get("retraction_hint") == "retracted" else ""}
    return evidence


def measure_summary(values):
    return {"median": statistics.median(values), "min": min(values), "max": max(values),
            "n": len(values)}


def candidate(row, spec, evidence, version=1, digest=None):
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
    support = []
    if version == 2:
        support = unique_ids(row.get("support_ids", []), 20)
        if not set(support).issubset(refs):
            w.fail("support_not_in_evidence")
        if basis in ("external", "mixed"):
            if not support or any(evidence[ref]["access"] != "read" for ref in support):
                reasons.append("supporting_originals_not_read")
            if any(evidence[ref]["retraction_hint"] for ref in support):
                reasons.append("supporting_source_retracted")
            if row.get("applicability") not in ("matched", "adapted"):
                reasons.append("applicability_not_verified")
            w.text(row.get("applicability_note", ""), 600, False)
            license_state = row.get("license_status")
            if license_state not in ("compatible", "not_copied"):
                reasons.append("license_not_cleared")
            w.text(row.get("license_note", ""), 400, False)
        variant = identifier(row.get("variant_id"))
        if row.get("protocol_sha256") != digest:
            reasons.append("protocol_digest_mismatch")
    else:
        variant = None
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
        command = command_text(run.get("command"))
        w.text(run.get("observed"), 800)
        if version == 2 and run.get("variant_id") != variant:
            if "variant_mismatch" not in reasons:
                reasons.append("variant_mismatch")
        if "exit_code" in run:
            code = run["exit_code"]
            if type(code) is not int or not -255 <= code <= 65535:
                w.fail("invalid_exit_code")
            if code != 0 and "nonzero_exit_code" not in reasons:
                reasons.append("nonzero_exit_code")
        if command != spec["command"]:
            same_protocol = False
            if "comparison_context_mismatch" not in reasons:
                reasons.append("comparison_context_mismatch")
        observed[rep] = {"metrics": normalized, "checks": checks}
    if state != "measured" and observed:
        w.fail("unmeasured_candidate_has_runs")
    complete = (state == "measured" and set(observed) == set(spec["replicates"]) and same_protocol
                and "variant_mismatch" not in reasons and "protocol_digest_mismatch" not in reasons)
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
            "evidence_ids": refs, "support_ids": support, "variant_id": variant,
            "comparable": complete, "eligible": complete and not reasons,
            "reasons": reasons, "replicates_observed": len(observed), "metrics": summaries,
            "failed_checks": failures, "threshold_failures": thresholds}, observed


def improvement(left, right, objective):
    return left - right if objective["direction"] == "max" else right - left


def dominance(a, b, objectives, a_runs=None, b_runs=None, mode="median"):
    """Acyclic median Pareto dominance with meaningful improvement.

    A dominates B only when no median is worse and at least one median
    improves beyond its declared absolute practical margin. Conservative
    mode additionally rejects a meaningful degradation in any matched
    replicate. No significance test is implied.
    """
    changes = {key: improvement(a["metrics"][key]["median"], b["metrics"][key]["median"], obj)
               for key, obj in objectives.items()}
    if not all(value >= 0 for value in changes.values()) or not any(
            value > objectives[key].get("minimum_improvement", 0) for key, value in changes.items()):
        return False
    if mode == "paired_conservative":
        for rep in a_runs:
            for key, objective in objectives.items():
                if improvement(a_runs[rep]["metrics"][key], b_runs[rep]["metrics"][key],
                               objective) < -objective["minimum_improvement"]:
                    return False
    return True


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
                       "practical_improved_pairs": sum(value > obj["minimum_improvement"] for value in differences),
                       "practical_worse_pairs": sum(value < -obj["minimum_improvement"] for value in differences),
                       "positive_is_improvement": True}
    return result


def measurement_record(candidate_id, protocol_sha256, run):
    """Canonical, independent structured measurement file for one replicate.

    This binds values to a local file; it does not authenticate who produced
    that file or establish that a command was really executed.
    """
    return {"schema_version": 1, "candidate_id": identifier(candidate_id),
            "protocol_sha256": protocol_sha256, "variant_id": identifier(run.get("variant_id")),
            "replicate": identifier(run.get("replicate")), "command": command_text(run.get("command")),
            "exit_code": run.get("exit_code"), "metrics": w.object_(run.get("metrics")),
            "checks": w.object_(run.get("checks")), "observed": w.text(run.get("observed"), 800)}


def verify_measurements(value, directory, protocol_sha256):
    root = bundle.checked_root(directory)
    seen, total = set(), 0
    for candidate_row in rows(value.get("candidates"), MAX_CANDIDATES, 2):
        key = identifier(candidate_row.get("id"))
        for run in rows(candidate_row.get("runs", []), MAX_REPLICATES):
            artifact = run.get("measurement_artifact")
            if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256"}:
                w.fail("measurement_artifact_required")
            name = bundle.portable_path(artifact["path"])
            fingerprint = artifact["sha256"]
            if name.casefold() in seen or not bundle.valid_digest(fingerprint):
                w.fail("invalid_measurement_artifact")
            seen.add(name.casefold())
            raw = bundle.read_member(root, name, MAX_MEASUREMENT_BYTES)
            total += len(raw)
            if total > MAX_MEASUREMENT_TOTAL:
                w.fail("measurement_artifact_limit")
            if hashlib.sha256(raw).hexdigest() != fingerprint:
                w.fail("measurement_artifact_digest_mismatch")
            actual, _ = core.decode_case_bytes(raw)
            expected = measurement_record(key, protocol_sha256, run)
            if type(expected["exit_code"]) is not int:
                w.fail("measurement_exit_code_required")
            # Canonical serialization avoids Python bool/int equality and
            # preserves the declared metrics and exact command semantics.
            encode = lambda obj: json.dumps(obj, sort_keys=True, ensure_ascii=True,
                                           separators=(",", ":"), allow_nan=False)
            if encode(actual) != encode(expected):
                w.fail("measurement_artifact_content_mismatch")
    return {"checked": True, "files": len(seen), "bytes": total,
            "scope": "local file digest and structured value consistency, not proof of execution"}


def compare(value, lock=None, artifact_root=None):
    value = w.object_(value)
    version = value.get("schema_version")
    if type(version) is not int or version not in (1, 2):
        w.fail("invalid_comparison_schema")
    computed_lock = protocol_lock(value.get("protocol"))
    spec = computed_lock["protocol"]
    digest = computed_lock["protocol_sha256"]
    if lock is not None and (not isinstance(lock, dict) or lock != computed_lock):
        w.fail("protocol_lock_mismatch")
    if version == 2 and lock is None:
        w.fail("protocol_lock_required")
    if artifact_root is not None and version != 2:
        w.fail("measurement_artifacts_require_v2")
    measurement_status = (verify_measurements(value, artifact_root, digest) if artifact_root is not None
                          else {"checked": False, "files": 0})
    evidence = evidence_records(value.get("evidence", []))
    candidates, runs = [], {}
    for row in rows(value.get("candidates"), MAX_CANDIDATES, 2):
        result, observations = candidate(row, spec, evidence, version, digest)
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
    frontier = [row for row in eligible if not any(
        dominance(other, row, spec["objectives"], runs[other["id"]], runs[row["id"]], spec["dominance_mode"])
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
        # At each declared priority, keep every candidate within the
        # practical margin of the best remaining median. Do not manufacture
        # a winner from sub-margin measurement noise.
        remaining = frontier[:]
        for metric in spec["priority"]:
            objective = spec["objectives"][metric]
            vals = [row["metrics"][metric]["median"] for row in remaining]
            best = min(vals) if objective["direction"] == "min" else max(vals)
            remaining = [row for row in remaining if improvement(best,
                         row["metrics"][metric]["median"], objective) <= objective["minimum_improvement"]]
            if len(remaining) == 1:
                selected = remaining[0]["id"]
                decision = "declared_lexicographic_preference"
                break
    if selected == baseline["id"]:
        decision, selected = "baseline_preferred", None
    warnings = []
    if len(spec["replicates"]) < 3:
        warnings.append("fewer_than_three_replicates_descriptive_only")
    if not any(row["kind"] == "regression" for row in spec["checks"].values()):
        warnings.append("no_explicit_regression_check")
    if any(row["state"] != "measured" for row in candidates):
        warnings.append("unmeasured_options_remain")
    if lock is None:
        warnings.append("no_independent_protocol_lock_checked")
    if artifact_root is None:
        warnings.append("measurement_artifacts_not_checked")
    return {"schema_version": 1, "scope": "conditional_measured_comparison", "notice": NOTICE,
            "protocol_id": spec["id"], "protocol_sha256": digest, "protocol_lock_checked": lock is not None,
            "dominance_mode": spec["dominance_mode"], "replicates": len(spec["replicates"]),
            "measurement_artifacts": measurement_status,
            "objectives": spec["objectives"], "declared_priority": spec["priority"],
            "baseline": baseline["id"], "decision": decision, "selected_candidate": selected,
            "pareto_frontier": [row["id"] for row in frontier],
            "candidates": sorted(candidates, key=lambda row: row["id"]),
            "warnings": warnings, "review_required": True}


def main(argv=None):
    parser = core.SafeArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--comparison", type=Path)
    operation.add_argument("--freeze-protocol", type=Path, help="Freeze the declared protocol before measurement")
    parser.add_argument("--protocol-lock", type=Path, help="Independently retained protocol lock (required for schema v2)")
    parser.add_argument("--artifact-root", type=Path, help="Verify every v2 replicate measurement JSON against its declared SHA-256 and values")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.freeze_protocol:
            if args.protocol_lock or args.artifact_root:
                w.fail("unexpected_protocol_lock_or_artifacts")
            result = protocol_lock(w.read_json(args.freeze_protocol))
        else:
            result = compare(w.read_json(args.comparison),
                             w.read_json(args.protocol_lock) if args.protocol_lock else None, args.artifact_root)
        w.write_json(result, args.output)
        return 0
    except (w.WorkflowError, OSError, ValueError, TypeError, RecursionError) as error:
        code = str(error) if isinstance(error, w.WorkflowError) else "invalid_input_or_file_operation"
        print(json.dumps({"ok": False, "error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
