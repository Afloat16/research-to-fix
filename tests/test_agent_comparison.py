"""Synthetic importer tests only: no model or repair outcome experiment."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
import agent_comparison as c
from test_agent_trials import protocol, arm, write


def design():
    return {"schema_version": 2, "base_protocol": protocol(), "arms": [
        {"id": "baseline", "repository": None, "commit": None, "skill_path": None, "intervention_sha256": None},
        {"id": "skill", "repository": "Afloat16/research-to-fix", "commit": "4" * 40,
         "skill_path": "skills/research-to-fix", "intervention_sha256": "a" * 64},
        {"id": "competitor", "repository": "example/debugging", "commit": "7" * 40,
         "skill_path": "skills/debugging", "intervention_sha256": "b" * 64}]}


def fixture(root, lock, spec, resolved):
    name = spec["id"]
    shared = lock["protocol"]["base_protocol"]
    arm(root / name, {"protocol": shared, "protocol_sha256": lock["protocol_sha256"]}, name, resolved)
    path = root / name / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(applied_skill_commit=spec["commit"], intervention_sha256=spec["intervention_sha256"])
    write(path, manifest)


class ComparisonTests(unittest.TestCase):
    def test_frozen_multi_arm_denominator_and_cost_coverage(self):
        lock = c.freeze(design())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for spec in lock["protocol"]["arms"]:
                fixture(root, lock, spec, spec["id"] == "skill")
            result = c.summarize(lock, root, expected_protocol_sha256=lock["protocol_sha256"])
            self.assertTrue(result["expected_protocol_digest_checked"])
            self.assertEqual(result["arms"]["skill"]["outcome_breakdown"]["evaluation_status"]["resolved"], 2)
            self.assertEqual(result["arms"]["skill"]["outcome_breakdown"]["budget_status"]["usage_missing"], 2)
            changed = design()
            changed["base_protocol"]["max_seconds"] = 99
            with self.assertRaisesRegex(ValueError, "Independent protocol digest mismatch"):
                c.summarize(c.freeze(changed), root, expected_protocol_sha256=lock["protocol_sha256"])
            self.assertEqual(result["trials_per_arm"], 4)
            self.assertEqual(result["arms"]["skill"]["resolved_rate"], .5)
            self.assertEqual(result["arms"]["skill"]["usage_coverage"], .5)
            self.assertEqual(result["arms"]["competitor"]["statuses"]["not_submitted"], 2)
            self.assertEqual(result["skill_vs_predeclared_arms"]["competitor"]["mean_delta"], .5)
            self.assertEqual(set(result["skill_vs_predeclared_arms"]), {"baseline", "competitor"})
            path = root / "competitor" / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["run_ids"]["1"] = "skill-1"
            write(path, manifest)
            with self.assertRaises(ValueError):
                c.summarize(lock, root)

    def test_multi_arm_consumed_artifact_pin_detects_cost_edit(self):
        lock = c.freeze(design())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for spec in lock["protocol"]["arms"]:
                fixture(root, lock, spec, spec["id"] == "skill")
            result = c.summarize(lock, root)
            artifact = result["consumed_artifacts"]
            self.assertEqual(set(artifact["arms"]), {"baseline", "skill", "competitor"})
            self.assertTrue(c.summarize(lock, root, expected_artifacts_sha256=artifact["sha256"])
                            ["consumed_artifacts"]["expected_digest_checked"])
            path = root / "competitor/seed-1/usage.json"
            usage = json.loads(path.read_text(encoding="utf-8"))
            usage["repo__a-1"]["tokens"] += 1
            write(path, usage)
            self.assertEqual(c.summarize(lock, root)["arms"]["skill"]["resolved_rate"],
                             result["arms"]["skill"]["resolved_rate"])
            with self.assertRaisesRegex(ValueError, "Independent artifact digest mismatch"):
                c.summarize(lock, root, expected_artifacts_sha256=artifact["sha256"])

    def test_freeze_and_invalid_interventions(self):
        value = design()
        self.assertEqual(c.freeze(value), c.freeze({**value, "arms": value["arms"][::-1]}))
        for key, bad in (("skill_path", "../secret"), ("intervention_sha256", "a" * 64),
                         ("commit", "short"), ("id", "baseline")):
            mutated = design()
            mutated["arms"][-1][key] = bad
            with self.assertRaises(ValueError):
                c.freeze(mutated)
        lock = c.freeze(value)
        lock["protocol"]["arms"][1]["commit"] = "9" * 40
        with self.assertRaises(ValueError):
            c.validate_lock(lock)

    def test_exact_sign_and_holm(self):
        self.assertEqual(c.sign_p(0, 0), 1.)
        self.assertEqual(c.sign_p(5, 0), .0625)
        self.assertEqual(c.sign_p(0, 5), .0625)
        self.assertEqual(c.sign_p(3, 3), 1.)
        self.assertAlmostEqual(c.holm({"a": .01, "b": .04, "c": .03})["a"], .03)
        self.assertAlmostEqual(c.holm({"a": .01, "b": .04, "c": .03})["b"], .06)
        self.assertAlmostEqual(c.holm({"a": .01, "b": .04, "c": .03})["c"], .06)


if __name__ == "__main__":
    unittest.main()
