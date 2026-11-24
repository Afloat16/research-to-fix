# Exact attention: research-led workspace comparison

This example explores the same problem as memory-efficient attention papers: storing an entire score matrix grows expensive with sequence length. The local experiment implements four mathematically equivalent forward-only algorithms in standard-library Python, without importing GPU kernels or copying third-party source code.

Bibliographic leads: [Self-attention Does Not Need O(n²) Memory](https://arxiv.org/abs/2112.05682), [FlashAttention](https://arxiv.org/abs/2205.14135), [Online normalizer calculation for softmax](https://arxiv.org/abs/1805.02867). Their abstracts motivate the problem; the local derivations and measurements are separate. No full-text review or reproduction of their reported GPU speedups is claimed.

| Candidate | Workspace mechanism |
| --- | --- |
| Full score matrix | Materialize all score rows; stable softmax |
| Row streaming | Store one query's score row at a time |
| Block summary merge | Maintain the maximum, normalizer and weighted value sum across blocks |
| Per-key online recurrence | Update a stable weighted sum for each key |

Run in the repository root:

```bash
python examples/exact-attention/compare_attention.py --output /tmp/r2f-attention-new
python skills/research-to-fix/scripts/solution_compare.py --comparison /tmp/r2f-attention-new/comparison.json --protocol-lock /tmp/r2f-attention-new/protocol-lock.json --design-lock /tmp/r2f-attention-new/design-lock.json
```

The harness writes its protocol, candidate design and separate hash locks **before** running five seeded paired experiments on 96 queries × 192 keys, query/key dimension 16 and value dimension 8. A separate direct stable-softmax oracle checks every result at maximum absolute error ≤ 1e-10. Additional checks exercise extreme logits, causal behavior, uniform weights and invalid empty input. Timing uses three calls per seed, peak allocation uses a separate tracemalloc pass excluding the preallocated inputs but including returned output. Candidate order rotates; all-pairs Pareto and fixed resolution bins avoid assuming tiny numerical differences establish superiority. No claims about CUDA, training/backpropagation, long-context model quality, or GPU/NumPy speed are made. The full measurements and failed checks (if any) remain in CI artifacts.
