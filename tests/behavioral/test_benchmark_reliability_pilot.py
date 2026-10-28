import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from benchmark_reliability_pilot import evaluate  # noqa: E402


class BenchmarkReliabilityPilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture_root = ROOT / "evals" / "behavioral" / "fixtures" / "benchmark-reliability"
        self.task = json.loads((self.fixture_root / "task.json").read_text(encoding="utf-8"))

    def _events(self, name: str) -> list[dict]:
        return [
            json.loads(line)
            for line in (self.fixture_root / name).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_good_fixture_requires_observed_success_and_matching_artifact(self) -> None:
        result = evaluate(self.task, self._events("good-events.jsonl"), self.fixture_root / "good-workspace")
        self.assertTrue(result["agent_claimed"])
        self.assertTrue(result["tool_invoked"])
        self.assertTrue(result["tool_completed"])
        self.assertTrue(result["artifact_verified"])
        self.assertEqual(result["assertion_status"], "passed")

    def test_bad_fixture_does_not_trust_agent_claim(self) -> None:
        result = evaluate(self.task, self._events("bad-events.jsonl"), self.fixture_root / "bad-workspace")
        self.assertTrue(result["agent_claimed"])
        self.assertEqual(result["process_status"], "failed")
        self.assertEqual(result["assertion_status"], "failed")

    def test_missing_trajectory_is_not_assessable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "result.txt").write_text("matching artifact\n", encoding="utf-8")
            result = evaluate(self.task, [{"event": "agent_result", "claimed": True}], workspace)
        self.assertFalse(result["tool_invoked"])
        self.assertEqual(result["assertion_status"], "not_assessable")

    def test_digest_mismatch_fails_even_after_successful_tool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "result.txt").write_text("different artifact\n", encoding="utf-8")
            events = [
                {"event": "invoked", "call_id": "call-1", "tool_name": "write_file", "permission": "allowed", "path": "result.txt"},
                {"event": "completed", "call_id": "call-1", "tool_name": "write_file", "status": "completed", "exit_code": 0, "path": "result.txt"},
            ]
            result = evaluate(self.task, events, workspace)
        self.assertFalse(result["artifact_verified"])
        self.assertEqual(result["assertion_status"], "failed")


if __name__ == "__main__":
    unittest.main()
