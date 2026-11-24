# Multi-arm agent comparison — frozen protocol, no result yet

The primary unanswered question is whether the **skill** improves actual repair outcomes at fixed cost, not whether one lexical index beats another. Compare R2F, no skill and the actual pinned `systematic-debugging` skill from [obra/superpowers](https://github.com/obra/superpowers/tree/main/skills/systematic-debugging), or other explicitly registered competitors. SWE-agent and OpenHands are entire agent scaffolds, not drop-in skills: use a separate scaffold experiment. See also [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401) for the importance of evaluating skills in context.

## Predeclare every arm

Reuse the schema-1 base protocol in [AGENT_TRIAL_PROTOCOL.md](AGENT_TRIAL_PROTOCOL.md). Create a schema-2 JSON object with `schema_version: 2`, `base_protocol` (the complete schema-1 object), and `arms` (2–8 records). Each record has exactly:

| Field | Meaning |
| --- | --- |
| id | Unique lowercase arm identifier, including required baseline and skill |
| repository | owner/repo; null for baseline |
| commit | Full source commit; target skill must match base_protocol.skill_commit |
| skill_path | Relative directory or file at that commit |
| intervention_sha256 | SHA-256 of exact installed intervention bundle, null for baseline |

Baseline has null in all intervention fields. Use separate worktrees/processes, same model version, scaffold, task base commits, test isolation, generation settings, allowed tools, budgets and seeds. Record what is actually installed; archive the installed skill bundle and manifest outside the evaluator so an independent reviewer can verify the digest. A source commit alone does not prove what was injected. Do not cherry-pick seeds or comparators. Preregister the task selection, all arms and intended comparisons; freeze before generation.

```bash
python benchmarks/agent_comparison.py --freeze comparison.json --output comparison-lock.json
```

For every arm, use the same official evaluator artifact layout as the paired protocol in a separate `arms/<id>/` root. Its manifest contains the frozen comparison protocol digest, arm ID, applied_skill_commit, run_ids, plus intervention_sha256 (the registered value or null). Evaluator run IDs must be globally distinct across all arms/seeds. Preserve actual patches, usage and per-instance evaluator reports. Do not provide gold answers to agents. Supply empty prediction/usage artifacts for blocked replicates rather than deleting them from the trial denominator.

```bash
python benchmarks/agent_comparison.py --lock comparison-lock.json --arms-root arms --output comparison-results.json
```

## Independent lock and diagnostic outcomes

Keep the frozen `protocol_sha256` in an independently controlled record before generation; pass it as `--expected-protocol-sha256 DIGEST` when importing either paired or multi-arm results. A rewritten protocol and matching manifests can otherwise be self-consistent. The output records whether an independent digest was supplied and matched; this is not authentication of model execution. Existing commands remain compatible.

The importer reports separate prediction, evaluator and budget statuses for every replicate, plus counts per arm. These are diagnostic axes, not extra successes: the budget-gated resolved rate and existing primary status retain their original meanings. For example, a reported evaluator success with missing usage is not a valid success, and a missing prediction can still have measured over-budget cost. Empty predictions receive a digest. The paired importer also exposes usage coverage.

## Post-evaluation input digest

Both importers now return `consumed_artifacts.sha256` and per-arm file counts, bytes and SHA-256 summaries of the exact relative-path/size/digest inventory. This includes each consumed manifest, prediction, usage, report and evaluator patch file. Retain the post-evaluation digest independently and pass `--expected-artifacts-sha256 DIGEST` on re-import to detect even a semantically equivalent byte rewrite or added/removed consumed report. It is stable under relocating the same arm directories and does not scan unconsumed extras. This is separate from the pre-generation protocol pin; neither authenticates the run nor proves that unconsumed files do not exist. The operator must control the inputs during import.

## Interpretation

Report all arm rates, status counts, usage coverage and paired task-level deltas with pointwise bootstrap 95% intervals. Multiple seeds are clustered by task. The exact two-sided sign test ignores task-level ties; Holm-adjusted p-values cover all predeclared target-vs-arm tests (including baseline). The mean interval and sign test address different quantities. Incomplete usage sums are lower bounds, not evidence of lower cost. Report losses, inconclusive outcomes and blocked cases, not only wins.

The importer checks supplied artifact consistency and declared budgets; it cannot authenticate a model run or certify agent isolation. Synthetic tests validate the importer, not repair ability. **No same-model multi-arm results have been collected for this repository yet.** Do not publish a leaderboard until actual matched agent trials have been run.

The paired protocol's explicit-null prediction and optional official report-flag checks also apply to every multi-arm trial. No change to the meaning of a budget-gated success; a contradiction rejects the import instead of silently scoring it. See [format compatibility](AGENT_TRIAL_PROTOCOL.md).
