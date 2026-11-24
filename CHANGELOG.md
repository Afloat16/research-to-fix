# Changelog

## Unreleased — evidence integrity and engineering upgrade

### Added

- `research_case.py review`: a deterministic, machine-readable completeness review for baseline/final check coverage, comparison context, per-test details, artifact declarations, and external evidence gaps. Review findings are not a quality score or certification.
- `case_bundle.py seal/verify`: offline, explicit SHA-256 manifest creation and verification with optional independently retained manifest digest, resource bounds and traversal/link rejection.
- Regression tests for strict JSON, nonregular and oversized inputs, multicast/encoded credential markers, evidence integrity, and final-attempt review.
- Bilingual user documentation, evidence bundle guide, contribution and security policies, issue and PR templates, and a release checklist.
- CI matrix for Python 3.10–3.14 on Linux and Python 3.13 on Windows/macOS; Linux jobs capture an end-to-end case review and verified evidence manifest.

### Changed

- `validate` and `review` use bounded regular UTF-8 JSON reads (4 MiB) and the same strict parsing policy as `recall`; duplicate keys, overflowed non-finite numbers and unpaired surrogates are rejected.
- Reject multicast/reserved IP literals and inspect decoded credential markers in URLs. Detection remains heuristic; no DNS resolution.
- File reads reject symbolic links and Windows reparse points, detect common file replacement/modification races, and preserve bounded, nonblocking reads where supported.
- The skill now recommends completeness review and optional evidence sealing for complex handoffs.

### Compatibility

- Schema v1, existing query defaults, recall ranking, and validation exit codes are retained.
- `validate` intentionally rejects oversized, linked or special-file inputs that were previously not bounded by this policy.
- Evidence bundles are optional and have their own manifest format; existing case files need no migration.
- No runtime dependencies, automatic upload, or command execution introduced. No general repair-success or performance improvement claim is made.
