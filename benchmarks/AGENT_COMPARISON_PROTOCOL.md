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

## Interpretation

Report all arm rates, status counts, usage coverage and paired task-level deltas with pointwise bootstrap 95% intervals. Multiple seeds are clustered by task. The exact two-sided sign test ignores task-level ties; Holm-adjusted p-values cover all predeclared target-vs-arm tests (including baseline). The mean interval and sign test address different quantities. Incomplete usage sums are lower bounds, not evidence of lower cost. Report losses, inconclusive outcomes and blocked cases, not only wins.

The importer checks supplied artifact consistency and declared budgets; it cannot authenticate a model run or certify agent isolation. Synthetic tests validate the importer, not repair ability. **No same-model multi-arm results have been collected for this repository yet.** Do not publish a leaderboard until actual matched agent trials have been run.
