# Post-holdout competitor diagnostic

After the frozen holdout results were opened, predeclare a separate diagnostic (not an additional blind experiment): use the same full SciFact and NASA corpora, queries, binary qrels, field caps, Top-10 and self-ID exclusion. Compare frozen Precision Field, v1 Contextual, native SQLite Porter and selected SQLite Unicode4 against [BM25S](https://github.com/xhluca/bm25s) 0.2.14. BM25S uses its actual Lucene scoring method with k1=1.5 and b=.75. Both BM25S inputs duplicate the capped title as v1 Contextual does; `bm25s_native` uses BM25S English stopwords and tokenizer plus R2F English stem normalization; `bm25s_matched` uses R2F stemmed technical tokens. Both use distinct query terms and stable score/ID Top-K; no positive qrels enter ranking. Native sparse scores are obtained from the installed package, not reimplemented. Runtime includes tokenization and deterministic Top-K; exclude download/import. No winner-based tuning or changes to the frozen evaluation. Record all nDCG/Recall/MRR/Hit, build/p50/p95/total times and pointwise paired intervals. The pinned benchmark-only dependencies are not production requirements.

```bash
python -m pip install --only-binary=:all: -r benchmarks/requirements-bm25s.txt
python benchmarks/independent_data.py --dataset scifact --output /tmp/scifact-new
python benchmarks/compare_bm25s.py --data /tmp/scifact-new --output /tmp/scifact-bm25s.json
```

We will report stronger competitor speed/quality where applicable. The dataset has already been viewed, so do not use these numbers to assert independent generalization of a new ranker. No dense or agent evaluation claim.
