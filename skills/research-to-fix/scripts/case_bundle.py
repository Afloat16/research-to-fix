#!/usr/bin/env python3
"""Seal and verify explicit local repair evidence without executing it."""
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

from research_case import (SafeArgumentParser, VALIDATE_MAX_FILE_BYTES,
                           _read_regular_file, decode_case_bytes, validate_case)

MANIFEST = "manifest.json"
CASE = "case.json"
MAX_FILES = 128
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 128 * 1024
NOTICE = ("Integrity only: hashes detect changes relative to a manifest. "
          "They do not authenticate the author, prove the recorded experiment, "
          "or establish causality. Review and redact before sharing.")


class BundleError(ValueError):
    """Fixed diagnostic code; never includes user paths or record contents."""

    def __init__(self, code, exit_code=2):
        super().__init__(code)
        self.exit_code = exit_code


def digest(data):
    return hashlib.sha256(data).hexdigest()


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def portable_path(value):
    # Strict portable relative POSIX paths: no traversal, drives, aliases,
    # control characters, Windows devices or ambiguous trailing dots.
    if not isinstance(value, str) or not 1 <= len(value) <= 240:
        raise BundleError("invalid_path")
    parts = value.split("/")
    for part in parts:
        if (not re.fullmatch(r"[A-Za-z0-9._-]+", part) or part in (".", "..")
                or part.endswith(".") or
                re.fullmatch(r"CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9]", part.split(".")[0], re.I)):
            raise BundleError("invalid_path")
    if value.casefold() == MANIFEST:
        raise BundleError("manifest_self_reference")
    return value


def checked_root(directory):
    root = Path(directory)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise BundleError("invalid_directory")
    return root


def read_member(root, name, maximum):
    # The caller must control the directory while sealing/verifying. This
    # preflight is not a sandbox against concurrent hostile tree replacement.
    path = root
    parts = name.split("/")
    for part in parts[:-1]:
        path = path / part
        if not stat.S_ISDIR(path.lstat().st_mode):
            raise BundleError("non_regular_member")
    path = path / parts[-1]
    data, issue = _read_regular_file(path, maximum)
    if issue:
        raise BundleError(issue)
    return data


def read_record(raw):
    case, _ = decode_case_bytes(raw)
    if validate_case(case):
        raise BundleError("invalid_record", 1)
    return case


def declared_artifacts(case):
    """Recognize the optional run artifacts mapping used by the recorder."""
    paths = set()
    for run in case["validation"]["runs"]:
        if "artifacts" not in run:
            continue
        refs = run["artifacts"]
        if not isinstance(refs, dict):
            raise BundleError("invalid_artifact_references", 1)
        for path in refs.values():
            paths.add(portable_path(path))
            if len(paths) >= MAX_FILES:
                raise BundleError("file_limit")
    return paths


def checked_paths(paths):
    names = set()
    folded = set()
    for value in paths:
        name = portable_path(value)
        if name in names or name.casefold() in folded:
            raise BundleError("duplicate_path")
        names.add(name)
        folded.add(name.casefold())
        if len(names) > MAX_FILES:
            raise BundleError("file_limit")
    if CASE not in names:
        raise BundleError("missing_case")
    return sorted(names)


def file_rows(root, names, case_raw):
    rows = []
    total = 0
    for name in names:
        maximum = min(MAX_FILE_BYTES, MAX_TOTAL_BYTES - total)
        data = case_raw if name == CASE else read_member(root, name, maximum)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise BundleError("total_limit")
        rows.append({"path": name, "bytes": len(data), "sha256": digest(data)})
    return rows


