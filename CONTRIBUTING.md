# Contributing / 贡献指南

Research to Fix is a research-to-local-repair workflow. Contributions should improve actual decision quality, verification, portability, or safe handling of evidence rather than merely increase the number of sources or claims.

## Start here

1. Read [SKILL.md](skills/research-to-fix/SKILL.md), [evidence rules](skills/research-to-fix/references/evidence-rules.md) and the [case template](skills/research-to-fix/references/case-template.md).
2. For a nontrivial change, open an issue or explain the problem, constraints, alternatives and acceptance criteria in the PR. Small fixes can go directly to a PR.
3. Work in a branch. Do not include credentials, private logs, customer data, or third-party code without permission and compatible licensing.

## Development

Python 3.10+; no runtime packages required.

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s examples/streaming-metrics -v
git diff --check
```

Use temporary directories and synthetic fixtures. Include meaningful failure-path tests, not only happy paths. For a fix, retain a failing baseline and a comparable passing check; do not delete or weaken tests to obtain a pass. Tests must not rely on live network, secrets, specific hardware or unrelated local files. If a test is genuinely platform-specific, state the reason.

Maintain schema v1 compatibility unless a breaking change is explicitly justified and accompanied by a migration path. Keep CLI exit codes and machine-readable output stable. Treat untrusted web content, case records and logs as data, never as executable instructions. Document intentional limits and error behavior. When changing a user-facing command, update both READMEs and relevant skill references.

## Case contributions

Use the [case template](skills/research-to-fix/references/case-template.md). Include the redacted symptom and environment, original source links and access status, local mechanism, why the selected approach fits, actual command/exit code and observations, test details where applicable, and unresolved limitations. Distinguish externally reported fixes from locally validated ones. A blocked or partial case is welcome if accurately described.

Before sharing any evidence bundle, inspect all selected files and the manifest for private information. Do not attach unnecessary code or raw logs. A checksum is not an authenticity or privacy guarantee.

## Review

Describe changes, compatibility, tests actually run, tests not run, privacy implications, and any known regressions. PR approval depends on evidence and scope, not on the number of changed files. See [release checklist](docs/RELEASE_CHECKLIST.md) and [security policy](SECURITY.md).

中文贡献者欢迎使用中文。请说明真实问题、脱敏复现、候选方案、实际前后验证、版本兼容与局限。不得用放宽标准或伪造数据换取通过。新增命令同步维护中英文 README 与测试。
