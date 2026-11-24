# Trusted local before/after unittest capture

The generic recorder turns an explicit, approved local test suite into a frozen, sealed before/after case. It does not invent research evidence or automatically execute commands from case records. It is deliberately limited to trusted stdlib Python projects. Never run untrusted candidate/test code with this tool. Fresh temporary directories, a stripped environment, `-I -S -B -X utf8` and no shell reduce accidental coupling but **are not a sandbox**: Python code can access the host filesystem/network, launch processes, and alter its own test behavior. Use a separately isolated environment for untrusted code. Source snapshots and logs may contain sensitive data; the tool does not redact them.

## 1. Explicit prospective design

Prepare three operator-controlled directories: before and after contain the selected implementation files at the same relative paths; tests contains the unchanged test/fixture files. No directory scans, git operations, downloads, package installation, credentials or arbitrary commands. List every imported local implementation/test/fixture file explicitly. This example assumes a real test module and original test ID; substitute your actual files and fully qualified method IDs.

```json
{
  "schema_version": 1,
  "case_id": "division-capture",
  "summary": "Division zero exception contract",
  "component": "calculation",
  "hypothesis": "Check denominator without changing signed nonzero division.",
  "implementation_files": ["calculation.py"],
  "comparison_files": ["test_calculation.py"],
  "test_modules": ["test_calculation"],
  "original_test_ids": ["test_calculation.CalculationTests.test_zero"],
  "timeout_seconds": 30
}
```

```bash
python skills/research-to-fix/scripts/unittest_capture.py freeze --spec spec.json \
  --before ./baseline --after ./candidate --tests ./tests --output plan.json
```

Freeze reads bytes only and binds the exact implementation/test/runner hashes, Python version/implementation, declared original IDs and timeout. It refuses existing output. Retain the printed plan SHA-256 independently. It binds content, not when the lock was created. Changes require a new plan, not an edited result.

## 2. Execute only after explicit approval

```bash
python skills/research-to-fix/scripts/unittest_capture.py record --plan plan.json \
  --before ./baseline --after ./candidate --tests ./tests --output ./captured-case \
  --expected-plan-sha256 HASH --approve-local-execution
```

The output directory must not exist. Before execution the recorder re-reads all selected files, compares exact hashes/plan and Python labels, and copies these same in-memory bytes into independent temporary workspaces and preserved snapshots. Runs the same explicit test modules without shell, with the same frozen comparison bytes. Only complete method-level reports are accepted; unsupported/incomplete reports, excessive output or timeouts leave partial artifacts and return an error. The parent terminates the direct process at its bounds; this is not containment of descendants or a hard disk quota. No third-party site packages are included. unittest expected-failure/unexpected-success semantics and class/module setup failures with incomplete outcomes are not supported.

A solved declaration requires a real fail/error on at least one declared original ID before, identical test ID sets, no baseline skips, every method passing after, and changed implementation bytes. Otherwise the complete evidence can still be recorded as partial, with explicit findings. Both cases are validated, sealed, and semantically audited. These checks do not prove the tests are adequate, the declared mechanism is correct, or a model performed the repair. Inspect the actual code and criteria; preserve failures.

```bash
python skills/research-to-fix/scripts/case_bundle.py audit --directory ./captured-case \
  --expected-manifest-sha256 HASH
```

The root contains case.json and manifest.json; per-phase workspaces contain exact copies of selected implementation/test files, the frozen plan, and the trusted runner. Logs and structured reports are separate. The case can be reviewed and recalled by the existing helpers (only solved records are eligible). Never replay a received bundle automatically.

Limits: 48 distinct input paths, 1 MiB per source and 12 MiB combined source bytes, 24 explicit test modules, up to 64 original IDs, 2,000 methods, 1–120 seconds per phase, 256 KiB stdout/report, 1 MiB stderr; portable relative paths, no case-insensitive collisions or linked members. See [evidence-bundle.md](evidence-bundle.md).
