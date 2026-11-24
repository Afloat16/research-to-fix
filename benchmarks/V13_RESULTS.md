# v1.3.0 — Evidence and execution diagnostics

Source: [completed benchmark CI, Linux/Python 3.13.18](https://github.com/Afloat16/research-to-fix/actions/runs/45372900657), commit `ca775731aa083e6ae5670383cbf8a6aa98d98d3e`; [committed measured snapshot](../docs/figures/v13-snapshot.json). These diagnostics measure separate outcomes with separate denominators. No cross-metric leaderboard or universal accuracy claim.

## 1. Semantic evidence audit

The streaming-metrics example produces two actual test subprocess reports with 12 total method outcomes. Apply 13 named perturbations separately, reseal each bundle, and compare unpinned hash verification, unpinned semantic audit, and both with the original independently retained manifest digest.

| Method | Named contradictions rejected | Clean control | Coherent log-edit control |
| --- | ---: | --- | --- |
| Verify, unpinned | 0/13 | Accept | Accept |
| Audit, unpinned | 13/13 | Accept | Accept |
| Verify, pinned | 13/13 | Accept | Reject |
| Audit, pinned | 13/13 | Accept | Reject |

The test covers report/stdout disagreements, environment labels, omitted or changed outcomes, exit/result mismatch, incomplete reports, success flags, changed implementation/test snapshots, missing capture metadata/bindings, aliasing and unsealed members. Hash verification is doing its intended job: a resealed, internally hash-consistent bundle can still contain contradictory claims. The stronger audit is not a general tamper or forgery detector; independent digests remain essential. The coherent-edit control demonstrates this limitation.

## 2. Executed repair candidate diagnostics

Seven intentionally constructed defects: streaming iterable, exception contract, binary-search tie, numerical variance cancellation, ranking tie order, CSV empty fields, and nested cache aliasing. Each task is evaluated with unchanged implementation, narrowly repaired symptom, and designed full repair against identical frozen comparison files. No model calls, external issue patches or hidden-test evaluation.

| Candidate | Original symptom accepted | Full suite accepted |
| --- | ---: | ---: |
| unchanged | 0/7 | 0/7 |
| narrow | 7/7 | 0/7 |
| fixed | 7/7 | 7/7 |

21 candidate comparisons, 42 actual test subprocesses, 174 method outcomes, 21 consistent bundles. All seven narrow candidates pass the original symptom check but fail at least one other frozen test. All seven designed fixes pass the full suite. The generated test and candidate designs make this a controlled discrimination diagnostic, not an unbiased repair success benchmark.

The recorder subsequently gained an offline frozen-plan audit; [seven-platform checks](https://github.com/Afloat16/research-to-fix/actions/runs/45373126737) verified its claim-binding regression test. The performance workflow reruns the diagnostics with that stronger audit before release.

## 3. Coverage-first research planning

See [predeclared protocol](SESSION_COVERAGE_PROTOCOL.md). 34 fixed public task fingerprints × four predetermined status scenarios × two equal three-round budgets (12 or 14 distinct queries) = 272 paired simulations. Each strategy sees the same status function, never a live response. Reused fingerprints and scenario runs are not independent real-world samples.

| Metric | Legacy | Coverage-first | Wins / ties / losses |
| --- | ---: | ---: | --- |
| completed_stages | 4.757 | 5.360 | 128 / 143 / 1 |
| completed_families | 2.610 | 4.680 | 264 / 8 / 0 |
| completed_queries | 9.493 | 10.327 | 163 / 82 / 27 |
| all_stages_completed | 20.59% | 37.87% | 47 / 225 / 0 |
| counterevidence_completed | 97.79% | 97.79% | 0 / 272 / 0 |

In the 12-query all-available scenario the full-stage completion fraction is 100% versus 41.18%; under hash-partial/12 queries, completed request count decreases from 7.353 to 7.147 while stage coverage increases. Counterevidence completion is unchanged overall. All scenario/budget metrics, including losses, are retained in the snapshot. Do not equate completion with relevant evidence, counterexample discovery or repair correctness. The explicit coverage strategy preserves the legacy CLI default and never automatically reissues a request.

## Reproduce

Python 3.10+, no third-party runtime packages or network. Use new output paths. The repair diagnostic executes only the repository's trusted local test fixtures.

```bash
python benchmarks/capture_audit.py --output /tmp/r2f-capture-audit.json
python benchmarks/repair_capture_suite.py --output /tmp/r2f-repair-capture.json
python benchmarks/session_coverage.py --output /tmp/r2f-session-coverage.json
node docs/figures/render-v13.cjs --check
```

The [trusted recorder guide](../skills/research-to-fix/references/unittest-capture.md) documents freeze, explicit execution approval and offline re-auditing. The [matched agent protocol](AGENT_COMPARISON_PROTOCOL.md) remains the route to future real same-model agent comparisons. No such trials have been reported yet.
