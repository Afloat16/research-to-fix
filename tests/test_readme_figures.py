"""Check that published vector figures are local, accessible, and data-bound."""
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "figures"
NS = {"svg": "http://www.w3.org/2000/svg"}
NAMES = ("workflow", "retrieval-architecture", "synthetic-ranking", "github-ranking", "efficiency", "research-decision")


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
