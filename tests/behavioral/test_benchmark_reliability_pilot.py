import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from benchmark_reliability_pilot import evaluate  # noqa: E402
from build_bundle import sanitize_result  # noqa: E402
from run_model_evals import parse_codex_json_stream  # noqa: E402


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
                {"event": "completed", "call_id": "call-1", "tool_name": "write_file", "status": "completed", "exit_code": 0, "path": "result.txt", "artifact_action": "updated", "artifact_sha256": "0" * 64},
            ]
            result = evaluate(self.task, events, workspace)
        self.assertFalse(result["artifact_verified"])
        self.assertEqual(result["assertion_status"], "failed")

    def test_missing_call_id_cannot_link_completion(self) -> None:
        events = [
            {"event": "invoked", "tool_name": "write_file", "permission": "allowed", "path": "result.txt"},
            {"event": "completed", "call_id": "other", "tool_name": "write_file", "status": "completed", "exit_code": 0, "path": "result.txt", "artifact_action": "created", "artifact_sha256": self.task["expected_sha256"]},
        ]
        result = evaluate(self.task, events, self.fixture_root / "good-workspace")
        self.assertEqual(result["assertion_status"], "not_assessable")
        self.assertEqual(result["call_identity_status"], "unavailable")

    def test_completion_before_invocation_is_not_linked(self) -> None:
        events = [
            {"event": "completed", "call_id": "call-1", "tool_name": "write_file", "status": "completed", "exit_code": 0, "path": "result.txt", "artifact_action": "created", "artifact_sha256": self.task["expected_sha256"]},
            {"event": "invoked", "call_id": "call-1", "tool_name": "write_file", "permission": "allowed", "path": "result.txt"},
        ]
        result = evaluate(self.task, events, self.fixture_root / "good-workspace")
        self.assertEqual(result["assertion_status"], "not_assessable")

    def test_preexisting_matching_artifact_without_provenance_is_not_a_pass(self) -> None:
        events = [
            {"event": "invoked", "call_id": "call-1", "tool_name": "write_file", "permission": "allowed", "path": "result.txt"},
            {"event": "completed", "call_id": "call-1", "tool_name": "write_file", "status": "completed", "exit_code": 0, "path": "result.txt"},
        ]
        result = evaluate(self.task, events, self.fixture_root / "good-workspace")
        self.assertTrue(result["artifact_verified"])
        self.assertIsNone(result["artifact_produced_by_observed_call"])
        self.assertEqual(result["assertion_status"], "not_assessable")

    def test_truncated_trajectory_is_not_assessable(self) -> None:
        result = evaluate(
            self.task,
            self._events("good-events.jsonl"),
            self.fixture_root / "good-workspace",
            trajectory_status="truncated",
        )
        self.assertEqual(result["assertion_status"], "not_assessable")

    def test_mixed_failed_and_successful_attempts_are_not_combined(self) -> None:
        events = [
            {"event": "invoked", "call_id": "call-failed", "tool_name": "write_file", "permission": "allowed", "path": "result.txt"},
            {"event": "completed", "call_id": "call-failed", "tool_name": "write_file", "status": "failed", "exit_code": 1, "path": "result.txt"},
            {"event": "invoked", "call_id": "call-success", "tool_name": "write_file", "permission": "allowed", "path": "result.txt"},
            {"event": "completed", "call_id": "call-success", "tool_name": "write_file", "status": "completed", "exit_code": 0, "path": "result.txt", "artifact_action": "updated", "artifact_sha256": self.task["expected_sha256"]},
        ]
        result = evaluate(self.task, events, self.fixture_root / "good-workspace")
        self.assertEqual(result["assertion_status"], "not_assessable")

    def test_provider_parser_bundle_and_scorer_form_one_offline_chain(self) -> None:
        expected_sha = self.task["expected_sha256"]
        stream = "\n".join([
            json.dumps({"type": "item.started", "item": {
                "id": "call-chain", "type": "command_execution", "path": "result.txt",
            }}),
            json.dumps({"type": "item.completed", "item": {
                "id": "call-chain", "type": "command_execution", "path": "result.txt",
                "status": "completed", "exit_code": 0,
                "artifact_action": "created", "artifact_sha256": expected_sha,
            }}),
        ])
        parsed = parse_codex_json_stream(stream)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "result.txt").write_bytes(
                (self.fixture_root / "good-workspace" / "result.txt").read_bytes()
            )
            bundled = sanitize_result("run", "rev", {
                "case_id": "case", "variant": "sovetwave", "process_status": "completed",
                "tool_events": parsed["tool_events"],
                "tool_events_status": parsed["tool_events_status"],
            })
            result = evaluate(
                {**self.task, "tool_name": "command_execution"},
                bundled["tool_events"], workspace,
                trajectory_status=bundled["tool_events_status"],
            )
        self.assertEqual(result["assertion_status"], "passed")
        self.assertTrue(result["artifact_produced_by_observed_call"])


if __name__ == "__main__":
    unittest.main()
