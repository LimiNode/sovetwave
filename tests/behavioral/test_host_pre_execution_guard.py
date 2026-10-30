import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "host-pre-execution-guard"))

import guard  # noqa: E402


def request(
    action_id: str,
    category: str,
    *,
    target: str = "fixture-target",
    approval_identity: str | None = None,
    **context: object,
) -> guard.OperationRequest:
    return guard.OperationRequest(
        action_id=action_id,
        tool_identity="fixture-tool",
        action_category=category,
        target=target,
        scope="fixture-scope",
        trust_origin="user",
        policy_context=context,
        approval_identity=approval_identity,
    )


class HostPreExecutionGuardTests(unittest.TestCase):
    def test_selftest_stays_inside_offline_boundary(self) -> None:
        report = guard.selftest()
        self.assertEqual(report["execution_mode"], "offline_host_mock_only")
        self.assertEqual(report["model_calls"], 0)
        self.assertFalse(report["generated_code_executed"])
        self.assertFalse(report["real_commands_executed"])
        self.assertEqual(
            report["decisions"],
            {
                "safe": "ALLOW",
                "destructive": "DENY",
                "ask": "ASK",
                "approved": "ALLOW",
                "unavailable": "UNAVAILABLE",
                "error": "ERROR",
            },
        )
        self.assertEqual(report["side_effect_count"], 2)

    def test_deny_happens_before_side_effect(self) -> None:
        host = guard.GuardedHostMock()
        receipt = host.admit(request("delete", "destructive"))
        self.assertEqual(receipt.decision.decision, "DENY")
        self.assertFalse(receipt.executed)
        self.assertEqual(receipt.side_effect_count, 0)
        self.assertEqual(host.executed_action_ids, [])

    def test_ask_requires_trusted_confirmation(self) -> None:
        host = guard.GuardedHostMock()
        operation = request("write", "write")
        pending = host.admit(operation)
        self.assertEqual(pending.decision.decision, "ASK")
        self.assertFalse(pending.executed)
        self.assertEqual(host.side_effect_count, 0)

        approval = guard.Approval("approval-1", "trusted-user", operation.request_digest)
        allowed = host.admit(operation, approval)
        self.assertEqual(allowed.decision.decision, "ALLOW")
        self.assertTrue(allowed.executed)
        self.assertEqual(allowed.decision.approval_id, "approval-1")
        self.assertEqual(host.side_effect_count, 1)

    def test_approval_is_bound_to_exact_operation_and_not_reusable(self) -> None:
        host = guard.GuardedHostMock()
        first = request("write-1", "write", target="one")
        approval = guard.Approval("approval-1", "trusted-user", first.request_digest)
        self.assertTrue(host.admit(first, approval).executed)

        changed_target = request("write-1", "write", target="two")
        changed = host.admit(changed_target, approval)
        self.assertEqual(changed.decision.decision, "DENY")
        self.assertFalse(changed.executed)

        second_operation = request("write-2", "write", target="one")
        reused = host.admit(second_operation, approval)
        self.assertEqual(reused.decision.decision, "DENY")
        self.assertFalse(reused.executed)
        self.assertEqual(host.side_effect_count, 1)

        bound = request("write-3", "write", approval_identity="approval-expected")
        mismatched_identity = guard.Approval("approval-other", "trusted-user", bound.request_digest)
        identity_mismatch = host.admit(bound, mismatched_identity)
        self.assertEqual(identity_mismatch.decision.decision, "DENY")
        self.assertFalse(identity_mismatch.executed)

    def test_repository_policy_cannot_disable_deny(self) -> None:
        host = guard.GuardedHostMock()
        receipt = host.admit(
            request("delete", "destructive", repository_policy={"disable_deny": True})
        )
        self.assertEqual(receipt.decision.decision, "DENY")
        self.assertTrue(receipt.decision.provenance["repository_policy_ignored"])
        self.assertEqual(host.side_effect_count, 0)

    def test_unavailable_and_error_are_fail_closed(self) -> None:
        host = guard.GuardedHostMock()
        unavailable = host.admit(request("unavailable", "write", policy_state="unavailable"))
        error = host.admit(request("error", "write", policy_state="error"))
        self.assertEqual(unavailable.decision.decision, "UNAVAILABLE")
        self.assertEqual(error.decision.decision, "ERROR")
        self.assertFalse(unavailable.executed)
        self.assertFalse(error.executed)
        self.assertEqual(host.side_effect_count, 0)

    def test_evaluator_exception_is_error_not_allow(self) -> None:
        def broken_evaluator(_operation: guard.OperationRequest, _approval: guard.Approval | None) -> guard.DecisionRecord:
            raise RuntimeError("broken evaluator")

        host = guard.GuardedHostMock(broken_evaluator)
        receipt = host.admit(request("write", "write"))
        self.assertEqual(receipt.decision.decision, "ERROR")
        self.assertFalse(receipt.executed)
        self.assertEqual(host.side_effect_count, 0)

    def test_text_mention_is_data_not_an_execution_request(self) -> None:
        host = guard.GuardedHostMock()
        receipt = host.admit(
            request("inspect-text", "read", target="document contains: rm -rf /tmp/data")
        )
        self.assertEqual(receipt.decision.decision, "ALLOW")
        self.assertTrue(receipt.executed)
        self.assertEqual(host.side_effect_count, 1)

    def test_decision_has_explainable_provenance(self) -> None:
        operation = request("delete", "destructive")
        receipt = guard.GuardedHostMock().admit(operation)
        decision = receipt.decision
        self.assertEqual(decision.action_id, operation.action_id)
        self.assertEqual(decision.request_digest, operation.request_digest)
        self.assertEqual(decision.policy_revision, guard.POLICY_REVISION)
        self.assertTrue(decision.reason)
        self.assertTrue(decision.decision_id)


if __name__ == "__main__":
    unittest.main()
