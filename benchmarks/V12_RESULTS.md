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
python benchmarks/relative_recall.py
python -m unittest discover -s tests -v
node docs/figures/render-v12.cjs --check
```

The [frozen Mathematica transfer protocol](TRANSFER_V12_PROTOCOL.md) defines a separate retrieval comparison. The [multi-arm evaluation protocol](AGENT_COMPARISON_PROTOCOL.md) and coverage audit are engineering contributions, not demonstrated gains in agent repair accuracy. See the prior [four-corpus evaluation](INDEPENDENT_RESULTS.md) and [BM25S results](COMPETITOR_RESULTS.md) for comparisons, uncertainty and known losses.
