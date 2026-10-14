"""在三个规模的 float 流上核对结果和可比较的峰值内存。"""

import json
import tracemalloc

from metrics import summarize


def main():
    rows = []
    for size in (10_000, 100_000, 1_000_000):
        peaks = []
        for _ in range(3):
            tracemalloc.start()
            try:
                result = summarize(float(i) for i in range(size))
                _current, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            assert result == {"count": size, "mean": (size - 1) / 2}, result
            assert peak <= 16 * 1024, peak
            peaks.append(peak)
        rows.append({"size": size, "peaks_bytes": peaks})
    all_peaks = [peak for row in rows for peak in row["peaks_bytes"]]
    assert max(all_peaks) - min(all_peaks) <= 4 * 1024, all_peaks
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
