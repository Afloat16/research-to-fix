"""Evidence bundle invariants; use synthetic local files only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "research-to-fix" / "scripts" / "case_bundle.py"
sys.path.insert(0, str(SCRIPT.parent))
import case_bundle as bundle
import research_case as rc


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = rc.new_case()
        self.write_case()
        (self.root / "runs").mkdir()
        (self.root / "runs" / "test.log").write_bytes(b"original output\n")

    def write_case(self):
        (self.root / "case.json").write_text(json.dumps(self.case), encoding="utf-8")

    def invoke(self, operation, *options):
        result = subprocess.run([sys.executable, str(SCRIPT), operation,
                                 "--directory", str(self.root), *options],
                                capture_output=True, text=True, timeout=5, encoding="utf-8")
        return result.returncode, json.loads(result.stdout)

    def add_declared_artifact(self, path="runs/test.log"):
        self.case["validation"]["runs"] = [{
            "id": "V1", "check_id": "test", "phase": "before", "kind": "test",
            "result": "not_run", "command": "", "observed": "", "exit_code": None,
            "evidence_ids": [], "artifacts": {"output": path}}]
        self.write_case()

    def test_seal_verify_and_pin(self):
        self.add_declared_artifact()
        code, report = self.invoke("seal")
        self.assertEqual(code, 0, report)
        self.assertEqual(report["artifacts"], 1)
        manifest = (self.root / "manifest.json").read_bytes()
        self.assertEqual(report["manifest_sha256"], hashlib.sha256(manifest).hexdigest())
        code, checked = self.invoke("verify", "--expected-manifest-sha256", report["manifest_sha256"])
        self.assertEqual(code, 0, checked)
        self.assertTrue(checked["expected_digest_checked"])
        self.assertTrue(checked["record_consistency"])
        self.assertEqual(self.invoke("verify", "--expected-manifest-sha256", "0" * 64)[0], 1)

    def test_deterministic_seal_and_no_overwrite(self):
        (self.root / "a.txt").write_bytes(b"a")
        paths = ["runs/test.log", "a.txt"]
        first = bundle.seal(self.root, paths)
        original = (self.root / "manifest.json").read_bytes()
        self.assertEqual(self.invoke("seal")[0], 2)
        self.assertEqual((self.root / "manifest.json").read_bytes(), original)
        (self.root / "manifest.json").unlink()
        second = bundle.seal(self.root, reversed(paths))
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])

    def test_tampered_or_missing_member_fails(self):
        self.add_declared_artifact()
        self.assertEqual(self.invoke("seal")[0], 0)
        path = self.root / "runs" / "test.log"
        path.write_bytes(b"changed output\n")
        self.assertEqual(self.invoke("verify")[0], 1)
        path.unlink()
        self.assertEqual(self.invoke("verify")[0], 1)

    def test_changed_case_and_invalid_case_fail(self):
        self.assertEqual(self.invoke("seal")[0], 0)
        self.case["case_id"] = "changed"
        self.write_case()
        self.assertEqual(self.invoke("verify")[0], 1)
        (self.root / "manifest.json").unlink()
        self.case["schema_version"] = 999
        self.write_case()
        self.assertEqual(self.invoke("seal")[0], 1)

    def test_unlisted_declared_reference_rejected_even_with_matching_case_hash(self):
        self.add_declared_artifact()
        bundle.seal(self.root)
        path = self.root / "manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["files"] = [row for row in manifest["files"] if row["path"] == "case.json"]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        code, report = self.invoke("verify")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"], "unsealed_artifact")

    def test_rejects_traversal_and_manifest_self_reference(self):
        for name in ("../private.txt", "/etc/passwd", r"C:\private.txt", "runs//test.log",
                     "runs/./test.log", "manifest.json", "runs/NUL.txt"):
            with self.subTest(name=name):
                code, report = self.invoke("seal", "--artifact", name)
                self.assertEqual(code, 2)
                self.assertNotIn(name, json.dumps(report))
                self.assertFalse((self.root / "manifest.json").exists())
        self.add_declared_artifact("../private.txt")
        self.assertEqual(self.invoke("seal")[0], 2)

    def test_rejects_symlink_files_and_directories(self):
        try:
            (self.root / "link.log").symlink_to(self.root / "runs" / "test.log")
            (self.root / "alias").symlink_to(self.root / "runs", target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest("Symlinks unavailable")
        for name in ("link.log", "alias/test.log"):
            self.assertEqual(self.invoke("seal", "--artifact", name)[0], 2)

    def test_invalid_manifest_and_casefold_aliases(self):
        with self.assertRaises(bundle.BundleError):
            bundle.checked_paths(["case.json", "A.txt", "a.txt"])
        bundle.seal(self.root)
        path = self.root / "manifest.json"
        data = json.loads(path.read_bytes())
        data["files"][0]["path"] = "../outside"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.invoke("verify")[0], 2)

    def test_size_budget_and_no_implicit_collection(self):
        large = self.root / "large.bin"
        with large.open("wb") as handle:
            handle.truncate(bundle.MAX_FILE_BYTES + 1)
        self.assertEqual(self.invoke("seal", "--artifact", "large.bin")[0], 2)
        result = bundle.seal(self.root)
        self.assertEqual(result["files"], 1)
        self.assertEqual(bundle.verify(self.root)["files"], 1)


if __name__ == "__main__":
    unittest.main()
