# Release readiness / 发布验收

This checklist is a review contract, not a claim that every item has passed. Keep links to actual runs and identify any waived item with justification.

| Area | Acceptance evidence |
| --- | --- |
| Scope and compatibility | Review the diff against the previous default-branch commit; schema v1 compatibility tests and documented intentional changes. |
| Behavior | All supported CI jobs complete successfully; no disabled, weakened or removed baseline tests except justified platform-specific constraints. |
| Offline safety | No new external dependencies, implicit scanning, network calls, or execution of case commands; adversarial inputs and diagnostics tested. |
| Evidence lifecycle | Reproduce the synthetic streaming case, validate it, review its declared gaps, recall it, seal explicitly selected snapshots/logs and verify its manifest. Retain CI artifacts. |
| Documentation | Both READMEs, SKILL.md, CLI help, reference files and changelog agree on behavior and limits. |
| Open source operations | Issue/PR templates, contribution instructions and security reporting channel are usable. Review license and attributions. |
| Retrieval performance | Fixed benchmark data fingerprints match; legacy and compact-index top-k parity, batch parity, bounded memory regression, quality floors and timing warnings reviewed. |
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
- Tag only a reviewed, passing commit; release assets must not include secrets. A tag or publication is a separate maintainer action.

## After release

Monitor issues for regressions, prioritize reproducible reports, and retain honest partial/blocked case outcomes. If rollback is necessary, prefer a reviewed revert or patch release over destructive history changes.
