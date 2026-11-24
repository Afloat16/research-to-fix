import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
import agent_trials as a


def protocol():
    return {"schema_version": 1, "dataset": "fixture", "dataset_revision": "1" * 40,
            "split": "test", "evaluator_commit": "2" * 40, "scaffold_commit": "3" * 40,
            "skill_commit": "4" * 40, "model": "fixed", "model_revision": "fixed-revision",
            "environment": "same image", "network_policy": "same restricted tools",
            "generation_config": "temperature=0", "max_tokens": 1000, "max_tool_calls": 10,
            "max_seconds": 100, "seeds": [1, 2], "instances": [
                {"instance_id": "repo__a-1", "base_commit": "5" * 40, "repo": "repo/a"},
                {"instance_id": "repo__b-2", "base_commit": "6" * 40, "repo": "repo/b"}]}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def arm(root, lock, kind, resolved):
    p = lock["protocol"]
    write(root / "manifest.json", {"protocol_sha256": lock["protocol_sha256"], "arm": kind,
        "applied_skill_commit": p["skill_commit"] if kind == "skill" else None,
        "run_ids": {str(seed): f"{kind}-{seed}" for seed in p["seeds"]}})
    for seed in p["seeds"]:
        path = root / f"seed-{seed}"
        key = "repo__a-1"
        patch = "synthetic fixture diff"
        write(path / "predictions.json", [{"instance_id": key, "model_patch": patch, "model_name_or_path": kind}])
        write(path / "usage.json", {key: {"tokens": 100, "tool_calls": 2, "seconds": 3}})
        target = path / "reports" / key
        write(target / "report.json", {key: {"resolved": resolved}})
        (target / "patch.diff").write_bytes(patch.encode())