def manifest_bytes(rows):
    return (json.dumps({"schema_version": 1, "algorithm": "sha256", "files": rows},
                       ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("utf-8")


def report(operation, rows, raw_manifest, pinned=False):
    return {"operation": operation, "ok": True, "scope": "local_bundle_integrity",
            "files": len(rows), "artifacts": len(rows) - 1,
            "bytes": sum(row["bytes"] for row in rows),
            "manifest_sha256": digest(raw_manifest), "expected_digest_checked": pinned,
            "record_consistency": True, "notice": NOTICE}


def seal(directory, artifacts=()):
    root = checked_root(directory)
    raw = read_member(root, CASE, VALIDATE_MAX_FILE_BYTES)
    case = read_record(raw)
    explicit = list(artifacts)
    # Reject repeated explicit options instead of silently hiding mistakes.
    checked_paths([CASE, *explicit])
    names = checked_paths({CASE, *explicit, *declared_artifacts(case)})
    rows = file_rows(root, names, raw)
    manifest = manifest_bytes(rows)
    with (root / MANIFEST).open("xb") as handle:
        handle.write(manifest)
    return report("seal", rows, manifest)


def verify(directory, expected_digest=None):
    if expected_digest is not None and not valid_digest(expected_digest):
        raise BundleError("invalid_expected_digest")
    root = checked_root(directory)
    manifest = read_member(root, MANIFEST, MAX_MANIFEST_BYTES)
    if expected_digest is not None and digest(manifest) != expected_digest:
        raise BundleError("manifest_digest_mismatch", 1)
    value, _ = decode_case_bytes(manifest)
    if (not isinstance(value, dict) or set(value) != {"schema_version", "algorithm", "files"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["algorithm"] != "sha256" or not isinstance(value["files"], list)
            or len(value["files"]) > MAX_FILES):
        raise BundleError("invalid_manifest")
    rows = value["files"]
    if any(not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}
           or type(row["bytes"]) is not int or not 0 <= row["bytes"] <= MAX_FILE_BYTES
           or not valid_digest(row["sha256"]) for row in rows):
        raise BundleError("invalid_manifest")
    names = checked_paths(row["path"] for row in rows)
    if names != [row["path"] for row in rows] or sum(row["bytes"] for row in rows) > MAX_TOTAL_BYTES:
        raise BundleError("invalid_manifest")
    try:
        raw = read_member(root, CASE, VALIDATE_MAX_FILE_BYTES)
        actual = file_rows(root, names, raw)
    except (OSError, BundleError):
        raise BundleError("missing_or_unreadable_member", 1) from None
    if actual != rows:
        raise BundleError("member_digest_mismatch", 1)
    case = read_record(raw)
    if not declared_artifacts(case).issubset(names):
        raise BundleError("unsealed_artifact", 1)
    return report("verify", rows, manifest, expected_digest is not None)


def main(argv=None):
    parser = SafeArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True, parser_class=SafeArgumentParser)
    create = sub.add_parser("seal", help="Create a manifest; never overwrite")
    create.add_argument("--directory", required=True, type=Path)
    create.add_argument("--artifact", action="append", default=[],
                        help="Additional relative file path; repeat as needed")
    check = sub.add_parser("verify", help="Check manifest, members and case structure")
    check.add_argument("--directory", required=True, type=Path)
    check.add_argument("--expected-manifest-sha256", help="Optional independently retained lowercase SHA-256")
    args = parser.parse_args(argv)
    try:
        if args.operation == "seal":
            result = seal(args.directory, args.artifact)
        else:
            result = verify(args.directory, args.expected_manifest_sha256)
        status = 0
    except BundleError as error:
        status = error.exit_code
        result = {"ok": False, "error": str(error)}
    except FileExistsError:
        status, result = 2, {"ok": False, "error": "manifest_exists"}
    except OSError:
        status, result = 2, {"ok": False, "error": "file_operation"}
    except (ValueError, RecursionError):
        status, result = 2, {"ok": False, "error": "invalid_json"}
    result.update({"operation": args.operation, "scope": "local_bundle_integrity", "notice": NOTICE})
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return status


if __name__ == "__main__":
    sys.exit(main())
