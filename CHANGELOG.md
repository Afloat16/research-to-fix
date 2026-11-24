# Changelog

## 1.0.0 — 2026-11-24

### Multi-round research, paired evidence, and locked decisions

- Add bounded, immutable-output research sessions with per-round query IDs, plan digests, distinct-query budgets, coverage diagnostics and targeted follow-up.
- Extend opt-in metadata adapters with Semantic Scholar, OpenAlex and DBLP; retain fixed allowlisted endpoints, per-provider budgets, explicit approval, no credentials or automatic retries.
- Add balanced provider scheduling and bounded parallel workers; stable report ordering, serialized provider groups and recorded failures.
- Isolate contradictory source aliases and reported retraction/withdrawal warnings; distinguish metadata mentions from explicit paper–code assertions. Add optional paired and experimental fusion ranking; preserve the default BM25.
- Add independent protocol/design locks, precise supporting source locators, code revision/license/compatibility review, matched-replicate Pareto and declared metric resolutions.
- Add six cross-domain algorithm tasks and bilingual query formulations, quality gates on both fixed corpora, and a five-seed actual exact-attention comparison.
- Freeze actual benchmark reports and bilingual figures; retain a separate live known-item probe with failure states. No claim of independent repair accuracy.
- Add reproducible exact-commit skill ZIP with SHA-256 and version-change-triggered GitHub publication after CI and benchmark gates.

### Research discovery and measured multi-solution decision (included foundation)

- Public-fingerprint research planner spanning symptom, mechanism, implementation, alternatives, verification and counterevidence; explicit source budgets and coverage gaps.
- Optional, explicitly approved public metadata API adapter with fixed endpoints, bounded requests and mocked transport tests; host browsing remains preferred.
- Provenance-preserving identity grouping, BM25 and facet rankers, paper-code graph and source access review.
- Protocol-bound baseline/alternative measurement comparison, every-replicate acceptance gates, paired metrics, Pareto frontier and optional declared objective priority.
- Source-linked 32-identity algorithm discovery development replay and measured numerical variance example in offline CI. No representative live-provider accuracy or universal repair-success claim.
- Agent Skills prompts, bilingual guides and reproducibility documentation.

## Previous upgrade — retrieval performance, ranking and reproducible benchmarks

### Retrieval performance

- Reusable validated in-memory `RecallSnapshot` and `recall-batch` CLI; compact arrays, precomputed BM25 postings, bounded top-k, deterministic tie-breaking and exact legacy score semantics across Python versions. Single-query scan avoids full-index startup cost.
- Experimental technical, stemmed, hybrid and phrase-aware contextual rankers; identifier expansion, Chinese bigrams and primary symptom weighting, with no default ranking change.
- Strict batch query file bounds and no persistent cache; rebuild after file changes. Existing case corpus limits and solved-case validation unchanged.
- Fixed 40-document bilingual synthetic corpus (83 queries), a public 44-title GitHub duplicate-issue sample (18 source-linked judgments), SQLite FTS5/Porter baselines, synthetic throughput/memory workloads, and an optional local BEIR adapter/downloader. Benchmark reports distinguish ranking from repair success.
- CI performance comparisons, deterministic quality/consistency gates, broad timing warnings, source provenance, and documented limitations.

### Documentation and visualization

- Redesigned bilingual landing pages with five original paper-style vector figures in each language: full evidence workflow, dual retrieval architecture, synthetic and public-issue ranking comparisons, and paired throughput/memory results.
- Freeze a source-linked completed benchmark snapshot and provide deterministic SVG generation/checking. Preserve full command explanations in bilingual user guides.

## Previous upgrade — evidence integrity and engineering upgrade

### Added

- Optional `queries --strategy balanced`: interleave error and mechanism stages and cover distinct sources before repeating languages under a limited candidate budget. Legacy order remains the default.

- `research_case.py review`: a deterministic, machine-readable completeness review for baseline/final check coverage, comparison context, per-test details, artifact declarations, changed acceptance criteria, missing/nonpassing baseline test IDs, and external evidence gaps. Review findings are not a quality score or certification.
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
