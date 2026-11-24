#!/usr/bin/env python3
"""Paired offline measurement of public provider scheduling under mock latency."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "research-to-fix" / "scripts"))
import public_discovery as d
import research_workflow as w

PROBLEM = {"symptom": "Attention GPU memory grows", "task": "efficient attention",
           "concepts": ["exact attention"], "alternative_concepts": ["block sparse attention"]}


def transport(url, provider):
    # Identical artificial I/O delay for each API request. Does not contact
    # a provider, measure real-world network latency, or use real metadata.
    time.sleep(.04)
    if provider == "arxiv":
        return b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
    if provider.startswith("github"):
        return b'{"items":[]}'
    if provider == "crossref":
        return b'{"message":{"items":[]}}'
    if provider == "semantic_scholar":
        return b'{"data":[]}'
    if provider == "openalex":
        return b'{"results":[]}'
    if provider == "dblp":
        return b'{"result":{"hits":{}}}'
    return b'[]'


def run():
    plan = w.make_plan(PROBLEM, 24)
    counts = {}
    for schedule in ("plan", "balanced"):
        reserved = d.reserve_queries(plan["queries"], 6, schedule)
        counts[schedule] = len({d.GROUPS[row["provider"]] for row in reserved})
    timings = {1: [], 3: []}
    expected = None
    for repeat in range(5):
        for workers in ((1, 3) if repeat % 2 == 0 else (3, 1)):
            start = time.perf_counter()
            report = d.discover(plan, True, 6, transport=transport, workers=workers, schedule="balanced")
            timings[workers].append((time.perf_counter() - start) * 1000)
            comparable = [{k: v for k, v in row.items() if k != "searched_at"} for row in report["searches"]]
            if expected is None:
                expected = comparable
            if report["requests"] != 6 or expected != comparable:
                raise RuntimeError("provider scheduling parity failure")
    sequential = statistics.median(timings[1])
    parallel = statistics.median(timings[3])
    return {"scope": "mock_40ms_transport_per_request_not_live_latency",
            "requests": 6, "repeats": 5, "provider_groups_plan": counts["plan"],
            "provider_groups_balanced": counts["balanced"],
            "sequential_median_ms": round(sequential, 3), "three_workers_median_ms": round(parallel, 3),
            "speedup": round(sequential / parallel, 3), "identical_search_records_excluding_timestamps": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run()
    w.write_json(result, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
