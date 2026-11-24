"""Check that published vector figures are local, accessible, and data-bound."""
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "figures"
NS = {"svg": "http://www.w3.org/2000/svg"}
NAMES = ("workflow", "retrieval-architecture", "synthetic-ranking", "github-ranking", "efficiency", "research-decision", "release-v1", "independent-holdout", "competitor-diagnostic", "v12-recall", "v12-transfer", "v13-evidence")


class ReadmeFiguresTest(unittest.TestCase):
    def test_landing_pages_embed_all_local_language_figures(self):
        for filename, suffix in (("README.md", ""), ("README.zh-CN.md", ".zh-CN")):
            content = (ROOT / filename).read_text(encoding="utf-8")
            for name in NAMES:
                relative = f"docs/figures/{name}{suffix}.svg"
                self.assertIn(f"]({relative})", content)
                self.assertTrue((ROOT / relative).is_file())
            for target in re.findall(r"\]\(([^)\s]+)\)", content):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                self.assertTrue((ROOT / target.split("#", 1)[0]).exists(), target)

    def test_svg_is_self_contained_and_benchmark_bars_match_snapshot(self):
        data = json.loads((FIGURES / "benchmark-snapshot.json").read_text(encoding="utf-8"))
        self.assertTrue(data["regression"]["passed"])
        self.assertTrue(data["scale"]["batch_recall"]["identical_reports"])
        self.assertTrue(data["scale"]["index_scale"]["exact_top_10_scores"])
        for suffix in ("", ".zh-CN"):
            for name in NAMES:
                document = ET.parse(FIGURES / f"{name}{suffix}.svg").getroot()
                self.assertIsNotNone(document.find("svg:title", NS))
                self.assertIsNotNone(document.find("svg:desc", NS))
                self.assertEqual(document.get("role"), "img")
                for element in document.iter():
                    local = element.tag.rsplit("}", 1)[-1]
                    self.assertNotIn(local, {"script", "image", "foreignObject", "iframe"})
                if name == "v13-evidence":
                    s = json.loads((FIGURES / "v13-snapshot.json").read_text(encoding="utf-8"))
                    bars = {e.get("data-metric"): float(e.get("data-value")) for e in document.iter() if e.get("data-metric")}
                    self.assertEqual(bars, {
                        "capture.verify_unpinned": s["capture"]["rejected_faults"]["verify_unpinned"],
                        "capture.audit_unpinned": s["capture"]["rejected_faults"]["audit_unpinned"],
                        "repair.symptom_only_incomplete": s["repair"]["symptom_only_accepted"] - s["repair"]["full_suite_accepted"],
                        "repair.full_suite_incomplete": sum(row["variant"] == "narrow" and row["full_suite_accept"] for row in s["repair"]["rows"]),
                        "planning.legacy_all_stages": s["planning"]["overall"]["methods"]["legacy"]["all_stages_completed"],
                        "planning.coverage_all_stages": s["planning"]["overall"]["methods"]["coverage"]["all_stages_completed"],
                    })
                    self.assertEqual(s["repair"]["audited_bundles"], s["repair"]["candidate_comparisons"])
                if name == "v12-transfer":
                    snapshot = json.loads((FIGURES / "v12-snapshot.json").read_text(encoding="utf-8"))["transfer"]
                    bars = {e.get("data-method"): float(e.get("data-value")) for e in document.iter() if e.get("data-method")}
                    self.assertEqual(bars, {k: v["ndcg@10"] for k, v in snapshot["methods"].items()})
                    self.assertTrue(snapshot["exact_recall"]["exact_count_scores_ids_explanations"])
                    self.assertEqual(snapshot["exact_recall"]["queries"], 804)
                if name == "v12-recall":
                    snapshot = json.loads((FIGURES / "v12-snapshot.json").read_text(encoding="utf-8"))["relative_recall"]
                    bars = {e.get("data-scenario"): float(e.get("data-value")) for e in document.iter() if e.get("data-scenario")}
                    self.assertEqual(bars, {k: v["p50_speedup"] for k, v in snapshot["scenarios"].items()})
                    self.assertTrue(all(v["exact_count_scores_ids_explanations"] for v in snapshot["scenarios"].values()))
                    self.assertEqual(snapshot["exact_parity_queries"], 288)
                if name == "release-v1":
                    snapshot = json.loads((FIGURES / "v1-snapshot.json").read_text(encoding="utf-8"))
                    self.assertTrue(snapshot["gate"]["passed"])
                    self.assertTrue(snapshot["attention"]["design_lock_checked"])
                    bars = {(e.get("data-corpus"), e.get("data-method"), e.get("data-metric")): float(e.get("data-value"))
                            for e in document.iter() if e.get("data-corpus")}
                    self.assertEqual(bars, {(corpus, method, metric): snapshot[corpus]["methods"][method]["overall"][metric]
                                            for corpus in ("original", "transfer")
                                            for method in ("stemmed_bm25", "sqlite_porter", "paired_rank")
                                            for metric in ("recall", "complete_pair_recall")})
                if name == "competitor-diagnostic":
                    snap = json.loads((FIGURES / "competitor-snapshot.json").read_text(encoding="utf-8"))
                    bars = {(e.get("data-dataset"), e.get("data-method")): float(e.get("data-value"))
                            for e in document.iter() if e.get("data-dataset")}
                    expected = {(ds, method): snap["diagnostics"][ds]["methods"][method]["ndcg@10"]
                                for ds in ("scifact", "nasa")
                                for method in ("precision_field4", "v1_contextual", "bm25s_native", "bm25s_matched", "sqlite_porter")}
                    self.assertEqual(bars, expected)
                    self.assertTrue(all(row["exact_top11_scores_and_ids"] for row in snap["vector"].values()))
                if name == "independent-holdout":
                    snapshot = json.loads((FIGURES / "independent-snapshot.json").read_text(encoding="utf-8"))
                    bars = {(e.get("data-dataset"), e.get("data-method"), e.get("data-metric")): float(e.get("data-value"))
                            for e in document.iter() if e.get("data-dataset")}
                    expected = {(dataset, method, "ndcg@10"): report["methods"][method]["ndcg@10"]
                                for dataset, report in snapshot["reports"].items()
                                for method in ("precision_field4", "v1_contextual", "sqlite_unicode4")}
                    self.assertEqual(bars, expected)
                    self.assertTrue(all(v["status"] == "completed" for v in snapshot["status"]["datasets"].values()))
                    self.assertTrue(snapshot["tokenizer"]["precision_feature_parity"]["exact_token_sequence_parity"])
                if name not in ("synthetic-ranking", "github-ranking"):
                    continue
                expected = data["synthetic" if name.startswith("synthetic") else "github"]["methods"]
                bars = {
                    (element.get("data-method"), element.get("data-metric")): float(element.get("data-value"))
                    for element in document.iter()
                    if element.get("data-method")
                }
                metrics = ("mrr@5", "recall@5") if name.startswith("synthetic") else (
                    "mrr@5", "recall@5", "query_p50_ms")
                self.assertEqual(bars, {
                    (method, metric): expected[method][metric]
                    for method in expected
                    for metric in metrics
                })


if __name__ == "__main__":
    unittest.main()
