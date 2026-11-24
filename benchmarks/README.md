# Retrieval benchmarks / 检索基准评测

## What is measured

The original small fixtures below are fixed development fixtures, not a general repair-success benchmark, not a leaderboard, and not a held-out estimate of field performance. A separate external retrieval evaluation is defined in [INDEPENDENT_PROTOCOL.md](INDEPENDENT_PROTOCOL.md). Compare the same inputs, relevance judgments, top-k and environment. The production CLI additionally requires valid solved case declarations and applies a relative score threshold; raw ranking evaluations deliberately omit that threshold and evaluate top-k.

| Dataset / workload | Scope | Ground truth |
| --- | --- | --- |
| [retrieval_v1.json](datasets/retrieval_v1.json) | 40 authored diagnostic descriptions; 80 positive and 3 unrelated bilingual queries | Synthetic one-target relevance labels; not real repairs |
| [github_duplicate_titles_v1.json](datasets/github_duplicate_titles_v1.json) | 44 actual GitHub issue titles, 18 actual duplicate issue titles | Explicit public duplicate-link comments, 14 canonical targets + 30 unjudged closed bug titles; all source and judgment links retained |
| Scale workload | 120 generated structurally valid synthetic case files / 32 queries; 5,000 sparse generated documents / 64 queries | Exact report and score equality, not semantic relevance |
| [BEIR CQADupStack programmers](https://huggingface.co/datasets/BeIR/cqadupstack) | External English duplicate-question retrieval corpus | Published [qrels](https://huggingface.co/datasets/BeIR/cqadupstack-qrels), CC BY-SA 4.0; revision-pinned external data; separate independent evaluation |

The public issue sample is a small convenience sample of explicitly linked duplicates (some canonical targets remain open). The 30 distractors are unjudged, not established irrelevant. No issue bodies, comments, author details, private information, code or attached logs are included in ranked text. Dataset source links and attribution are retained in the JSON; original issue titles retain their source rights. The sample was used during algorithm development, so results are not independent test results. Do not tune repeatedly on this set and claim generalized superiority.

## Run locally

Python 3.10+; bundled benchmarks use only the standard library and report FTS5 unavailable if the local SQLite build lacks it.

```bash
python benchmarks/retrieval.py --k 5 --output /tmp/r2f-synthetic.json
python benchmarks/retrieval.py --github-titles --k 5 --output /tmp/r2f-github.json
python benchmarks/scale.py --output /tmp/r2f-scale.json
python benchmarks/regression.py --synthetic /tmp/r2f-synthetic.json \
  --github /tmp/r2f-github.json --scale /tmp/r2f-scale.json \
  --output /tmp/r2f-regression.json
```

Choose new output filenames. The [performance workflow](../.github/workflows/performance.yml) runs these comparisons offline. Reports include dataset SHA-256, document/query counts, Python/SQLite/platform, build times, repeated p50/p95 query latency, and quality metrics. The scale run compares repeated cold-helper calls against a single batch snapshot using a warmed OS page cache, and tuple vs packed retained allocations using tracemalloc; the input corpus is allocated before tracing.

MRR@k measures the reciprocal rank of the first relevant result; Recall@k measures the fraction of known relevant results retrieved; nDCG@k rewards placing relevant results high in a ranked list. Unrelated synthetic queries have separate abstention measurement. Timing varies across runners; compare same-run measurements. The gate hard-checks fixture hashes, exact parity, quality floors and a broad retained-allocation bound; latency speedups are warning thresholds, not brittle fixed millisecond gates. The old scanner is an independent transcription of the previous BM25 calculation. SQLite FTS5 native and Porter use their actual built-in tokenizers and BM25, with title weight 2 and body weight 1 ([upstream documentation](https://www.sqlite.org/fts5.html#the_bm25_function)). R2F English normalization is independently implemented from the [Porter algorithm description](https://snowballstem.org/algorithms/porter/stemmer.html); it is not claimed byte-identical to SQLite.

## Optional external evaluation

The BEIR adapter reads local `corpus.jsonl`, `queries.jsonl`, and `qrels/test.tsv`. Alternatively, explicitly fetch the pinned public programmers Parquet files and qrels; this is the only benchmark helper that uses the network. It is never run by the production skill, helper or regular CI:

```bash
python benchmarks/fetch_beir.py --output /tmp/r2f-beir
python -m pip install --only-binary=:all: pyarrow==20.0.0
python benchmarks/retrieval.py --beir-dir /tmp/r2f-beir \
  --query-limit 128 --k 10 --repeats 2 --output /tmp/r2f-beir-report.json
```

Run in a dedicated benchmark virtual environment if installing PyArrow. Corpus revision [e84b722](https://huggingface.co/datasets/BeIR/cqadupstack/commit/e84b7220ce5a4e6c49aeb568983b0ec5a7584c2c); qrels revision [2b9f579](https://huggingface.co/datasets/BeIR/cqadupstack-qrels/commit/2b9f5791698b5be7bc5e10535c8690f20043c3db). Parquet files are verified against the publisher's SHA-256, the qrels are revision-pinned and their digest is recorded. Query selection is a fixed hash of query IDs, independent of qrels scores or method outputs; use `--query-limit 0` for all queries. The full corpus is retained for either choice. Self-ID matches are excluded uniformly. BEIR document text is bounded by the same field budget for all methods. Do not redistribute BEIR material without following CC BY-SA 4.0 attribution and share-alike terms.

The attempted external Actions workflows in this iteration were rejected before creating jobs ([first attempt](https://github.com/Afloat16/research-to-fix/actions/runs/45338902871), [second](https://github.com/Afloat16/research-to-fix/actions/runs/45339034117), [combined](https://github.com/Afloat16/research-to-fix/actions/runs/45339195482)); no successful public BEIR download or score is claimed. Those automatic network workflows were removed; the local adapter remains available.

## How to compare repair systems fairly

[GPT Researcher](https://github.com/assafelovic/gpt-researcher) is a research orchestration project; [SWE-agent](https://github.com/SWE-agent/SWE-agent) and [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent) execute agent-driven software repairs. R2F is an offline evidence workflow skill and helper, not a standalone model runner. SQLite is a directly comparable lexical retrieval baseline, whereas an end-to-end agent comparison requires the same model, agent scaffold, repository snapshot, test environment, token/time/tool budget, network policy and benchmark instances. [SWE-bench](https://www.swebench.com/SWE-bench/faq/) evaluates real repository patch success; its resolved rate is not interchangeable with MRR/Recall/nDCG.

For a future independent evaluation, freeze the R2F version and candidate selection first. Use a held-out collection of real duplicate issues for retrieval, then compare one fixed agent with and without the skill on the same SWE-bench split. Record valid patches, fail-to-pass and pass-to-pass test outcomes, blocked cases, runtime, tool/token cost, source attribution, and confidence intervals. Prevent access to gold patches and post-fix data when evaluating repair. Report any inaccessible cases and failures; no general superiority claim without matched experiments.

中文：本目录提供固定双语合成数据、带公开 issue 重复链接的真实小样本、SQLite 对照、端到端批处理及内存测量和 BEIR 本地适配。数据规模、真实标签来源、性能指标、未执行的公开大数据评测均明确记录。检索指标不等于自动修复成功率，不能直接与 SWE-bench 的解决率相比较。

## Algorithm discovery and decision

[algorithm_discovery_v1.json](datasets/algorithm_discovery_v1.json) contains 32 public source identities (papers, repository and documentation links), 44 observations including publisher/DOI and synthetic tracking aliases, eight authored algorithm tasks, two query formulations per task, topic-based relevance judgments and explicit paper/code pair labels. Topics cover attention, finetuning, diffusion, graph learning, approximate nearest neighbors, distributed training, contrastive learning and boosted trees. Descriptions are independently summarized; source URLs and relationships are retained. Unjudged sources are not proven irrelevant. This is a small development fixture, not a live search evaluation or proof of code applicability. Compare the same corpus with deterministic fixed order, stemmed BM25, SQLite FTS5 Porter, facet ranking and the evidence-aware shortlist.

```bash
python benchmarks/discovery.py --output /tmp/r2f-discovery.json
python examples/numerical-variance/compare_methods.py --output /tmp/r2f-variance
```

The variance example actually runs a raw-moment baseline and three alternatives with five fixed seeds and an exact integer oracle. It checks every replicate against a fixed accuracy threshold and regression criteria, then compares latency, relative error and traced allocations. It is a small local experiment, not a general GPU or NumPy benchmark. See [the decision guide](../skills/research-to-fix/references/research-decision.md) and [example methodology](../examples/numerical-variance/README.md).

Measured snapshot: [CI 45343672697](https://github.com/Afloat16/research-to-fix/actions/runs/45343672697) · [frozen discovery and variance reports](../docs/figures/research-snapshot.json). The final shortlist achieves 92.19% recall@6, 100% MRR@6, 100% paper-and-code coverage and 87.5% complete pair recall; stemmed BM25 matches these metrics and has slightly higher nDCG (0.941939 vs 0.939178). Mechanism-formulated queries achieve 96.875% recall vs 87.5% for symptom-only queries, both on the fixed development set. The initial facet-only approach and forced family coverage were not selected as defaults after comparison. Do not infer superiority from these small development samples.

## v1.0.0 transfer and release gates

The [transfer fixture](datasets/algorithm_transfer_v1.json) adds 24 source-linked paper/repository identities and six different algorithm tasks. With the original 32 identities as unjudged background, it contains 56 distinct sources, 68 observations and 18 queries (symptom, mechanism and explicitly bilingual formulations). Relevance labels and explicit paper–code links are authored, not held out. Source availability does not imply an open-source license; inspect individual license restrictions. Both suites evaluate the same candidate corpus/Top-6 budget per method; paired ranking also uses declared links, an additional signal unavailable to lexical baselines. The method comparison does not estimate live search coverage or end-to-end repair success.

```bash
python benchmarks/discovery.py --output /tmp/r2f-original-v1.json
python benchmarks/discovery.py --dataset transfer --output /tmp/r2f-transfer-v1.json
python benchmarks/discovery_regression.py --original /tmp/r2f-original-v1.json --transfer /tmp/r2f-transfer-v1.json --output /tmp/r2f-discovery-gate.json
python benchmarks/discovery_schedule.py --output /tmp/r2f-schedule.json
python examples/exact-attention/compare_attention.py --output /tmp/r2f-attention
```

[Offline CI 45355977079](https://github.com/Afloat16/research-to-fix/actions/runs/45355977079) · [frozen snapshot](../docs/figures/v1-snapshot.json). The paired method achieves Recall@6 of 98.44% and 95.83%, complete pair recall 100% and 94.44%, respectively. Fusion and facet were retained as optional, not selected as defaults. The scheduling experiment uses fixed 40 ms mock delays, not measured internet speed. The attention experiment tests exact forward results and allocation/time tradeoffs, not GPU acceleration.

The separate explicitly approved public known-item probe ran six requests in [CI 45355435962](https://github.com/Afloat16/research-to-fix/actions/runs/45355435962). Three completed; three had provider errors. Fifteen observations, 14 unique identities, target paper DOI and repository found. This single known item is not a quality benchmark. Reproduce only with explicit network consent: `python benchmarks/live_probe.py --approve-public --output /tmp/r2f-live-probe.json`. Normal CI does not invoke it.

## External protocol and paired agent evaluation

See [INDEPENDENT_PROTOCOL.md](INDEPENDENT_PROTOCOL.md) and [independent_selection.json](independent_selection.json) for development selection and frozen external datasets, scoring rules and exact measured development results. Use `python benchmarks/independent_suite.py --selection benchmarks/independent_selection.json --output /path/to/new-output` only when authorized to download those public datasets. The suite records failures without inventing scores. Ordinary CI remains offline. Run `python benchmarks/tokenizer_benchmark.py --data /path/to/downloaded/programmers --output tokenizer.json` for paired exact-token parity and timing.

[AGENT_TRIAL_PROTOCOL.md](AGENT_TRIAL_PROTOCOL.md) defines a distinct same-model, same-scaffold, same-budget SWE-bench evaluation. Its offline result importer does not run models or repairs and its synthetic tests are not repair success measurements.
