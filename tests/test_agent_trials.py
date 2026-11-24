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

    def test_protocol_tamper(self):
        lock = a.freeze(protocol())
        lock["protocol"]["max_tokens"] = 999
        with self.assertRaises(ValueError):
            a.validate_lock(lock)


if __name__ == "__main__":
    unittest.main()
