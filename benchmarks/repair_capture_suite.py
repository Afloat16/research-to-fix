#!/usr/bin/env python3
"""Controlled repair-candidate stress suite with actual frozen subprocess tests.

The fixtures deliberately include incomplete fixes that pass the original
symptom check but violate a separate invariant. This is not a model trial,
an external bug dataset, or a representative estimate of false acceptance.
"""
import argparse
import json
from pathlib import Path
import platform
import sys
import tempfile
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/research-to-fix/scripts"))
import case_bundle as bundle
import unittest_capture as capture


def simple(name, baseline, narrow, fixed, methods):
    tests = "import unittest\nfrom subject import solve\n\nclass Checks(unittest.TestCase):\n" + methods
    return {"id": name, "source": "subject.py", "baseline": baseline,
            "narrow": narrow, "fixed": fixed, "tests": {"test_subject.py": tests},
            "modules": ["test_subject"], "original": ["test_subject.Checks.test_original"]}


def fixtures():
    example = ROOT / "examples/streaming-metrics"
    return [
        {"id": "streaming_iterable", "source": "metrics.py",
         "baseline": """def summarize(values):
    total = sum(values)
    count = sum(1 for _ in values)
    return {"count": count, "mean": total / count}
""",
         "narrow": """def summarize(values):
    values = list(values)
    return {"count": len(values), "mean": sum(values) / len(values)}
""",
         "fixed": (example / "metrics.py").read_text(encoding="utf-8"),
         "tests": {name: (example / name).read_text(encoding="utf-8")
                   for name in ("test_metrics.py", "test_metrics_streaming.py")},
         "modules": ["test_metrics", "test_metrics_streaming"],
         "original": ["test_metrics.MetricsTests.test_stream"]},
        simple("exception_contract",
               "def solve(a, b):\n    return a / b\n",
               "def solve(a, b):\n    if not b: raise ValueError('zero')\n    return abs(a / b)\n",
               "def solve(a, b):\n    if not b: raise ValueError('zero')\n    return a / b\n",
               """    def test_original(self):
        with self.assertRaises(ValueError): solve(1, 0)
    def test_signed(self):
        self.assertEqual(solve(-6, 2), -3)
    def test_normal(self):
        self.assertEqual(solve(8, 2), 4)
"""),
        simple("binary_search_tie",
               """def solve(xs, target):
    left, right = 0, len(xs) - 1
    while left <= right:
        mid = (left + right) // 2
        if xs[mid] == target: return mid
        if xs[mid] < target: left = mid + 1
        else: right = mid - 1
    return -1
""",
               "def solve(xs, target):\n    return xs.index(target)\n",
               """from bisect import bisect_left
def solve(xs, target):
    i = bisect_left(xs, target)
    return i if i < len(xs) and xs[i] == target else -1
""",
               """    def test_original(self):
        self.assertEqual(solve([1, 2, 2, 2, 3], 2), 1)
    def test_absent(self):
        self.assertEqual(solve([1, 3, 4], 2), -1)
    def test_empty(self):
        self.assertEqual(solve([], 4), -1)
    def test_distinct(self):
        self.assertEqual(solve([1, 2, 3], 3), 2)
"""),
        simple("variance_cancellation",
               """def solve(values):
    xs = list(values)
    mean = sum(xs) / len(xs)
    return sum(x*x for x in xs)/len(xs) - mean*mean
""",
               """import math
def solve(values):
    xs = list(values)
    mean = math.fsum(xs) / len(xs)
    return math.fsum((x-mean)**2 for x in xs) / len(xs)
""",
               """import statistics
def solve(values):
    return statistics.pvariance(values)
""",
               """    def test_original(self):
        self.assertAlmostEqual(solve([1e12-1, 1e12, 1e12+1]), 2/3)
    def test_empty(self):
        with self.assertRaises(ValueError): solve([])
    def test_single(self):
        self.assertEqual(solve([12]), 0)
    def test_generator(self):
        self.assertAlmostEqual(solve(iter([0, 2, 4])), 8/3)
"""),
        simple("rank_tie_order",
               "def solve(rows, k):\n    return sorted(rows, key=lambda x: -x[1])[:k]\n",
               "def solve(rows, k):\n    return sorted(rows, key=lambda x: x[0])[:k]\n",
               "def solve(rows, k):\n    return sorted(rows, key=lambda x: (-x[1], x[0]))[:k]\n",
               """    def test_original(self):
        self.assertEqual(solve([('z', 2), ('a', 2)], 1), [('a', 2)])
    def test_score_precedence(self):
        self.assertEqual(solve([('a', 1), ('z', 3)], 1), [('z', 3)])
    def test_empty(self):
        self.assertEqual(solve([], 5), [])
    def test_zero(self):
        self.assertEqual(solve([('z', 1)], 0), [])
"""),
        simple("csv_empty_fields",
               "def solve(text):\n    return text.split(',')\n",
               "import csv\ndef solve(text):\n    return [x for x in next(csv.reader([text])) if x]\n",
               "import csv\ndef solve(text):\n    return next(csv.reader([text]))\n",
               """    def test_original(self):
        self.assertEqual(solve('"a,b",c'), ['a,b', 'c'])
    def test_empty_fields(self):
        self.assertEqual(solve('a,,b,'), ['a', '', 'b', ''])
    def test_escaped_quote(self):
        self.assertEqual(solve('"a""b",c'), ['a"b', 'c'])
    def test_plain(self):
        self.assertEqual(solve('a,b'), ['a', 'b'])
"""),
        simple("cache_nested_alias",
               "def solve(cache, key):\n    return cache[key]\n",
               "def solve(cache, key):\n    return list(cache[key])\n",
               "import copy\ndef solve(cache, key):\n    return copy.deepcopy(cache[key])\n",
               """    def test_original(self):
        cache = {'k': [1]}
        solve(cache, 'k').append(2)
        self.assertEqual(cache['k'], [1])
    def test_nested(self):
        cache = {'k': [[1]]}
        solve(cache, 'k')[0].append(2)
        self.assertEqual(cache['k'], [[1]])
    def test_empty(self):
        self.assertEqual(solve({'k': []}, 'k'), [])
    def test_missing(self):
        with self.assertRaises(KeyError): solve({}, 'missing')
"""),
    ]


