# Release readiness / 发布验收

This checklist is a review contract, not a claim that every item has passed. Keep links to actual runs and identify any waived item with justification.

| Area | Acceptance evidence |
| --- | --- |
| Scope and compatibility | Review the diff against the previous default-branch commit; schema v1 compatibility tests and documented intentional changes. |
| Behavior | All supported CI jobs complete successfully; no disabled, weakened or removed baseline tests except justified platform-specific constraints. |
| Offline safety | Default helpers and CI remain offline; no implicit scanning, network calls or execution of case commands. Optional public metadata adapter requires approval; fixed endpoint, timeout, response size, request budget, error and redaction tests. |
| Evidence lifecycle | Reproduce the synthetic streaming case, validate it, review its declared gaps, recall it, seal explicitly declared snapshots/logs, verify its manifest, and audit its captured outcomes against sealed files. Retain CI artifacts; a consistent capture does not authenticate the run. |
| Documentation | Both READMEs, SKILL.md, CLI help, reference files and changelog agree on behavior and limits. |
| Open source operations | Issue/PR templates, contribution instructions and security reporting channel are usable. Review license and attributions. |
| Retrieval performance | Fixed benchmark data fingerprints match; legacy and compact-index top-k parity, batch parity, bounded memory regression, quality floors and timing warnings reviewed. |
| Research and decision | Review fixed public-source replay metrics against lexical baselines, identity collapse, paper-code graph provenance and actual numerical comparison gates. No live-provider or general repair claim from offline fixtures. |
| Real-world efficacy | New workflow success claims require independent cases with reproducible before/after checks and explicit scope. Synthetic examples alone are not a general benchmark. |

## Before merging

- Inspect [Checks](https://github.com/Afloat16/research-to-fix/actions/workflows/checks.yml) for the exact candidate commit.
- Review all failed/skipped jobs and CI artifact contents. Never describe pending tests as passed.
- Review sensitive file/path handling and example artifacts. Do not publish private material.
- Ensure branch is up to date; review conflicts rather than force-pushing main.

## Before tagging a release

- Decide the version based on prior published releases and compatibility, not the size of the diff. Keep schema and release versions distinct.
- Move Unreleased changelog entries to the chosen version, note intentional input-policy changes and migration/workarounds.
- Verify installation through a supported agent host and document host-dependent behavior.
- Choose release notes with verified improvements, limitations, and links to evidence. Do not claim an independent benchmark or security certification.
- Tag only a reviewed, passing commit; release assets must not include secrets. Changing VERSION on reviewed main is the explicit maintainer publication action. Checks builds the exact-commit deterministic skill ZIP, runs quality gates before publication, and refuses existing tags. Confirm the actual release and checksum assets; CI success alone does not prove a release exists. Runtime host compatibility still depends on the host.

## Reproducible package

From a committed release version: `python tools/build_release.py --commit FULL_COMMIT_SHA --output /tmp/r2f-release`. Check the ZIP SHA-256. The package includes only tracked skill files, LICENSE and VERSION, not the worktree. The release job runs only after a main push and detects a VERSION change relative to its first parent; no release on PRs or routine unchanged-version pushes.

## After release

Monitor issues for regressions, prioritize reproducible reports, and retain honest partial/blocked case outcomes. If rollback is necessary, prefer a reviewed revert or patch release over destructive history changes.
