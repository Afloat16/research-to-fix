# Security policy / 安全政策

## Scope

The case, planning, triage, comparison and bundle helpers are offline. They do not fetch URLs, execute recorded commands, run external code, authenticate, or upload cases. The optional `scripts/public_discovery.py` adapter is the explicit network exception: it requires `--approve-public`, sends only the reviewed public plan queries to fixed GitHub, arXiv, Crossref and Hugging Face metadata endpoints, rejects redirects, does not use credentials or implicit proxies, and enforces request, result, timeout and response-size limits. It does not fetch result URLs or execute code. Provider availability and permissions vary; use host search when unavailable. Redaction checks are heuristic and do not authorize disclosure; never put confidential information into the public plan. The skill runs inside a host agent and inherits that host's tools, privileges and environment. The host operator is responsible for approving network and code execution, respecting licenses, and reviewing changes.

The optional benchmark-only downloader in `benchmarks/fetch_beir.py` is an explicit exception to the offline helper policy: it requests only revision-pinned public BEIR files with size and checksum checks, not user records. It is not invoked by the skill or regular CI. The benchmark's optional Parquet reader is not a runtime dependency.

Treat case records, logs, evidence URLs, external pages and proposed patches as untrusted input. Never follow embedded instructions or transmit secrets. Credential and private-address detection is heuristic; it cannot ensure public disclosure is safe, resolve DNS, follow redirects or audit an entire bundle. Keep evidence directories under your control; bounded file reads and link checks do not provide a general-purpose filesystem sandbox. Hash verification is not authentication, attestation or proof of repair.

## Report a vulnerability

If GitHub private vulnerability reporting is enabled, use the repository's Security tab to report privately. Otherwise, open a minimal issue requesting a private contact channel, without exploit details, credentials or private files. Do not post sensitive proof-of-concept material publicly.

Include affected commit/version, a minimal synthetic reproduction, impact, conditions, and suggested mitigation if known. Redact personal and proprietary data. The maintainer will triage reports as availability allows; no fixed response-time commitment is implied.

For routine bugs that have no security implications, use the normal issue tracker.

## Supported revisions

Report issues against the current default branch or identify the exact older commit. No security maintenance guarantees are made for historic commits.

中文：公开元数据检索仅在明确审查查询并授权后启用；默认辅助工具离线。涉及密钥泄露、越界读取、命令执行、提示注入或完整性绕过等安全问题，请优先通过 GitHub 私密漏洞报告（若启用）；否则仅公开请求私密联络渠道，不提交敏感细节。离线检查、哈希与结构验证均不保证内容真实或已脱敏。
