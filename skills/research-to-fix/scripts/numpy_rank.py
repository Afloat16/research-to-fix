"""Optional NumPy score-only acceleration for large immutable posting indexes.

The regular CLI and all default paths remain standard-library-only.
Only instantiate explicitly with an existing PostingIndex/FieldIndex, after
installing NumPy. Keep the underlying postings immutable while using this
wrapper. The scratch space is O(number of documents), not O(matches).
"""
import sys


class NumpyRanker:
    """Sparse posting traversal with dense float64 accumulators and exact ties.

    CPython 3.10/3.11 sum(float) accumulates left to right. CPython
    3.12–3.14 uses a compensated sum. Traverse the same sorted distinct terms
    and preserve this arithmetic for finite positive BM25 contributions.
    Explain requests use the normal index path. Other interpreters are not
    accepted; no silent approximation or default dependency.
    """

    def __init__(self, index):
        if sys.implementation.name != "cpython" or not (3, 10) <= sys.version_info[:2] <= (3, 14):
            raise RuntimeError("Optional vector ranking supports CPython 3.10–3.14")
        import numpy as np
        self.np = np
        self.index = index
        self.ids = index.ids
        self.compensated = sys.version_info >= (3, 12)
        self.tie_rank = np.empty(len(self.ids), dtype=np.intp)
        for rank, position in enumerate(sorted(range(len(self.ids)), key=self.ids.__getitem__)):
            self.tie_rank[position] = rank
        self.postings = {}
        for term, (ids, values) in index.postings.items():
            # Read-only views; index arrays remain the authoritative storage.
            positions = np.frombuffer(ids, dtype=np.dtype("=u" + str(ids.itemsize)))
            weights = np.frombuffer(values, dtype=np.float64)
            positions.flags.writeable = False
            weights.flags.writeable = False
            self.postings[term] = positions, weights

    def rank(self, query_terms, limit=None, explain=True):
        if explain:
            return self.index.rank(query_terms, limit, True)
        if limit is not None and (type(limit) is not int or limit < 0):
            raise ValueError("limit must be a nonnegative integer or None")
        if limit == 0 or not self.ids:
            return []
        np = self.np
        hi = np.zeros(len(self.ids), dtype=np.float64)
        lo = np.zeros_like(hi) if self.compensated else None
        for term in sorted(set(query_terms)):
            posting = self.postings.get(term)
            if posting is None:
                continue
            ids, values = posting
            old = hi[ids]
            updated = old + values
            if lo is not None:
                # All posting contributions are positive finite floats.
                # These explicitly separated operations preserve CPython's
                # Neumaier update order; no BLAS, reductions or float32.
                lo[ids] += np.where(old >= values, (old - updated) + values,
                                    (values - updated) + old)
            hi[ids] = updated
        if lo is not None:
            hi += lo
        if not np.all(np.isfinite(hi)):
            return self.index.rank(query_terms, limit, False)
        positive = np.flatnonzero(hi > 0)
        if limit is not None and len(positive) > limit:
            boundary = np.partition(hi[positive], len(positive) - limit)[len(positive) - limit]
            positive = positive[hi[positive] >= boundary]
        order = positive[np.lexsort((self.tie_rank[positive], -hi[positive]))]
        if limit is not None:
            order = order[:limit]
        return [(float(hi[i]), self.ids[int(i)], []) for i in order]
