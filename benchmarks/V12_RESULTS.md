# v1.2.0 evidence and reproduction

## Exact relative-threshold recall

Source: [completed benchmark run 45366494938](https://github.com/Afloat16/research-to-fix/actions/runs/45366494938), [job log](https://github.com/Afloat16/research-to-fix/actions/runs/45366494938/job/138349447314), commit `0c65120111e94c1b4d964b231b3531bbf4233fa9`, Linux/Python 3.13.18. [Full numeric snapshot](../docs/figures/v12-snapshot.json).

The old path computes all matching explanations, ranks candidates and slices Top-K; the new path computes identical scores and threshold-qualified count, chooses the same deterministic Top-K and reconstructs explanations for only returned documents. The test checks exact count, float score, ID, order and explanation equality, not just aggregate metrics.

| Workload | Old P50 (ms) | New P50 (ms) | P50 speedup | P95 speedup | Sample peak allocation reduction | Parity |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| bm25_sparse | 0.2600 | 0.0905 | 2.87× | 2.57× | 59.5% | Exact |
| bm25_mixed | 10.0483 | 2.1076 | 4.77× | 6.83× | 64.8% | Exact |
| bm25_dense | 27.5054 | 7.9357 | 3.47× | 4.13× | 65.8% | Exact |
| field_sparse | 0.2593 | 0.0909 | 2.85× | 2.73× | 59.4% | Exact |
| field_mixed | 10.1877 | 2.1088 | 4.83× | 6.66× | 64.8% | Exact |
| field_dense | 27.5294 | 7.8640 | 3.50× | 4.28× | 65.8% | Exact |

5,000 generated documents; 48 queries per workload, three timing repeats, 288 distinct workload-query pairs, Top-5, relative threshold 0.5. Prepared tokens and warmed index; excludes index build, tokenization, file IO and end-to-end agent execution. Peak allocation measured on one fixed query per workload, not total RAM or representative memory distribution. Timings may vary across hardware; do not compare these numbers directly with raw-query benchmarks from external engines.

```bash
python benchmarks/relative_recall.py --output /tmp/r2f-relative-recall.json
python -m unittest discover -s tests -v
node docs/figures/render-v12.cjs --check
```

The [frozen Mathematica transfer protocol](TRANSFER_V12_PROTOCOL.md) defines the separate retrieval comparison below. The [multi-arm evaluation protocol](AGENT_COMPARISON_PROTOCOL.md) and coverage audit are engineering contributions, not demonstrated gains in agent repair accuracy. See the prior [four-corpus evaluation](INDEPENDENT_RESULTS.md) and [BM25S results](COMPETITOR_RESULTS.md) for comparisons, uncertainty and known losses.

## Mathematica external transfer

[Completed CI](https://github.com/Afloat16/research-to-fix/actions/runs/45366934273) · [artifact](https://github.com/Afloat16/research-to-fix/actions/runs/45366934273/artifacts/14906654892) · [predeclared protocol](TRANSFER_V12_PROTOCOL.md). The run used the frozen method configuration at commit `74ba0309601b5fdfd8ee642d90c5826ff9087ded`. Full BEIR CQADupStack Mathematica corpus (16,705 documents, 804 queries, binary positive qrels); no tuning. Dataset revision URLs and original/normalized digests are in the committed snapshot. Actual BM25S 0.2.14 and rank-bm25 0.2.2 are installed benchmark-only; SQLite 3.46.1, Linux CPython 3.13.18. All eight methods use top-10, fixed title/body bounds and exclude self IDs.

| Method | nDCG@10 | MRR@10 | Recall@10 | Hit@10 | Build (s) | P50 (ms) | P95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| precision_field4 | 0.2366 | 0.2313 | 0.3350 | 0.4030 | 13.96 | 7.793 | 19.081 |
| v1_contextual | 0.2389 | 0.2304 | 0.3420 | 0.4017 | 11.26 | 6.238 | 15.355 |
| v1_bm25 | 0.2113 | 0.2084 | 0.2946 | 0.3532 | 2.95 | 4.793 | 14.230 |
| sqlite_unicode4 | 0.2157 | 0.2145 | 0.2979 | 0.3607 | 1.75 | 14.183 | 33.329 |
| sqlite_porter | 0.2256 | 0.2249 | 0.3108 | 0.3694 | 1.77 | 17.919 | 36.613 |
| bm25s_native | 0.2264 | 0.2249 | 0.3157 | 0.3744 | 5.89 | 0.236 | 0.734 |
| bm25s_matched | 0.2294 | 0.2234 | 0.3279 | 0.3818 | 5.63 | 0.176 | 0.687 |
| rank_bm25_matched | 0.2235 | 0.2183 | 0.3130 | 0.3719 | 5.01 | 20.437 | 37.458 |

| Comparator (Precision Field minus comparator) | Mean delta | Pointwise paired 95% interval | Win/tie/loss queries | Interpretation |
| --- | ---: | ---: | ---: | --- |
| v1_contextual | -0.00227 | [-0.01133, 0.00670] | 101/602/101 | Inconclusive |
| v1_bm25 | 0.02530 | [0.01433, 0.03596] | 138/578/88 | Positive |
| sqlite_unicode4 | 0.02094 | [0.01086, 0.03100] | 127/592/85 | Positive |
| sqlite_porter | 0.01099 | [-0.00122, 0.02327] | 128/579/97 | Inconclusive |
| bm25s_native | 0.01022 | [-0.00058, 0.02121] | 113/590/101 | Inconclusive |
| bm25s_matched | 0.00716 | [-0.00323, 0.01759] | 112/594/98 | Inconclusive |
| rank_bm25_matched | 0.01312 | [0.00227, 0.02416] | 127/589/88 | Positive |

2,000 fixed-seed paired query-bootstrap resamples per comparison; pointwise intervals are descriptive, not multiplicity-adjusted. Precision Field has positive intervals against old BM25, Unicode 4 and rank-bm25 Matched. Contextual has the highest measured nDCG and recall, BM25S has substantially lower raw query latency, and SQLite has cheaper index builds. The observed score advantage over BM25S is inconclusive. No universal winner is established.

### Exact recall on the same real queries

| Measure | Old full explanation | New bounded explanation |
| --- | ---: | ---: |
| P50 (ms) | 35.357 | 7.238 |
| P95 (ms) | 120.982 | 20.894 |

**4.88× P50; 804/804 identical count, scores, IDs and explanations.** Single paired pass with full explanation first, prepared tokens, warm index. Order effects possible; no index build, raw query parsing or repair-success claim. Together with the 288 generated workload-query pairs, 1,092 exact comparisons. This is not 1,092 independent real-world queries.

```bash
python -m pip install -r benchmarks/requirements-bm25s.txt rank-bm25==0.2.2
python benchmarks/independent_data.py --dataset mathematica --output /tmp/r2f-mathematica
python benchmarks/transfer_v12.py --data /tmp/r2f-mathematica --output /tmp/transfer.json
```
