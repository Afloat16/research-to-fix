#!/usr/bin/env python3
"""Build an installable skill archive from committed source, not the worktree."""
import argparse
import hashlib
import io
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

PREFIX = "skills/research-to-fix/"
MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def package(repo, commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A full commit SHA is required")
    if git(repo, "cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("Expected a commit")
    version = git(repo, "show", commit + ":VERSION").decode("ascii").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Invalid release version")
    raw = git(repo, "ls-tree", "-r", "-z", "--full-tree", commit, "--",
              PREFIX, "LICENSE", "VERSION")
    files = {}
    total = 0
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, encoded = entry.split(b"\t", 1)
        mode, kind, blob = meta.decode("ascii").split()
        path = encoded.decode("utf-8")
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ValueError("Nonregular release entry")
        if path.startswith(PREFIX):
            relative = path[len(PREFIX):]
        elif path in ("LICENSE", "VERSION"):
            relative = path
        else:
            raise ValueError("Unexpected release entry")
        parts = PurePosixPath(relative).parts
        if not parts or any(part in (".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
            raise ValueError("Unsafe archive path")
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            raise ValueError("Unexpected hidden or cached release file")
        if path.startswith(PREFIX) and not (relative == "SKILL.md" or parts[0] in ("agents", "references", "scripts")):
            raise ValueError("Unexpected skill entry")
        name = "research-to-fix/" + relative
        if name.casefold() in {key.casefold() for key in files}:
            raise ValueError("Duplicate archive path")
        size = int(git(repo, "cat-file", "-s", blob))
        total += size
        if size > MAX_FILE or total > MAX_TOTAL:
            raise ValueError("Release exceeds size limits")
        data = git(repo, "cat-file", "blob", blob)
        if len(data) != size:
            raise ValueError("Blob size changed")
        files[name] = (data, mode)
    for path in ("SKILL.md", "LICENSE", "VERSION", "scripts/research_session.py",
                 "scripts/research_workflow.py", "scripts/public_discovery.py", "scripts/solution_compare.py"):
        if "research-to-fix/" + path not in files:
            raise ValueError("Missing required release entry: " + path)
    stream = io.BytesIO()
    # Stored ZIP, fixed ordering/timestamp/Unix metadata: bytes depend only on
    # committed file bytes and executable bits, not the current platform/time.
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, (data, mode) in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = int(mode, 8) << 16
            archive.writestr(info, data)
    return "research-to-fix-v" + version + "-skill.zip", stream.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    name, data = package(args.repo, args.commit)
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / name).open("xb") as handle:
        handle.write(data)
    digest = hashlib.sha256(data).hexdigest()
    with (args.output / (name + ".sha256")).open("x", encoding="ascii", newline="\n") as handle:
        handle.write(digest + "  " + name + "\n")
    print(digest + "  " + name)


if __name__ == "__main__":
    main()