class AgentTrialTests(unittest.TestCase):
    def test_fixed_denominator_and_paired_cluster(self):
        lock = a.freeze(protocol())
        with tempfile.TemporaryDirectory() as temp:
            base, skill = Path(temp).resolve() / "baseline", Path(temp).resolve() / "skill"
            arm(base, lock, "baseline", False)
            arm(skill, lock, "skill", True)
            result = a.summarize(lock, base, skill)
            self.assertEqual(result["trials_per_arm"], 4)
            self.assertEqual(result["baseline"]["resolved_rate"], 0.)
            self.assertEqual(result["skill"]["resolved_rate"], .5)
            self.assertEqual(result["skill"]["statuses"]["not_submitted"], 2)
            self.assertEqual(result["paired_task_interval"]["mean_delta"], .5)

    def test_patch_mismatch_and_overbudget(self):
        lock = a.freeze(protocol())
        with tempfile.TemporaryDirectory() as temp:
            base, skill = Path(temp).resolve() / "baseline", Path(temp).resolve() / "skill"
            arm(base, lock, "baseline", False)
            arm(skill, lock, "skill", True)
            write(skill / "seed-1" / "usage.json", {"repo__a-1": {"tokens": 1001, "tool_calls": 2, "seconds": 3}})
            result = a.summarize(lock, base, skill)
            self.assertEqual(result["skill"]["resolved_rate"], .25)
            self.assertEqual(result["skill"]["statuses"]["budget_exceeded"], 1)
            (skill / "seed-1/reports/repo__a-1/patch.diff").write_text("wrong", encoding="utf-8")
            with self.assertRaises(ValueError):
                a.summarize(lock, base, skill)

    def test_independent_protocol_digest_and_orthogonal_outcomes(self):
        lock = a.freeze(protocol())
        changed = protocol()
        changed["max_tokens"] = 999
        rewritten = a.freeze(changed)
        # Self-consistency is insufficient when the entire lock is replaced.
        self.assertEqual(a.validate_lock(rewritten), rewritten["protocol"])
        with self.assertRaisesRegex(ValueError, "Independent protocol digest mismatch"):
            a.validate_lock(rewritten, lock["protocol_sha256"])
        with self.assertRaisesRegex(ValueError, "Independent protocol digest mismatch"):
            a.validate_lock(lock, "")
        with tempfile.TemporaryDirectory() as temp:
            base, skill = Path(temp).resolve() / "baseline", Path(temp).resolve() / "skill"
            arm(base, lock, "baseline", False)
            arm(skill, lock, "skill", True)
            # Seed 1: evaluator success over budget; absent patch with recorded cost.
            write(skill / "seed-1" / "usage.json", {
                "repo__a-1": {"tokens": 1001, "tool_calls": 2, "seconds": 3},
                "repo__b-2": {"tokens": 1001, "tool_calls": 0, "seconds": 1}})
            # Seed 2: evaluator success with missing usage; empty patch within budget.
            write(skill / "seed-2" / "predictions.json", [
                {"instance_id": "repo__a-1", "model_patch": "synthetic fixture diff", "model_name_or_path": "skill"},
                {"instance_id": "repo__b-2", "model_patch": "", "model_name_or_path": "skill"}])
            write(skill / "seed-2" / "usage.json", {
                "repo__b-2": {"tokens": 10, "tool_calls": 0, "seconds": 1}})
            result = a.summarize(lock, base, skill, expected_protocol_sha256=lock["protocol_sha256"])
            self.assertTrue(result["expected_protocol_digest_checked"])
            self.assertEqual(result["skill"]["resolved_rate"], 0.)
            self.assertEqual(result["skill"]["usage_coverage"], .75)
            self.assertEqual(result["skill"]["statuses"]["not_submitted"], 1)
            self.assertEqual(result["skill"]["statuses"]["empty_patch"], 1)
            self.assertEqual(result["skill"]["statuses"]["usage_missing"], 1)
            self.assertEqual(result["skill"]["statuses"]["budget_exceeded"], 1)
            self.assertEqual(result["skill"]["outcome_breakdown"], {
                "prediction_status": {"missing": 1, "empty": 1, "nonempty": 2},
                "evaluation_status": {"not_applicable": 2, "resolved": 2, "unresolved": 0,
                                      "evaluation_missing_or_error": 0},
                "budget_status": {"usage_missing": 1, "within_budget": 1, "budget_exceeded": 2}})
            for pair in result["pairs"]:
                self.assertFalse(pair["skill"]["resolved"])
            self.assertEqual(result["pairs"][-1]["skill"]["prediction_sha256"], a.sha256(b""))
            with self.assertRaisesRegex(ValueError, "Independent protocol digest mismatch"):
                a.summarize(rewritten, base, skill, expected_protocol_sha256=lock["protocol_sha256"])

    def test_consumed_artifacts_bind_usage_predictions_and_reports(self):
        import shutil
        lock = a.freeze(protocol())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            base, skill = root / "baseline", root / "skill"
            arm(base, lock, "baseline", False)
            arm(skill, lock, "skill", True)
            first = a.summarize(lock, base, skill)["consumed_artifacts"]
            self.assertEqual(first["arms"]["baseline"]["files"], 9)
            self.assertEqual(first["arms"]["skill"]["files"], 9)
            pin = first["sha256"]
            (skill / "ignored.txt").write_text("not consumed", encoding="utf-8")
            relocated = root / "relocated"
            shutil.copytree(skill, relocated)
            verified = a.summarize(lock, base, relocated, expected_artifacts_sha256=pin)["consumed_artifacts"]
            self.assertTrue(verified["expected_digest_checked"])
            self.assertEqual(verified["sha256"], pin)
            # Semantically identical JSON changes the exact consumed bytes.
            usage = relocated / "seed-1" / "usage.json"
            raw = usage.read_bytes()
            usage.write_bytes(raw + b" ")
            with self.assertRaisesRegex(ValueError, "Independent artifact digest mismatch"):
                a.summarize(lock, base, relocated, expected_artifacts_sha256=pin)
            usage.write_bytes(raw)
            # A structurally valid removed report must change the artifact set.
            (relocated / "seed-1/reports/repo__a-1/report.json").unlink()
            with self.assertRaisesRegex(ValueError, "Independent artifact digest mismatch"):
                a.summarize(lock, base, relocated, expected_artifacts_sha256=pin)

    def test_official_null_patch_preserves_denominator_and_budget(self):
        lock = a.freeze(protocol())
        with tempfile.TemporaryDirectory() as temp:
            base, skill = Path(temp).resolve() / "baseline", Path(temp).resolve() / "skill"
            arm(base, lock, "baseline", False)
            arm(skill, lock, "skill", True)
            for seed in (1, 2):
                write(skill / f"seed-{seed}/predictions.json", [
                    {"instance_id": "repo__a-1", "model_patch": None, "model_name_or_path": "skill"}])
            write(skill / "seed-2/usage.json", {})
            result = a.summarize(lock, base, skill)
            self.assertEqual(result["trials_per_arm"], 4)
            self.assertEqual(result["skill"]["resolved_rate"], 0.)
            self.assertEqual(result["skill"]["statuses"]["empty_patch"], 1)
            self.assertEqual(result["skill"]["statuses"]["usage_missing"], 1)
            self.assertEqual(result["skill"]["statuses"]["not_submitted"], 2)
            self.assertEqual(result["skill"]["outcome_breakdown"]["prediction_status"],
                             {"missing": 2, "empty": 2, "nonempty": 0})
            row = result["pairs"][0]["skill"]
            self.assertTrue(row["prediction_is_null"])
            self.assertNotIn("prediction_sha256", row)
            self.assertEqual(row["evaluation_status"], "not_applicable")
            # Missing key is malformed, not an explicit null prediction.
            write(skill / "seed-1/predictions.json", [
                {"instance_id": "repo__a-1", "model_name_or_path": "skill"}])
            with self.assertRaisesRegex(ValueError, "Unexpected prediction or patch"):
                a.summarize(lock, base, skill)

    def test_official_report_flag_consistency(self):
        lock = a.freeze(protocol())
        with tempfile.TemporaryDirectory() as temp:
            base, skill = Path(temp).resolve() / "baseline", Path(temp).resolve() / "skill"
            arm(base, lock, "baseline", False)
            arm(skill, lock, "skill", True)
            path = skill / "seed-1/reports/repo__a-1/report.json"
            flags = {"patch_is_None": False, "patch_exists": True,
                     "patch_successfully_applied": True, "infra_failure": False}
            write(path, {"repo__a-1": {"resolved": True, **flags}})
            result = a.summarize(lock, base, skill)
            self.assertEqual(result["skill"]["resolved_rate"], .5)
            self.assertEqual(result["pairs"][0]["skill"]["evaluation_flags"], flags)
            # Four contradictions and one wrong-type control. All would have
            # been accepted by the old resolved-boolean-only importer.
            for key, bad in (("patch_is_None", True), ("patch_exists", False),
                             ("patch_successfully_applied", False), ("infra_failure", True),
                             ("patch_exists", 1)):
                with self.subTest(key=key, bad=bad):
                    write(path, {"repo__a-1": {"resolved": True, **flags, key: bad}})
                    with self.assertRaisesRegex(ValueError, "official evaluation flag"):
                        a.summarize(lock, base, skill)
            # A failed infrastructure run is not a contradiction or a success.
            write(path, {"repo__a-1": {"resolved": False, **flags,
                                      "patch_successfully_applied": False, "infra_failure": True}})
            result = a.summarize(lock, base, skill)
            self.assertEqual(result["skill"]["resolved_rate"], .25)
            self.assertTrue(result["pairs"][0]["skill"]["evaluation_flags"]["infra_failure"])

    def test_protocol_tamper(self):
        lock = a.freeze(protocol())
        lock["protocol"]["max_tokens"] = 999
        with self.assertRaises(ValueError):
            a.validate_lock(lock)


if __name__ == "__main__":
    unittest.main()
