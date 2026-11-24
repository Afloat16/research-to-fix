"""Regression coverage for strict, bounded, offline case input."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "research-to-fix" / "scripts" / "research_case.py"
sys.path.insert(0, str(SCRIPT.parent))
import research_case as rc


class InputHardeningTests(unittest.TestCase):
    def invoke(self, path):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", str(path), "--format", "json"],
            capture_output=True, text=True, timeout=5, encoding="utf-8")
        return result.returncode, json.loads(result.stdout)

    def test_strict_json_consistent_between_validate_and_recall(self):
        for raw in (b'{"extra": 1e999}', b'{"extra": "\\ud800"}',
                    b'{"extra": 0, "extra": 1}', b'\xff'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    rc.decode_case_bytes(raw)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "case.json"
                    path.write_bytes(raw)
                    code, report = self.invoke(path)
                    self.assertEqual(code, 2)
                    self.assertTrue(report["input_error"])

    def test_ordinary_case_still_validates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            path.write_text(json.dumps(rc.new_case()), encoding="utf-8")
            self.assertEqual(self.invoke(path)[0], 0)

    def test_size_and_directory_rejected_without_echoing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private_marker.json"
            with path.open("wb") as handle:
                handle.truncate(rc.VALIDATE_MAX_FILE_BYTES + 1)
            for candidate in (path, Path(directory)):
                code, report = self.invoke(candidate)
                self.assertEqual(code, 2)
                self.assertTrue(report["input_error"])
                self.assertNotIn(str(candidate), json.dumps(report))

    def test_symlink_and_fifo_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "case.json"
            target.write_text(json.dumps(rc.new_case()), encoding="utf-8")
            link = root / "link.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                pass
            else:
                self.assertEqual(self.invoke(link)[0], 2)
            if hasattr(os, "mkfifo"):
                fifo = root / "fifo.json"
                os.mkfifo(fifo)
                self.assertEqual(self.invoke(fifo)[0], 2)

    def test_multicast_and_encoded_credential_markers(self):
        for url in ("https://224.0.0.1/docs", "https://[ff02::1]/docs",
                    "https://example.org/%67hp_123456789012345678901234567890",
                    "https://example.org/docs?value=%73k-abcdefghijklmnopqrst",
                    "https://example.org/path/password%3Dsynthetic"):
            with self.subTest(url=url):
                self.assertFalse(rc.public_url(url))
        for url in ("https://example.org/docs?version=2", "https://github.com/owner/repo"):
            self.assertTrue(rc.public_url(url))


if __name__ == "__main__":
    unittest.main()
