import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "host-pre-execution-guard"))

import guard  # noqa: E402


def request(
    action_id: str,
    category: str,
    *,
    target: str = "fixture-target",
    trust_origin: str = "user",
    approval_identity: str | None = None,
    **context: object,
) -> guard.OperationRequest:
    return guard.OperationRequest(
        action_id=action_id,
        tool_identity="fixture-tool",
        action_category=category,
        target=target,
        scope="fixture-scope",
        trust_origin=trust_origin,
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

    def test_unknown_category_is_denied_before_evaluator_or_side_effect(self) -> None:
        operation = request("unknown", "unrecognized-destructive-operation")
        evaluator_called = False

        def forged_allow(_operation: guard.OperationRequest, _approval: guard.Approval | None) -> guard.DecisionRecord:
            nonlocal evaluator_called
            evaluator_called = True
            return guard.DecisionRecord(
                decision="ALLOW",
                action_id=operation.action_id,
                request_digest=operation.request_digest,
                reason="forged unknown-category allow",
                policy_revision=guard.POLICY_REVISION,
                approval_id=None,
                provenance={"evaluator": "untrusted-test"},
            )

        host = guard.GuardedHostMock(forged_allow)
        receipt = host.admit(operation)
        self.assertEqual(receipt.decision.decision, "DENY")
        self.assertEqual(receipt.decision.provenance["host_validation"], "unknown_category")
        self.assertFalse(receipt.executed)
        self.assertFalse(evaluator_called)
        self.assertEqual(host.side_effect_count, 0)

    def test_untrusted_read_cannot_be_allowed_by_evaluator(self) -> None:
        operation = request("untrusted-read", "read", trust_origin="repository")

        def forged_allow(_operation: guard.OperationRequest, _approval: guard.Approval | None) -> guard.DecisionRecord:
            return guard.DecisionRecord(
                decision="ALLOW",
                action_id=operation.action_id,
                request_digest=operation.request_digest,
                reason="forged untrusted-read allow",
                policy_revision=guard.POLICY_REVISION,
                approval_id=None,
                provenance={"evaluator": "untrusted-test"},
            )

        host = guard.GuardedHostMock(forged_allow)
        receipt = host.admit(operation)
        self.assertEqual(receipt.decision.decision, "DENY")
        self.assertEqual(receipt.decision.provenance["host_validation"], "read_trust_origin")
        self.assertFalse(receipt.executed)
        self.assertEqual(host.side_effect_count, 0)

    def test_policy_state_cannot_be_bypassed_by_forged_allow(self) -> None:
        for state, expected in (("unavailable", "UNAVAILABLE"), ("error", "ERROR")):
            with self.subTest(state=state):
                operation = request(f"policy-{state}", "read", policy_state=state)
                evaluator_called = False

                def forged_allow(
                    _operation: guard.OperationRequest,
                    _approval: guard.Approval | None,
                ) -> guard.DecisionRecord:
                    nonlocal evaluator_called
                    evaluator_called = True
                    return guard.DecisionRecord(
                        decision="ALLOW",
                        action_id=operation.action_id,
                        request_digest=operation.request_digest,
                        reason="forged policy-state allow",
                        policy_revision=guard.POLICY_REVISION,
                        approval_id=None,
                        provenance={"evaluator": "untrusted-test"},
                    )

                host = guard.GuardedHostMock(forged_allow)
                receipt = host.admit(operation)
                self.assertEqual(receipt.decision.decision, expected)
                self.assertFalse(receipt.executed)
                self.assertFalse(evaluator_called)
                self.assertEqual(host.side_effect_count, 0)

    def test_ask_requires_trusted_confirmation(self) -> None:
        authority = guard.HostApprovalAuthority()
        host = guard.GuardedHostMock(approval_authority=authority)
        operation = request("write", "write")
        pending = host.admit(operation)
        self.assertEqual(pending.decision.decision, "ASK")
        self.assertFalse(pending.executed)
        self.assertEqual(host.side_effect_count, 0)

        approval = authority.issue(operation)
        allowed = host.admit(operation, approval)
        self.assertEqual(allowed.decision.decision, "ALLOW")
        self.assertTrue(allowed.executed)
        self.assertEqual(allowed.decision.approval_id, approval.approval_id)
        self.assertEqual(host.side_effect_count, 1)

    def test_approval_is_bound_to_exact_operation_and_not_reusable(self) -> None:
        authority = guard.HostApprovalAuthority()
        host = guard.GuardedHostMock(approval_authority=authority)
        first = request("write-1", "write", target="one")
        approval = authority.issue(first)
        self.assertTrue(host.admit(first, approval).executed)

        replayed = host.admit(first, approval)
        self.assertEqual(replayed.decision.decision, "DENY")
        self.assertFalse(replayed.executed)

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

    def test_approval_issuer_is_separate_from_agent_facing_host(self) -> None:
        authority = guard.HostApprovalAuthority()
        host = guard.GuardedHostMock(approval_authority=authority)
        self.assertFalse(hasattr(host, "issue_approval"))
        self.assertFalse(hasattr(host, "approval_authority"))

        operation = request("write", "write")
        approval = authority.issue(operation)
        receipt = host.admit(operation, approval)
        self.assertEqual(receipt.decision.decision, "ALLOW")
        self.assertTrue(receipt.executed)

    def test_unissued_or_wrong_principal_approval_is_rejected(self) -> None:
        authority = guard.HostApprovalAuthority()
        host = guard.GuardedHostMock(approval_authority=authority)
        operation = request("write", "write")

        forged = guard.Approval("not-issued", guard.TRUSTED_PRINCIPAL, operation.request_digest)
        forged_receipt = host.admit(operation, forged)
        self.assertEqual(forged_receipt.decision.decision, "DENY")
        self.assertFalse(forged_receipt.executed)

        wrong_principal = authority.issue(operation, principal="untrusted-user")
        wrong_principal_receipt = host.admit(operation, wrong_principal)
        self.assertEqual(wrong_principal_receipt.decision.decision, "DENY")
        self.assertFalse(wrong_principal_receipt.executed)
        self.assertEqual(host.side_effect_count, 0)

    def test_concurrent_admission_consumes_approval_once(self) -> None:
        authority = guard.HostApprovalAuthority()
        host = guard.GuardedHostMock(approval_authority=authority)
        operation = request("write-once", "write")
        approval = authority.issue(operation)

        with ThreadPoolExecutor(max_workers=2) as executor:
            receipts = list(executor.map(lambda _: host.admit(operation, approval), range(2)))

        self.assertEqual(sorted(receipt.executed for receipt in receipts), [False, True])
        self.assertEqual(host.side_effect_count, 1)

    def test_allow_write_requires_matching_host_approval(self) -> None:
        operation = request("write", "write")

        def forged_allow(_request: guard.OperationRequest, _approval: guard.Approval | None) -> guard.DecisionRecord:
            return guard.DecisionRecord(
                decision="ALLOW",
                action_id=operation.action_id,
                request_digest=operation.request_digest,
                reason="forged evaluator allow",
                policy_revision=guard.POLICY_REVISION,
                approval_id=None,
                provenance={"evaluator": "test"},
            )

        host = guard.GuardedHostMock(forged_allow)
        receipt = host.admit(operation)
        self.assertEqual(receipt.decision.decision, "ERROR")
        self.assertFalse(receipt.executed)
        self.assertEqual(host.side_effect_count, 0)

    def test_policy_context_is_immutable_snapshot(self) -> None:
        nested = {"limits": {"paths": ["one"]}}
        operation = request("snapshot", "read", metadata=nested)
        digest = operation.request_digest

        nested["limits"]["paths"].append("two")
        nested["limits"]["new"] = "mutated"

        self.assertEqual(operation.request_digest, digest)
        self.assertEqual(operation.policy_context["metadata"]["limits"]["paths"], ("one",))
        self.assertNotIn("new", operation.policy_context["metadata"]["limits"])

    def test_invalid_policy_context_is_rejected_at_request_construction(self) -> None:
        cyclic: dict[str, Any] = {}
        cyclic["self"] = cyclic
        invalid_values = (
            ({"bad": {1, 2}}, TypeError),
            ({"bad": object()}, TypeError),
            ({"bad": float("nan")}, ValueError),
            (cyclic, ValueError),
        )

        for value, error_type in invalid_values:
            with self.subTest(error_type=error_type.__name__):
                with self.assertRaises(error_type):
                    request("invalid-context", "write", malformed=value)

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

    def test_malformed_evaluator_results_fail_closed(self) -> None:
        operation = request("write", "write")

        def result(value: Any):
            return lambda _request, _approval: value

        valid = guard.DecisionRecord(
            decision="ALLOW",
            action_id=operation.action_id,
            request_digest=operation.request_digest,
            reason="test result",
            policy_revision=guard.POLICY_REVISION,
            approval_id=None,
            provenance={"evaluator": "test"},
        )
        mismatched_action = guard.DecisionRecord(
            decision="ALLOW",
            action_id="other-action",
            request_digest=operation.request_digest,
            reason="test result",
            policy_revision=guard.POLICY_REVISION,
            approval_id=None,
            provenance={"evaluator": "test"},
        )
        mismatched_digest = guard.DecisionRecord(
            decision="ALLOW",
            action_id=operation.action_id,
            request_digest="0" * 64,
            reason="test result",
            policy_revision=guard.POLICY_REVISION,
            approval_id=None,
            provenance={"evaluator": "test"},
        )
        wrong_revision = guard.DecisionRecord(
            decision="ALLOW",
            action_id=operation.action_id,
            request_digest=operation.request_digest,
            reason="test result",
            policy_revision="old-policy",
            approval_id=None,
            provenance={"evaluator": "test"},
        )

        for candidate in (None, object(), mismatched_action, mismatched_digest, wrong_revision):
            with self.subTest(candidate=type(candidate).__name__):
                host = guard.GuardedHostMock(result(candidate))
                receipt = host.admit(operation)
                self.assertEqual(receipt.decision.decision, "ERROR")
                self.assertFalse(receipt.executed)
                self.assertEqual(host.side_effect_count, 0)
        self.assertEqual(valid.decision, "ALLOW")

    def test_host_denies_forged_destructive_allow(self) -> None:
        operation = request("delete", "destructive")

        def forged_allow(_request: guard.OperationRequest, _approval: guard.Approval | None) -> guard.DecisionRecord:
            return guard.DecisionRecord(
                decision="ALLOW",
                action_id=operation.action_id,
                request_digest=operation.request_digest,
                reason="forged destructive allow",
                policy_revision=guard.POLICY_REVISION,
                approval_id=None,
                provenance={"evaluator": "untrusted-test"},
            )

        host = guard.GuardedHostMock(forged_allow)
        receipt = host.admit(operation)
        self.assertEqual(receipt.decision.decision, "DENY")
        self.assertFalse(receipt.executed)
        self.assertEqual(receipt.decision.provenance["host_validation"], "destructive_deny")
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
