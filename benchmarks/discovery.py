#!/usr/bin/env python3
"""Replay public paper/code metadata, evaluate reranking, coverage and pairing."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import statistics
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "research-to-fix" / "scripts"))
import research_workflow as w
import research_case as core
from retrieval import SQLiteBaseline

DATASET = ROOT / "benchmarks" / "datasets" / "algorithm_discovery_v1.json"
K = 6


def metrics(ranked, relevant, pairs, families):
    ranked = ranked[:K]
    hits = set(ranked) & relevant
    ideal = sum(1 / math.log2(i + 2) for i in range(min(K, len(relevant))))
    dcg = sum(1 / math.log2(i + 2) for i, key in enumerate(ranked) if key in relevant)
    return {"mrr": next((1 / (i + 1) for i, key in enumerate(ranked) if key in relevant), 0),
            "recall": len(hits) / len(relevant), "precision": len(hits) / K,
            "ndcg": dcg / ideal, "paper_and_code": float({families[key] for key in hits} >= {"paper", "code"}),
            "complete_pair_recall": sum(set(pair) <= hits for pair in pairs) / len(pairs)}


def summarize(values):
    return {key: round(statistics.mean(row[key] for row in values), 6) for key in values[0]}


TRANSFER = ROOT / "benchmarks" / "datasets" / "algorithm_transfer_v1.json"


def benchmark(dataset_path=DATASET):
    raw = dataset_path.read_bytes()
    dataset = json.loads(raw)
    documents = list(dataset["documents"])
    background_sha256 = None
    if dataset_path == TRANSFER:
        background = DATASET.read_bytes()
        background_sha256 = hashlib.sha256(background).hexdigest()
        documents.extend(json.loads(background)["documents"])
    originals = {row["id"]: row for row in documents if not row.get("duplicate_type")}
    expected_identities, expected_observations = (56, 68) if dataset_path == TRANSFER else (32, 44)
    if len(originals) != expected_identities or len(documents) != expected_observations:
        raise RuntimeError("Fixture size changed")
    # Baselines use the same unique source identities and same title/snippet
    # text. No ranking method is given relevance labels.
    corpus = [{"id": key, "title": row["title"], "text": row["snippet"]}
              for key, row in sorted(originals.items())]
    index = core.PostingIndex([(row["id"], core.ranking_counts(row["title"],
                              row["title"] + "\n" + row["text"], "stemmed")) for row in corpus])
    sqlite = SQLiteBaseline(corpus, porter=True)
    family = {key: w.KIND_FAMILY[row["kind"]] for key, row in originals.items()}
    canonical_to_id = {w.canonical_url(row["url"]): row["id"] for row in documents}
    all_metrics, per_query, timings = {}, [], []
    names = ("fixed_order", "stemmed_bm25", "sqlite_porter", "facet_rank", "evidence_shortlist", "intent_fusion")
    formulations = ("symptom", "mechanism", "bilingual") if dataset_path == TRANSFER else ("symptom", "mechanism")
    for task in dataset["tasks"]:
        relevant = set(task["relevant"])
        if not relevant <= set(originals):
            raise RuntimeError("Unknown qrels")
        for formulation in formulations:
            problem = dict(task["bilingual_problem"] if formulation == "bilingual" else task["problem"])
            if formulation == "symptom":
                problem.update(concepts=[], alternative_concepts=[], aliases=[])
            plan = w.make_plan(problem, 16)
            qids = {q["kind"]: q["id"] for q in plan["queries"]}
            rows = []
            for row in documents:
                # A fixture replay is not an executed provider query.
                if row["kind"] not in qids:
                    raise RuntimeError("Missing kind from plan")
                rows.append({**{k: v for k, v in row.items() if k not in ("id", "duplicate_type")},
                             "query_id": qids[row["kind"]], "origin": "host"})
            start = perf_counter_ns()
            report = w.rank_results(plan, [{"results": rows}], K)
            timings.append((perf_counter_ns() - start) / 1e6)
            facet = w.rank_results(plan, [{"results": rows}], K, "facet")
            fusion = w.rank_results(plan, [{"results": rows}], K, "fusion")
            if report["duplicates_collapsed"] != expected_observations - expected_identities or report["unique_identities"] != expected_identities:
                raise RuntimeError("Identity grouping regression")
            def original_id(row):
                result = {canonical_to_id[key[4:]] for key in row["identities"]
                          if key.startswith("url:") and key[4:] in canonical_to_id}
                if len(result) != 1:
                    raise RuntimeError("Wrong identity group")
                return result.pop()
            text = " ".join([problem.get("symptom", ""), problem.get("task", ""),
                             problem.get("component", ""), *problem.get("concepts", []),
                             *problem.get("alternative_concepts", []), *problem.get("aliases", [])])
            # Fixed pseudo-provider order: a deterministic non-relevance baseline,
            # not a measured search-engine/provider ranking.
            order = sorted(originals, key=lambda key: hashlib.sha256(("r2f-discovery-v1:" + key).encode()).digest())[:K]
            bm25 = [identifier for _, identifier, _ in index.rank(core.ranking_tokens(text, "stemmed"), K, False)]
            ranked = {"fixed_order": order, "stemmed_bm25": bm25,
                      "sqlite_porter": sqlite.search(text, K),
                      "facet_rank": [original_id(row) for row in facet["ranked"][:K]],
                      "evidence_shortlist": [original_id(row) for row in report["shortlist"]],
                      "intent_fusion": [original_id(row) for row in fusion["shortlist"]]}
            values = {name: metrics(ranked[name], relevant, task["pairs"], family) for name in names}
            for name in names:
                all_metrics.setdefault((name, formulation), []).append(values[name])
            per_query.append({"task": task["id"], "formulation": formulation,
                              "rankings": ranked, "metrics": values,
                              "unique_identities": report["unique_identities"],
                              "duplicates_collapsed": report["duplicates_collapsed"]})
    sqlite.db.close()
    report = {name: {"overall": summarize([row for form in formulations for row in all_metrics[(name, form)]]),
                     **{form: summarize(all_metrics[(name, form)]) for form in formulations}}
              for name in names}
    old = core.make_queries(dataset["tasks"][0]["problem"]["symptom"], max_queries=8)
    new = w.make_plan(dataset["tasks"][0]["problem"], 8)
    return {"dataset": dataset["name"], "dataset_sha256": hashlib.sha256(raw).hexdigest(),
            "tasks": len(dataset["tasks"]), "queries": len(per_query), "unique_sources": len(originals),
            "background_sha256": background_sha256,
            "observations": len(documents), "k": K, "methods": report,
            "planner_comparison": {"legacy_first_8_sources": sorted({row["source"] for row in old["queries"]}),
                                   "new_first_8_sources": sorted({row["source"] for row in new["queries"]}),
                                   "new_first_8_stages": sorted({row["stage"] for row in new["queries"]})},
            "triage_p50_ms": round(statistics.median(timings), 3), "per_query": per_query,
            "scope": "Relevance replay over a curated development corpus; no live discovery or repair-success claim."}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dataset", choices=("original", "transfer"), default="original")
    args = parser.parse_args()
    report = benchmark(TRANSFER if args.dataset == "transfer" else DATASET)
    w.write_json(report, args.output)
    summary = {key: value for key, value in report.items() if key != "per_query"}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
