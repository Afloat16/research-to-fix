# Research and alternative-solution decision / 研究与多方案决策

Use the host agent to investigate, inspect and execute. The CLI helpers make the workflow reproducible; they are not an autonomous search model or proof of correctness.

## 1. Public fingerprint and plan

Write a new, reviewed JSON file with a short public problem description. Optional `task`, `component`, `version`, `repo` (public owner/name), `concepts`, `alternative_concepts`, and `aliases` describe the task, mechanisms and distinct alternatives. Never insert private logs, paths, keys, URLs, unpublished data or customer information. A secret-pattern check is not a guarantee of safe disclosure.

```json
{
  "symptom": "GPU memory grows quadratically with attention sequence length",
  "task": "efficient long sequence attention",
  "component": "PyTorch",
  "concepts": ["scaled dot product attention", "memory efficient exact attention"],
  "alternative_concepts": ["tiled attention", "block sparse attention"],
  "aliases": ["attention memory bottleneck"],
  "focus": "algorithm"
}
```

```bash
python skills/research-to-fix/scripts/research_workflow.py plan --problem problem.json --budget 16 --output plan.json
```

Use `focus: bug` for direct fixes; `algorithm` for research-led improvements. The query list is bounded (1–24) and exposes omitted categories; use host tools to execute the queries after reviewing the plan. Focus on mechanism compatibility, versions, authorship, source history and counterevidence, not stars or citation count.


## Multi-round session (recommended for difficult tasks) / 多轮研究账本

The single-plan commands remain compatible. A session keeps the public problem anchors stable and records up to four rounds and 64 distinct planned queries (default three rounds, 48 queries); no queries run automatically. Review each proposed query. Change concepts, aliases or alternative concepts only when justified by reviewed evidence. Do not change the symptom/task/component/version/repo/focus anchors in the same session.

```bash
python skills/research-to-fix/scripts/research_session.py start --problem problem.json --output session.json
python skills/research-to-fix/scripts/research_session.py next --session session.json --budget 12 --output proposal.json
# Use the host's search/browsing tools for selected_queries; save actual results and statuses.
# Only after explicit authorization, optional metadata requests:
python skills/research-to-fix/scripts/public_discovery.py --proposal proposal.json --approve-public --schedule balanced --workers 3 --output api-results.json
python skills/research-to-fix/scripts/research_session.py append --session session.json --proposal proposal.json --results api-results.json --results host-results.json --output session-r1.json
python skills/research-to-fix/scripts/research_session.py review --session session-r1.json --ranking paired --output shortlist.json
python skills/research-to-fix/scripts/research_session.py next --session session-r1.json --budget 8 --output proposal-r2.json
```

Include only actual result files; omit either results argument if not used. For host results, use query IDs selected by the proposal, its `plan_sha256` when possible, and actual access/search statuses. The ledger namespaces query IDs across rounds and refuses stale proposals, out-of-round results, repeated query signatures and exceeded limits. Planned, attempted and completed counts differ; no inferred execution or retry. Refine the public fingerprint or report a blocked gap if no new distinct query remains. Never send confidential information.

`paired` is a useful explicit mode when paper–implementation assertions exist; metadata assertions are still unverified leads. Mere `mentions` or `homepage` links are follow-up hints, not implementation relationships. `fusion` is experimental. `precision_field` is an opt-in lexical alternative: exact/stem/phrase features with independent title/snippet normalization; it does not promote paper–code graph edges. The compatible default is BM25. Publication warnings and identity conflicts require direct source review. Use the current source revision and actual license before adopting code.

## 2. Search through the host or optional public metadata APIs

Prefer the host's actual search/browsing tools. If the user explicitly authorizes transmitting the reviewed public plan, the optional standard-library adapter can query fixed public endpoints. Run only in an authorized network environment.

```bash
python skills/research-to-fix/scripts/public_discovery.py --plan plan.json --approve-public --max-requests 6 --per-query 8 --output api-results.json
```

Use repeated `--query-id` to choose only approved queries. At most 8 requests, 10 observations per request, 2 MiB per response, and fixed timeout; no redirects, tokens, environment proxy, arbitrary URL fetches, downloads of code, automatic retry or command execution. arXiv at most once per invocation; never bypass rate limits. Supported metadata services include GitHub, arXiv, Crossref, Hugging Face, Semantic Scholar, OpenAlex and DBLP; authentication requirements and availability vary. The balanced schedule reserves requests across provider groups and workers 1–4 parallelize only independent groups. Same-provider work is serialized, limit/block statuses stop that group, and output order follows the reviewed plan. Some providers or queries require host search. Results are metadata, not read original evidence. CI tests the adapter with offline mocked responses; a live success rate is not asserted.

