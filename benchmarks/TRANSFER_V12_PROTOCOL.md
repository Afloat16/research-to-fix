# v1.2.0 transfer protocol (predeclared before outcomes)

**One new full external corpus:** BEIR CQADupStack Mathematica, 16,705 documents, 804 test queries, selected because it covers mathematical programming and technical troubleshooting. All data from the revision-pinned Tevatron representation and official BEIR qrels, as in the previous independent protocol. Record original and normalized SHA-256 digests. No corpus text committed. Source: [BEIR dataset card](https://huggingface.co/datasets/BeIR/cqadupstack), CC BY-SA 4.0.

**Frozen comparators:** existing v1.1.0 Precision Field (unchanged scorer, title 4/body 1), v1 Contextual, v1 BM25, SQLite FTS5 Unicode title weight 4, SQLite Porter title weight 2, actual BM25S 0.2.14 native and R2F-stem-matched analyzers, actual rank-bm25 0.2.2 BM25Okapi with the same matched stem analyzer. Fixed top-10, title/body bounds, binary positive qrels, self-ID excluded and deterministic ID tie-breaking. Do not select, train or tune on this dataset. All methods, including losses, reported.

Primary metric mean nDCG@10; secondary MRR/recall/hit@10, measured build and p50/p95 query time, pointwise paired 95% bootstrap intervals versus each comparator. The comparisons are descriptive; do not claim a multiplicity-adjusted global win. The bounded explanation algorithm is checked separately on the same corpus for exact old/new counts, scores, IDs and terms, not a change to ranking quality. External libraries are benchmark-only. No end-to-end repair, model or live research evaluation.

```bash
python -m pip install -r benchmarks/requirements-bm25s.txt rank-bm25==0.2.2
python benchmarks/independent_data.py --dataset mathematica --output /tmp/r2f-mathematica
python benchmarks/transfer_v12.py --data /tmp/r2f-mathematica --output /tmp/transfer.json
```

The new dataset is separate from the prior four external corpora. A failed download or dependency installation is a blocked experiment, not a zero score; record failures and do not substitute a dataset after viewing results.