def evaluate():
    rows = []
    with tempfile.TemporaryDirectory(prefix="r2f-controlled-repair-") as tmp:
        root = Path(tmp)
        for task in fixtures():
            task_dir = root / task["id"]
            task_dir.mkdir()
            before, tests = task_dir / "before", task_dir / "tests"
            before.mkdir()
            tests.mkdir()
            (before / task["source"]).write_text(task["baseline"], encoding="utf-8")
            for name, body in task["tests"].items():
                (tests / name).write_text(body, encoding="utf-8")
            for variant, key in (("unchanged", "baseline"), ("narrow", "narrow"), ("fixed", "fixed")):
                after = task_dir / variant
                after.mkdir()
                (after / task["source"]).write_text(task[key], encoding="utf-8")
                spec = {"schema_version": 1, "case_id": task["id"] + "-" + variant,
                        "summary": "Controlled " + task["id"] + " repair candidate",
                        "component": task["id"], "hypothesis": "Preserve original and regression behaviors.",
                        "implementation_files": [task["source"]], "comparison_files": sorted(task["tests"]),
                        "test_modules": task["modules"], "original_test_ids": task["original"],
                        "timeout_seconds": 20}
                lock = capture.freeze(spec, before, after, tests)
                destination = task_dir / (variant + "-capture")
                start = perf_counter_ns()
                result = capture.record(lock, before, after, tests, destination, approved=True,
                                        expected_digest=bundle.digest(capture.canonical(lock)))
                elapsed = (perf_counter_ns() - start) / 1e6
                case = json.loads((destination / "case.json").read_bytes())
                left, right = case["validation"]["runs"]
                original_before = any(left["test_results"][name] in ("fail", "error") for name in task["original"])
                symptom_accept = original_before and all(right["test_results"][name] == "pass" for name in task["original"])
                full_accept = result["declared_status"] == "solved"
                if not original_before or symptom_accept != (variant != "unchanged") or full_accept != (variant == "fixed"):
                    raise RuntimeError("Controlled repair classification changed: " + task["id"] + "/" + variant)
                if not (result["capture_audit"]["capture_consistency"] and result["capture_audit"]["plan_consistency"]):
                    raise RuntimeError("Capture audit failed")
                rows.append({"task": task["id"], "variant": variant, "before": left["test_results"],
                             "after": right["test_results"], "before_exit": left["exit_code"],
                             "after_exit": right["exit_code"], "symptom_only_accept": symptom_accept,
                             "full_suite_accept": full_accept, "capture_audit_passed": True,
                             "transition_findings": result["transition_findings"],
                             "plan_sha256": result["plan_sha256"], "manifest_sha256": result["manifest_sha256"],
                             "actual_test_outcomes": result["capture_audit"]["test_outcomes_audited"],
                             "record_ms": elapsed})
    return {"scope": "Controlled, deliberately designed local Python repair candidates; no model or external repair-rate claim",
            "python": platform.python_version(), "platform": platform.platform(),
            "tasks": len({row["task"] for row in rows}), "candidate_comparisons": len(rows),
            "subprocess_test_runs": len(rows) * 2,
            "actual_test_outcomes": sum(row["actual_test_outcomes"] for row in rows),
            "symptom_only_accepted": sum(row["symptom_only_accept"] for row in rows),
            "full_suite_accepted": sum(row["full_suite_accept"] for row in rows),
            "narrow_candidates_rejected_by_full_suite": sum(row["symptom_only_accept"] and not row["full_suite_accept"] for row in rows),
            "audited_bundles": sum(row["capture_audit_passed"] for row in rows), "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate()
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print("REPAIR_CAPTURE_SUMMARY", json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
