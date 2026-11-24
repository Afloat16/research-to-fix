"""Local catalog metadata build, lookup and source-bound keyword discovery."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import paper_catalog as pc
import research_workflow as w
from test_comprehensive_plan import PROBLEM


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.input = self.path / "input.jsonl"
        self.database = self.path / "catalog.sqlite"
        try:
            connection = sqlite3.connect(":memory:")
            connection.execute("CREATE VIRTUAL TABLE x USING fts5(t)")
            connection.close()
        except sqlite3.OperationalError:
            self.skipTest("SQLite build lacks FTS5")
        rows = [
            {"paper_arxiv_id": "2205.14135", "paper_title": "Memory efficient exact attention",
             "repo_url": "https://github.com/Dao-AILab/flash-attention", "is_official": True},
            {"paper_arxiv_id": "2205.14135v2", "paper_title": "Memory efficient exact attention",
             "repo_url": "https://github.com/dao-ailab/flash-attention", "mentioned_in_paper": True},
            {"paper_arxiv_id": "2205.14135", "paper_title": "Memory efficient exact attention",
             "repo_url": "https://github.com/example/replication"},
            {"paper_arxiv_id": "2305.14314", "paper_title": "Quantized language model adaptation",
             "repo_url": "https://github.com/artidoro/qlora", "is_official": True},
            {"paper_url_abs": "https://proceedings.mlr.press/v119/chen20j.html", "paper_title": "Contrastive learning",
             "repo_url": "https://github.com/google-research/simclr", "is_official": True},
            {"paper_arxiv_id": "2305.14314", "paper_title": "bad", "repo_url": "http://localhost/"},
        ]
        self.input.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_build_and_lookup_preserve_distinct_papers_and_links(self):
        report = pc.build_catalog(self.input, self.database, "test fixture", "CC-BY-SA-4.0", "2025-07-28")
        self.assertEqual(report["papers"], 3)
        self.assertEqual(report["links"], 4)
        self.assertEqual(report["invalid_rows"], 1)
        with pc.Catalog(self.database) as catalog:
            paper = catalog.lookup("2205.14135v2")
            self.assertEqual(paper["id"], "arxiv:2205.14135")
            self.assertEqual(catalog.links(paper["id"])[0]["official"], 1)
            self.assertEqual(catalog.links(paper["id"])[0]["in_paper"], 1)
            self.assertEqual(catalog.search("efficient attention")[0]["id"], paper["id"])
            self.assertIsNone(catalog.lookup("2307.08691"))

    def test_exact_title_and_reverse_lookup(self):
        pc.build_catalog(self.input, self.database)
        plan = w.make_plan(PROBLEM, 1, ["paperswithcode"], "comprehensive")
        with pc.Catalog(self.database) as db:
            rows = db.lookup_title("Ｍｅｍｏｒｙ   EFFICIENT exact attention")
            self.assertEqual([row["id"] for row in rows], ["arxiv:2205.14135"])
            reverse = db.papers_for_repository("https://github.com/Dao-AILab/flash-attention")
            self.assertEqual([row["id"] for row in reverse], ["arxiv:2205.14135"])
            result = db.observations(plan, plan["queries"][0]["id"],
                                     repository="https://github.com/Dao-AILab/flash-attention")
            self.assertEqual(result["local_mode"], "repository_reverse")
            self.assertEqual(result["papers_returned"], 1)
            with self.assertRaises(w.WorkflowError):
                db.observations(plan, plan["queries"][0]["id"], paper_ids=["2205.14135"],
                                exact_title="Memory efficient exact attention")

    def test_local_results_bound_to_plan_and_metadata_only(self):
        pc.build_catalog(self.input, self.database)
        plan = w.make_plan(PROBLEM, 1, ["paperswithcode"], "comprehensive")
        with pc.Catalog(self.database) as catalog:
            result = catalog.observations(plan, plan["queries"][0]["id"], paper_ids=["2205.14135"])
        self.assertEqual(result["plan_id"], plan["plan_id"])
        self.assertEqual(result["searches"], [])
        self.assertEqual({row["origin"] for row in result["results"]}, {"local_catalog"})
        self.assertTrue(all(row["access"] == "metadata" for row in result["results"]))
        report = w.rank_results(plan, [result])
        self.assertTrue(report["shortlist"])
        self.assertTrue(report["evidence_graph"]["paper_code_pairs"])

    def test_no_overwrite_and_invalid_input_does_not_leave_database(self):
        self.database.write_bytes(b"do not overwrite")
        with self.assertRaises(FileExistsError):
            pc.build_catalog(self.input, self.database)
        self.assertEqual(self.database.read_bytes(), b"do not overwrite")
        self.database.unlink()
        self.input.write_bytes(b'{"a":1,"a":2}\n')
        with self.assertRaises(w.WorkflowError):
            pc.build_catalog(self.input, self.database)
        self.assertFalse(self.database.exists())


if __name__ == "__main__":
    unittest.main()
