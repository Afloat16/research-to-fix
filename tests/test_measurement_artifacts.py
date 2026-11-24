"""Protocol-locked comparison artifacts bind each measured replicate."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import solution_compare as sc
import research_workflow as w
from test_solution_compare import fixture


class MeasurementArtifactTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.value = fixture()
        self.value["schema_version"] = 2
        self.lock = sc.protocol_lock(self.value["protocol"])
        digest = self.lock["protocol_sha256"]
        for row in self.value["candidates"]:
            row.update(variant_id=row["id"], protocol_sha256=digest,
                       support_ids=row["evidence_ids"], applicability="adapted",
                       license_status="not_copied")
            for run in row["runs"]:
                run.update(variant_id=row["id"], exit_code=0)
                path = f'{row["id"]}-{run["replicate"]}.json'
                data = json.dumps(sc.measurement_record(row["id"], digest, run)).encode()
                (self.root / path).write_bytes(data)
                run["measurement_artifact"] = {"path": path, "sha256": hashlib.sha256(data).hexdigest()}

    def test_verify_complete_and_reject_modified_report(self):
        report = sc.compare(self.value, self.lock, self.root)
        self.assertEqual(report["measurement_artifacts"]["files"], 9)
        self.assertTrue(report["measurement_artifacts"]["checked"])
        changed = copy.deepcopy(self.value)
        changed["candidates"][1]["runs"][0]["metrics"]["latency"] = 1
        with self.assertRaisesRegex(w.WorkflowError, "content_mismatch"):
            sc.compare(changed, self.lock, self.root)

    def test_digest_and_cross_replicate_swap(self):
        changed = copy.deepcopy(self.value)
        runs = changed["candidates"][1]["runs"]
        runs[0]["measurement_artifact"], runs[1]["measurement_artifact"] = (
            runs[1]["measurement_artifact"], runs[0]["measurement_artifact"])
        with self.assertRaisesRegex(w.WorkflowError, "content_mismatch"):
            sc.compare(changed, self.lock, self.root)
        name = self.value["candidates"][0]["runs"][0]["measurement_artifact"]["path"]
        (self.root / name).write_text("{}")
        with self.assertRaisesRegex(w.WorkflowError, "digest_mismatch"):
            sc.compare(self.value, self.lock, self.root)

    def test_path_and_missing_artifact(self):
        changed = copy.deepcopy(self.value)
        del changed["candidates"][0]["runs"][0]["measurement_artifact"]
        with self.assertRaisesRegex(w.WorkflowError, "artifact_required"):
            sc.compare(changed, self.lock, self.root)
        changed = copy.deepcopy(self.value)
        changed["candidates"][0]["runs"][0]["measurement_artifact"]["path"] = "../outside"
        with self.assertRaises(ValueError):
            sc.compare(changed, self.lock, self.root)


if __name__ == "__main__":
    unittest.main()
