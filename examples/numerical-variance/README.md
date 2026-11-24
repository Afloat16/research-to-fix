# Numerical variance repair: three comparable alternatives

A population-variance implementation based on raw moments can return an inaccurate or negative result when values cluster around a large offset. This experiment compares **four** methods on the same seeded inputs and integer-arithmetic oracle, including a failing baseline.

| Method | Basis | Tradeoff to measure |
| --- | --- | --- |
| Raw moments | Baseline | Fast, but cancellation can destroy small variance |
| Shifted two-pass + `math.fsum` | Local implementation guided by [NumPy's documented variance definition](https://numpy.org/doc/stable/reference/generated/numpy.var.html) | Requires replayable input; avoids subtraction of large nearly equal squares |
| One-pass corrected moment | Locally derived recurrence; [Welford 1962](https://doi.org/10.1080/00401706.1962.10490022) is a bibliographic lead, not a claimed full-text review | Incremental state; floating-point rounding remains |
| `statistics.pvariance` | [Python's documented population-variance API](https://docs.python.org/3/library/statistics.html#statistics.pvariance) | Library behavior and overhead depend on interpreter/input |

Run from repository root with Python 3.10+; no dependencies or downloads:

```bash
python examples/numerical-variance/compare_methods.py --output /tmp/r2f-variance-new
python skills/research-to-fix/scripts/solution_compare.py --comparison /tmp/r2f-variance-new/comparison.json
```

Five seeds, 8,192 exactly representable values per seed, independent integer-moment oracle, relative-error threshold `1e-5`, simple/constant/empty-input regression checks. Median timing from three calls per seed, separate `tracemalloc` run, input allocation excluded. The harness rotates candidate order and records all five per-candidate measurements. The original-error check must fail for the baseline and pass for all three alternatives. The comparator preserves tradeoffs; it does not invent a winner from incomparable units. These are local Python experiments, not general NumPy/GPU performance measurements, and do not assert that the cited paper or any external project has been reproduced.

For a fresh research task, the agent should first generate a public fingerprint, run the authorized searches, review original sources, and map the candidate mechanisms to local code; this fixed example only demonstrates the final measured-comparison phase. The external source statements are narrow, and the two-pass/online code is independent, not copied from external implementations.
