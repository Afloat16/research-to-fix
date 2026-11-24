# Performance evidence / 实测性能

## Architectural decision

Keep the default BM25 ranking contract and existing security/corpus limits. Use a low-startup scan for one-shot queries and a validated in-memory snapshot for repeated queries. Precompute posting contributions into compact arrays, use bounded heap top-k for rank-only evaluations, preserve Python's built-in sum behavior, and retain deterministic tie-breaking. The initial indexed iteration failed exact equivalence on Python 3.12+ ([failed checks](https://github.com/Afloat16/research-to-fix/actions/runs/45338466294)); it was corrected before subsequent success. No hidden persistent cache or validation bypass.

## Measured scale results

GitHub Actions [run 45338904509](https://github.com/Afloat16/research-to-fix/actions/runs/45338904509), commit `65f7106a068b128e33c5351918e7b93faf59ae4b`, Python 3.13, Linux, generated workloads:

| Workload | Baseline | Improved | Observation |
| --- | ---: | ---: | --- |
| 120 case files, 32 queries; median of 3 repetitions | 608.261 ms repeated one-shot | 21.909 ms batch | 27.764x; identical reports |
| 5,000-document index retained Python allocations | 22,013,956 bytes tuple postings | 5,184,748 bytes packed postings | 4.246x smaller (~76.4% reduction) |
| 5,000 documents, 64 sparse queries | full scanner | packed index | 120.262x warm query speedup, exact top-10 scores |

The workloads use generated data; memory excludes input corpus. These are paired observations, not guarantees, and the warm retrieval ratio excludes index construction. The complete batch timing includes file reads, JSON validation, tokenization and retrieval.

## Ranking iteration

The fixed source-linked public duplicate-title sample exposed poor English inflection handling: the pre-stemming iteration's BM25 and technical MRR@5 were 0.509259 and Recall@5 0.611111, versus SQLite FTS5 Porter 0.740741 and 0.833333 ([run 45339431980](https://github.com/Afloat16/research-to-fix/actions/runs/45339431980)). That motivated independently implemented English normalization and exact/stem channel experiments, rather than claiming the prior algorithm was universally best.

[Run 45339589743](https://github.com/Afloat16/research-to-fix/actions/runs/45339589743), commit `6103cdedca0dcb09b37c50b36449bb163de39fa5`, fixed top-5:

| Method | Synthetic MRR | Synthetic Recall | Public title MRR | Public title Recall |
| --- | ---: | ---: | ---: | ---: |
| Legacy BM25 scan | 0.940625 | 0.987500 | 0.509259 | 0.611111 |
| Indexed BM25 | 0.940625 | 0.987500 | 0.509259 | 0.611111 |
| Technical | 0.966667 | 0.987500 | 0.509259 | 0.611111 |
| Stemmed | 0.987500 | 1.000000 | 0.722222 | 0.833333 |
| Hybrid | 1.000000 | 1.000000 | 0.592593 | 0.722222 |
| SQLite FTS5 | 0.868750 | 0.887500 | 0.509259 | 0.611111 |
| SQLite FTS5 Porter | 0.893750 | 0.900000 | 0.740741 | 0.833333 |

Hybrid leads this synthetic sample, but stemmed is much stronger on actual English issue titles and still slightly behind SQLite Porter in MRR. All modes abstained on the three unrelated synthetic queries. This is why ranking choices remain explicit and the default remains compatible rather than selecting a universal winner from two small development sets. Later phrase-aware results are available in performance workflow reports.

See [benchmark protocol](../benchmarks/README.md) for data provenance, external BEIR reproduction and limitations. No external BEIR or end-to-end SWE-bench success rate is claimed.
