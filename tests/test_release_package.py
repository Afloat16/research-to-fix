import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_release", ROOT / "tools" / "build_release.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class ReleaseTest(unittest.TestCase):
    def test_committed_reproducible_package_ignores_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            def git(*args):
                return subprocess.check_output(["git", "-C", str(repo), *args])
            git("init", "-q")
            git("config", "user.email", "tests@example.invalid")
            git("config", "user.name", "Release test")
            files = {"LICENSE": "test license", "VERSION": "1.2.3\n", "skills/research-to-fix/SKILL.md": "test skill"}
            for name in ("research_session", "research_workflow", "public_discovery", "solution_compare"):
                files["skills/research-to-fix/scripts/" + name + ".py"] = "pass\n"
            for name, data in files.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data, encoding="utf-8")
            git("add", ".")
            git("commit", "-qm", "fixture")
            commit = git("rev-parse", "HEAD").decode().strip()
            name, first = build.package(repo, commit)
            (repo / "skills/research-to-fix/SKILL.md").write_text("changed", encoding="utf-8")
            (repo / "skills/research-to-fix/scripts/private.py").write_text("untracked", encoding="utf-8")
            name2, second = build.package(repo, commit)
            self.assertEqual(name, "research-to-fix-v1.2.3-skill.zip")
            self.assertEqual(name, name2)
            self.assertEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest())
            with zipfile.ZipFile(io.BytesIO(first)) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read("research-to-fix/SKILL.md"), b"test skill")
                self.assertNotIn("research-to-fix/scripts/private.py", archive.namelist())
                self.assertEqual(archive.namelist(), sorted(archive.namelist()))
            with self.assertRaises(ValueError):
                build.package(repo, "HEAD")


if __name__ == "__main__":
    unittest.main()
