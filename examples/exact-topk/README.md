# Exact top-k vector selection — matched local experiment

Compare three independently implemented mechanisms, **full sort**, **bounded heap selection**, and **blockwise exact merge**, using identical squared Euclidean distances and stable index tie-breaking. The small-k heap idea follows [Python's documented nsmallest API](https://docs.python.org/3/library/heapq.html#heapq.nsmallest); the [Faiss index guide](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index) motivates exact exhaustive and partitioned search. No Faiss code is copied or executed, and this is not a Faiss speed comparison.

```bash
python examples/exact-topk/compare_methods.py --output /tmp/r2f-exact-topk
```

The protocol is locked before measurements, with five paired seeds, 8,192 integer vectors per seed, 16 dimensions and k=10. An independent integer distance oracle checks exact output including ties. Timing and peak traced Python allocations are separate. The same input allocation is excluded from all candidates. The comparator uses conservative paired dominance and practical margins; it reports tradeoffs instead of forcing a winner. The baseline is valid, so a faster or lower-memory alternative must still pass every correctness check. Re-run on target hardware before adopting any result.

中文：全量排序、堆选择、分块精确合并三种方案，先锁定实验协议，再实测五组同条件输入、精确输出及边界条件，并比较耗时与额外内存，不把此 Python 样例宣称为对 Faiss 或其他向量库的性能胜利。
