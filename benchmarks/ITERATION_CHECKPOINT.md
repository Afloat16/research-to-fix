# Iteration checkpoint — 2026-11-24

Base: main `1f8c22900333cc922d417f406851df5b53635cfa`, published [v1.2.0](https://github.com/Afloat16/research-to-fix/releases/tag/v1.2.0). No open PRs at inspection. Continue `next/evidence-integrity-repair` from `b1db514fb9053c60fb0c40bd5c041d2c1cec1665` (8 ahead, 0 behind). Do not bump VERSION yet.

## Verification at base

- [Checks](https://github.com/Afloat16/research-to-fix/actions/runs/45373126737): all seven platform/version test jobs successful; branch release job skipped.
- [Retrieval performance](https://github.com/Afloat16/research-to-fix/actions/runs/45373126752): offline job successful, including capture perturbations, controlled local repair candidates, and simulated session planning. These are not model trials. Full artifact numbers have not been extracted in this checkpoint.
- Local git clone failed DNS resolution; use existing branch CI for the actual repository tests. No authorized model execution environment was established; no secrets queried or paid service enabled.

## New change and frozen check

The old importer retained the final budget-gated status but lost the explicit evaluator outcome when missing/over-budget usage overrode it. A non-submitted task could also carry over-budget usage without that being counted as a budget failure. The protocol lock was self-consistent, but an independently retained digest could not be checked. Add independent digest validation and orthogonal diagnostic axes without changing the gated rates or original primary statuses.

Reproducible synthetic importer comparison (not repair success): run `python -m unittest discover -s tests -p 'test_agent*.py' -v`. The controlled two-task/two-seed fixture has two evaluator-reported successes (one over budget, one missing usage), one absent prediction with over-budget cost, one empty prediction within budget. Expect unchanged 0/4 gated successes, 3/4 usage coverage, evaluation counts 2 resolved / 2 not applicable, budget counts 2 exceeded / 1 missing / 1 within. A rewritten self-consistent protocol must be rejected when compared to the original independent digest. Tests cover both importers. These are preregistered assertions, not observed outcomes at commit creation. Confirm the new head CI before interpreting or releasing.

## Comparator review

- [obra/superpowers systematic-debugging at 22f0b463](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/systematic-debugging/SKILL.md): root cause investigation, references, one hypothesis at a time, failing test and final verification; relevant skill intervention. No comparator code executed.
- [SWE-agent README at 3ea751c0](https://github.com/SWE-agent/SWE-agent/blob/3ea751c087f32b16e039a2233dd6eefecef325d5/README.md) recommends mini-SWE-agent as its successor; it is an execution scaffold, not a drop-in competing skill. Keep the scaffold identical across skill arms and evaluate scaffold comparisons separately.
- This is source review, not a measured performance comparison. Freeze exact installed bundle digests and task/model/budget identifiers before authorized model generation.

Next: inspect fresh Checks and Retrieval performance runs, retrieve the existing experiment JSONs and record exact counts/tradeoffs, verify newly added importer tests, and update bilingual README with measured results only. A true multi-arm trial remains unrun. Keep release gates intact.

## Concurrent release handoff

The release branch advanced during this run to `98a502434c05b79089272f800cecbb26b41df775` and opened [PR #9](https://github.com/Afloat16/research-to-fix/pull/9) for v1.3.0. The lease rejected our older-head update. Do not modify or reset that in-flight release PR. Preserve this nonoverlapping importer change on a single successor iteration branch based on the PR head, with no additional VERSION bump or release PR; reconcile against main once v1.3.0 is published. [V1.3 candidate results](V13_RESULTS.md) include the measured local repair and semantic audit outcomes and clearly label the planner simulations.

## Additional artifact provenance iteration

Add deterministic per-arm and protocol-bound aggregate digests of every byte consumed by the two offline importers; independent post-evaluation pin rejects changed usage, report removal, and even JSON whitespace changes, while relocation and ignored extras do not alter the digest. Unit tests exercise both importers. This does not authenticate model execution or certify the full directory contents. The successor branch is intentionally not released; retain the verified v1.3.0 release and accumulate meaningful next changes.
