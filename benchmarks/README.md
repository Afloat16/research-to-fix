# Retrieval benchmarks / 检索基准评测

## What is measured

These are fixed development fixtures, not a general repair-success benchmark, not a leaderboard, and not a held-out estimate of field performance. Compare the same inputs, relevance judgments, top-k and environment. The production CLI additionally requires valid solved case declarations and applies a relative score threshold; raw ranking evaluations deliberately omit that threshold and evaluate top-k.

| Dataset / workload | Scope | Ground truth |
| --- | --- | --- |
| [retrieval_v1.json](datasets/retrieval_v1.json) | 40 authored diagnostic descriptions; 80 positive and 3 unrelated bilingual queries | Synthetic one-target relevance labels; not real repairs |
| [github_duplicate_titles_v1.json](datasets/github_duplicate_titles_v1.json) | 44 actual GitHub issue titles, 18 actual duplicate issue titles | Explicit public duplicate-link comments, 14 canonical targets + 30 unjudged closed bug titles; all source and judgment links retained |
| Scale workload | 120 generated structurally valid synthetic case files / 32 queries; 5,000 sparse generated documents / 64 queries | Exact report and score equality, not semantic relevance |
| [BEIR CQADupStack programmers](https://huggingface.co/datasets/BeIR/cqadupstack) | External English duplicate-question retrieval corpus | Published [qrels](https://huggingface.co/datasets/BeIR/cqadupstack-qrels), CC BY-SA 4.0; optional local data, no external run claimed in this upgrade |

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
