# Evidence review and bundle integrity / 证据复核与封存

## Three different guarantees

| Tool | Checks | Does not establish |
| --- | --- | --- |
| `research_case.py validate` | Schema v1 declarations and reference consistency | Truth, causality, source availability |
| `research_case.py review` | Coverage of declared checks, context, test details, artifacts and source support | A quality score, actual artifact existence, actual source content |
| `case_bundle.py verify` | Listed file bytes and sizes against SHA-256 manifest; case consistency | Authorship, actual execution, completeness of unlisted material |
| `case_bundle.py audit` | Explicit unittest JSON captures: report/stdout equality, declared outcomes/exit, snapshot/context digests and complete capture coverage | Actual execution, coordinated fabrication, arbitrary log interpretation |

A valid blocked or partial case is useful. A verified bundle can still contain invented results. An independently retained manifest digest detects replacement relative to that digest; it is not a signature or identity proof.

## Usage

Run from the repository root after recording the streaming example:

```bash
python skills/research-to-fix/scripts/research_case.py review /tmp/research-to-fix-example/case.json
python skills/research-to-fix/scripts/case_bundle.py seal --directory /tmp/research-to-fix-example \
  --artifact runs/before/metrics.py --artifact runs/after/metrics.py
python skills/research-to-fix/scripts/case_bundle.py verify --directory /tmp/research-to-fix-example
```

For complete replay of the streaming example, add all four snapshot names (`metrics.py`, `test_metrics.py`, `test_metrics_streaming.py`, `_record_tests.py`) from both `runs/before/` and `runs/after/` with repeated `--artifact`. Logs and per-test JSON reports referenced by the record's optional run-level `artifacts` mapping are included automatically. The manifest itself is excluded.

The seal command prints its digest, file count and total bytes. Save the digest separately. The verifier accepts the optional `--expected-manifest-sha256 HASH` argument. Both commands print JSON and return 0 on success; 1 for a structurally inconsistent case or integrity mismatch; 2 for malformed input, unsafe paths, resource limits, file operations or an existing manifest. Missing or unreadable listed members during verification count as integrity failures.

`review` returns 0 for structurally valid records (including blocked/partial), 1 for record errors, 2 for input errors. In multi-attempt mode only the selected final attempt contributes to final check counts. Test detail and artifact declaration counts are presence indicators, not independent tests. Matching context is literal equality, not an environment audit. For valid partial records, review also flags changed acceptance criteria/expected exit codes and missing or nonpassing baseline test IDs; these are review prompts, not evidence that a repair has failed. External mappings without a read source declaring a viable route or solved report receive a review prompt; such prompts do not invalidate legacy records. Findings are stable identifiers to support integrations, not weights or probabilities.

## Strict capture consistency (opt-in)

New recording helpers can declare `capture` on every executed validation run. Existing schema-v1 cases and ordinary seal/verify remain compatible. Run `case_bundle.py audit --directory DIR --expected-manifest-sha256 HASH` after seal; omit the digest only for a local consistency diagnostic, not independent replacement detection. The streaming recorder now declares all snapshot files automatically. No commands or test code are executed by audit.

The `capture` object has exactly schema_version 1, format `unittest-json-v1`, report/stdout/stderr (distinct artifact paths), implementation_files (path to SHA-256), and comparison_files (comparison_context key ending in .sha256 to sealed path). All paths must also occur in that run's artifacts mapping. Every declared .sha256 comparison key must be bound, and matched checks must have the same actual snapshot digests. Use distinct paths for each run. The report is a JSON object with python_version, python_implementation, tests_run, successful and test_results; stdout must parse to the same object. The strict format requires complete per-method outcomes (pass/fail/error/skipped), tests_run equals count, successful iff no fail/error, exit 0 iff successful, and case result pass iff every method passes. Expected-failure semantics, incomplete test reports and other formats are not supported; use normal verify and manual review instead. The report and stdout are independently re-read with size/hash checks against the verified manifest. A partial repair can pass the consistency audit; it remains partial. The stderr file is sealed, not interpreted.

The new check catches contradictions even when someone inadvertently regenerates a manifest from inconsistent artifacts. An attacker who consistently rewrites the case, reports, snapshots and manifest can still pass without an independent pin; no authenticity or actual execution guarantee.

## Scope and limits

- No network, credentials, dependencies, uploads, archive extraction or recorded command execution.
- Only the fixed `case.json`, its declared run artifacts and explicitly selected relative files are read. Extra unlisted files are ignored, so explicitly include all material needed for review.
- Portable ASCII relative paths: letters, digits, dot, hyphen, underscore and slash; no traversal, absolute paths, device names, case-insensitive duplicates or symbolic links within the selected directory. Maximum path length 240 characters. Ancestors of the explicitly chosen directory resolve normally. Reparse points are rejected on Windows.
- At most 128 members including case.json, 4 MiB case, 16 MiB per other file, 64 MiB aggregate, 128 KiB manifest. UTF-8 JSON rejects duplicate keys, non-finite numbers and unpaired surrogates.
- Files must be regular and stable during reading. Use a quiescent directory controlled by the operator; these checks are not a sandbox against hostile concurrent tree replacement. A failed or interrupted write can leave a partial manifest; verify before sharing and use a fresh output directory for a new seal.
- The manifest contains file names, hashes and sizes, not raw file content, but the bundle still contains the original selected files. Review and redact before copying or publishing; hashes do not anonymize sensitive data. Do not use this tool to certify secret removal.
- `recall` scans top-level JSON candidates; it may count manifest.json as invalid_case. This is expected: a manifest is not a repair record.

## 中文说明

`validate` 判断案例声明的结构一致性；`review` 统计前后检查、最终轮次、比较条件、测试明细、产物声明与证据缺口；`seal/verify` 对明确选择的本地文件做 SHA-256 完整性校验。三者均不保证实验真实、因果成立或外部资料可信。复核提示不是评分，旧 schema v1 可继续使用。保留清单摘要时应独立保存；共享证据包必须检查源代码、路径、日志与数据，不自动脱敏。不运行案例命令、不联网、不扫描无关目录。
