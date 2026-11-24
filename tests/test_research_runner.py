"""One-round bundle is offline by default and preserves provenance."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/research-to-fix/scripts"))
import research_runner as runner
import research_workflow as w
from test_comprehensive_plan import PROBLEM


class RunnerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.output = Path(tmp.name) / "round"
        self.plan = w.make_plan(PROBLEM, 1, ["github_repositories"], "comprehensive")
        self.qid = self.plan["queries"][0]["id"]
        self.inputs = [{"plan_id": self.plan["plan_id"], "results": [
            {"query_id": self.qid, "url": "https://github.com/example/attention",
             "title": "memory efficient exact attention", "kind": "repository"}],
            "searches": [{"query_id": self.qid, "status": "completed"}]}]
        self.calls = []

    def transport(self, url, provider):
        self.calls.append((url, provider))
        return b'{"items":[]}'

    def test_offline_round_and_next_plan(self):
        result = runner.run_round(self.plan, self.output, self.inputs, transport=self.transport)
        self.assertEqual(self.calls, [])
        self.assertEqual(result["result_files"], ["host-01.json"])
        self.assertFalse(result["network_enabled"])
        report = json.loads((self.output / "session.json").read_text())
        self.assertEqual(result["session_id"], report["session_id"])
        self.assertEqual(w.validate_plan(w.read_json(self.output / "next-plan.json")), report["next_plan"])
        with self.assertRaises(FileExistsError):
            runner.run_round(self.plan, self.output, self.inputs)

    def test_approved_requests_and_preflight_failure(self):
        with self.assertRaises(w.WorkflowError):
            runner.run_round(self.plan, self.output, [{"plan_id": "wrong"}],
                             approve_public=True, transport=self.transport)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.output.exists())
        result = runner.run_round(self.plan, self.output, approve_public=True, requests=1,
                                  transport=self.transport)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["result_files"], ["api.json"])
        self.assertEqual(result["shortlisted"], 0)

    def test_no_implicit_source(self):
        with self.assertRaises(w.WorkflowError):
            runner.run_round(self.plan, self.output, transport=self.transport)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