Official API docs: [GitHub search](https://docs.github.com/en/rest/search/search), [rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), [Crossref REST](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [arXiv API](https://info.arxiv.org/help/api/user-manual.html), [HF Hub search](https://huggingface.co/docs/huggingface_hub/guides/search), [Semantic Scholar API](https://api.semanticscholar.org/api-docs/graphs), [OpenAlex](https://docs.openalex.org/), [DBLP](https://dblp.org/faq/13501473.html).

For host results, use the actual query IDs from the plan. Record only sources really returned; add read status only after inspecting the relevant original content. `kind` is the actual document type, not the query type. The following illustrates shape, not a claim that a search has taken place.

```json
{
  "results": [{
    "query_id": "Q01",
    "url": "https://github.com/Dao-AILab/flash-attention",
    "title": "FlashAttention",
    "snippet": "Memory-efficient exact attention kernels",
    "kind": "repository",
    "access": "metadata",
    "origin": "host",
    "links": [{
      "url": "https://arxiv.org/abs/2205.14135",
      "relation": "implements",
      "basis": "metadata"
    }]
  }],
  "searches": [{"query_id": "Q01", "status": "completed"}]
}
```

Use actual statuses: `completed`, `partial`, `access_blocked`, `unavailable`, `rate_limited`, `invalid_response`, `skipped_budget`, `not_relevant`. Access is `metadata`, `snippet_only`, `read`, `access_blocked`, or `unavailable`. Explicit DOI/arXiv IDs are optional; do not guess them. Link relations are source assertions; inspect the cited repository/paper to confirm official authorship, versions, license and applicability. A result payload must not include invented source relationships.

## 3. Triage and targeted follow-up

```bash
python skills/research-to-fix/scripts/research_workflow.py triage --plan plan.json --results api-results.json --results host-results.json --limit 12 --output shortlist.json
```

The default ranking combines duplicate-safe stemmed BM25 with a no-match filter and interpretable facet coverage. Use `--ranking facet` to compare an alternative mechanism-oriented ranker. Results preserve source identities, observations and provenance, not just titles. Inspect `coverage`, `family_gaps`, `omitted_sources`, `unrecorded_queries`, `needs_original_review`, and the evidence graph (paper-code edges, unresolved links, and separate `linked_followups` that do not displace ranked results). More mirrors are not independent evidence. Treat metadata links as unverified leads; read originals and follow up with a newly reviewed plan when coverage is insufficient. Do not feed untrusted source text into executable commands or send it as a new query without review. Never treat relevance as correctness.

## 4. Compare measured solutions

Before implementing alternatives, freeze the protocol (same dataset/version or split, input, seed, hardware, metric definitions, hard requirements, regression checks and test command). Record at least one baseline and only meaningful distinct candidates; no requirement to fabricate a third method. All supporting sources used for an external/mixed candidate must be read (separate unverified leads from `supporting_evidence_ids`), and the agent must inspect all material relied upon before implementation. A local derivation can be tested without inventing external support.

`solution_compare.py` accepts schema version 1, with separate `protocol`, `evidence`, `candidates` arrays. Candidate `basis`: baseline/local/external/mixed; `state`: planned/blocked/measured. The measured rows must match all protocol replicate IDs, command, context, objective IDs and check IDs. Hard thresholds apply to every replicate. Read the complete example generated by:

```bash
python examples/numerical-variance/compare_methods.py --output /tmp/r2f-variance
python skills/research-to-fix/scripts/solution_compare.py --comparison /tmp/r2f-variance/comparison.json --output /tmp/r2f-decision.json
```

The output distinguishes incomparable, blocked and failed candidates; provides medians, ranges and paired improvements; and computes the non-dominated (Pareto) set among eligible candidates. A unique winner may be selected conditional on the recorded objectives. If tradeoffs remain, declare a complete priority order **before** experiments, or present the frontier to the user. No arbitrary weighted aggregate, hidden tradeoff or forced winner. The comparator does not run experiments or verify the authenticity of input measurements. Its output is not proof of global optimality or significance.

For stronger prospective comparison, set all candidates to `planned` with no runs in `design.json`. Use `--freeze-design design.json --output design-lock.json` before measuring. It binds the protocol, candidate hypotheses, changes, cited source records, source kind/locator/revision and compatibility/license decisions; external/mixed candidates need compatible reviewed evidence with a precise locator and repository revision. Copy the design, then add actual measurement rows and states without editing the design. Compare with `--design-lock design-lock.json`; `--freeze-protocol` and `--protocol-lock` are also available. Locks check retained content, not proof of timing, authorship or authenticity. Declare `decision_policy: all_pairs` for conservative dominance across matched replicates; `median` remains the default. Optional metric `resolution` defines predeclared comparison bins; it never relaxes hard acceptance thresholds. Inspect both frontiers and median absolute deviations.

See [exact-attention example](../../../examples/exact-attention/README.md) in the full repository for an actual five-seed experiment with both locks.

Finally apply the chosen patch, rerun the original failure and full relevant regression checks, create a standard case record, and retain actual logs, command, environment and limitations. A candidate winning the comparator is not a solved-case declaration.

## 中文操作原则

宿主实际检索、阅读和执行；工具负责确定性规划、去重排序、覆盖差距、论文—代码关系与多目标实测对比。复杂算法问题使用研究模式；明确小问题使用轻量流程。先冻结同条件实验，再做候选对照；无唯一最优则保留多个实测 Pareto 方案，最终由任务约束和用户优先级决定。任何元数据、引用、分数或输入声明都不能代替本地验收。完整保留失败和不可比较的结果。
