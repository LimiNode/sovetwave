"""Offline host pre-execution guard pilot.

The pilot models the admission boundary only. It never invokes a shell,
filesystem mutation, network operation, generated code, or model API.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import secrets
from threading import Lock
from types import MappingProxyType
from typing import Any, Callable, Mapping


DECISIONS = ("ALLOW", "ASK", "DENY", "UNAVAILABLE", "ERROR")
POLICY_REVISION = "host-pre-execution-guard-pilot-v1"
EXECUTION_MODE = "offline_host_mock_only"
TRUSTED_PRINCIPAL = "trusted-user"


class PolicyUnavailable(Exception):
    """The policy source is unavailable, so admission must not proceed."""


class PolicyEvaluationError(Exception):
    """The policy evaluator failed, so admission must not proceed."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class OperationRequest:
    """Typed description of one operation presented to the host guard."""

    action_id: str
    tool_identity: str
    action_category: str
    target: str
    scope: str
    trust_origin: str
    policy_context: Mapping[str, Any]
    approval_identity: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "action_id",
            "tool_identity",
            "action_category",
            "target",
            "scope",
            "trust_origin",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.policy_context, Mapping):
            raise ValueError("policy_context must be a mapping")
        object.__setattr__(self, "policy_context", MappingProxyType(dict(self.policy_context)))
        if self.approval_identity is not None and (
            not isinstance(self.approval_identity, str) or not self.approval_identity.strip()
        ):
            raise ValueError("approval_identity must be a non-empty string when present")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "tool_identity": self.tool_identity,
            "action_category": self.action_category,
            "target": self.target,
            "scope": self.scope,
            "trust_origin": self.trust_origin,
            "policy_context": dict(self.policy_context),
            "approval_identity": self.approval_identity,
        }

    @property
    def request_digest(self) -> str:
        return sha256(_canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Approval:
    """A confirmation bound to one exact request and trusted principal."""

    approval_id: str
    principal: str
    request_digest: str

    def __post_init__(self) -> None:
        for name in ("approval_id", "principal", "request_digest"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class DecisionRecord:
    decision: str
    action_id: str
    request_digest: str
    reason: str
    policy_revision: str
    approval_id: str | None
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise ValueError(f"unknown decision: {self.decision}")
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))

    @property
    def decision_id(self) -> str:
        payload = {
            "action_id": self.action_id,
            "request_digest": self.request_digest,
            "decision": self.decision,
            "policy_revision": self.policy_revision,
            "approval_id": self.approval_id,
        }
        return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AdmissionReceipt:
    decision: DecisionRecord
    executed: bool
    side_effect_count: int


def _decision(
    request: OperationRequest,
    decision: str,
    reason: str,
    *,
    approval: Approval | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> DecisionRecord:
    return DecisionRecord(
        decision=decision,
        action_id=request.action_id,
        request_digest=request.request_digest,
        reason=reason,
        policy_revision=POLICY_REVISION,
        approval_id=approval.approval_id if approval else None,
        provenance={
            "evaluator": "checked_in_offline_policy",
            "request_digest": request.request_digest,
            **(dict(provenance) if provenance else {}),
        },
    )


def _approval_matches_request(request: OperationRequest, approval: Approval | None) -> bool:
    """Check only the request binding; host authority proves issuance and trust."""
    return bool(
        approval
        and approval.request_digest == request.request_digest
        and (
            request.approval_identity is None
            or approval.approval_id == request.approval_identity
        )
    )


def evaluate_policy(request: OperationRequest, approval: Approval | None = None) -> DecisionRecord:
    """Return an admission decision without performing the requested action."""
    state = request.policy_context.get("policy_state", "ready")
    if state == "unavailable":
        raise PolicyUnavailable("policy source is unavailable")
    if state == "error":
        raise PolicyEvaluationError("policy evaluator failed")
    if state != "ready":
        raise PolicyEvaluationError(f"unknown policy state: {state!r}")

    repository_policy = request.policy_context.get("repository_policy", {})
    repository_disable_deny = isinstance(repository_policy, Mapping) and bool(
        repository_policy.get("disable_deny")
    )
    provenance = {
        "policy_state": state,
        "repository_policy_ignored": repository_disable_deny,
    }

    if request.action_category == "destructive":
        reason = "destructive action is denied by the host policy"
        if repository_disable_deny:
            reason += "; untrusted repository policy cannot weaken the deny rule"
        return _decision(request, "DENY", reason, provenance=provenance)

    if request.action_category == "read" and request.trust_origin in {"system", "user"}:
        return _decision(request, "ALLOW", "non-destructive trusted read", provenance=provenance)

    if request.action_category in {"write", "external"}:
        if approval is None:
            return _decision(
                request,
                "ASK",
                "trusted confirmation is required before the operation",
                provenance=provenance,
            )
        if not _approval_matches_request(request, approval):
            return _decision(
                request,
                "DENY",
                "approval is absent or bound to a different operation",
                approval=approval,
                provenance=provenance,
            )
        return _decision(
            request,
            "ALLOW",
            "approval matches the exact operation digest; host authority must validate issuance",
            approval=approval,
            provenance=provenance,
        )

    return _decision(
        request,
        "ASK",
        "operation category requires explicit trusted confirmation",
        approval=approval,
        provenance=provenance,
    )


class HostApprovalAuthority:
    """Host-owned in-memory authority for exact, one-time approvals."""

    def __init__(self) -> None:
        self._issued: dict[str, tuple[str, str]] = {}
        self._lock = Lock()

    def issue(
        self,
        request: OperationRequest,
        *,
        principal: str = TRUSTED_PRINCIPAL,
    ) -> Approval:
        if not isinstance(request, OperationRequest):
            raise TypeError("request must be an OperationRequest")
        if not isinstance(principal, str) or not principal.strip():
            raise ValueError("principal must be a non-empty string")

        approval_id = f"host-{secrets.token_urlsafe(18)}"
        with self._lock:
            self._issued[approval_id] = (principal, request.request_digest)
        return Approval(
            approval_id=approval_id,
            principal=principal,
            request_digest=request.request_digest,
        )

    def consume(self, request: OperationRequest, approval: Approval | None) -> bool:
        """Atomically validate and consume one host-issued approval."""
        if not isinstance(request, OperationRequest) or not isinstance(approval, Approval):
            return False
        with self._lock:
            binding = self._issued.get(approval.approval_id)
            if binding is None:
                return False
            principal, request_digest = binding
            if principal != TRUSTED_PRINCIPAL:
                return False
            if approval.principal != principal or approval.request_digest != request_digest:
                return False
            if request.request_digest != request_digest:
                return False
            if request.approval_identity is not None and approval.approval_id != request.approval_identity:
                return False
            del self._issued[approval.approval_id]
            return True


class GuardedHostMock:
    """A deterministic host boundary whose only side effect is an in-memory counter."""

    def __init__(
        self,
        evaluator: Callable[[OperationRequest, Approval | None], object] = evaluate_policy,
        *,
        approval_authority: HostApprovalAuthority | None = None,
    ):
        self._evaluator = evaluator
        self.approval_authority = approval_authority or HostApprovalAuthority()
        self.side_effect_count = 0
        self.executed_action_ids: list[str] = []

    def issue_approval(
        self,
        request: OperationRequest,
        *,
        principal: str = TRUSTED_PRINCIPAL,
    ) -> Approval:
        return self.approval_authority.issue(request, principal=principal)

    @staticmethod
    def _validate_decision(
        request: OperationRequest,
        approval: Approval | None,
        decision: object,
    ) -> DecisionRecord:
        if not isinstance(decision, DecisionRecord):
            raise TypeError("evaluator did not return a DecisionRecord")
        if decision.decision not in DECISIONS:
            raise ValueError("decision value is not recognised by host")
        if decision.action_id != request.action_id:
            raise ValueError("decision action_id does not match request")
        if decision.request_digest != request.request_digest:
            raise ValueError("decision request_digest does not match request")
        if decision.policy_revision != POLICY_REVISION:
            raise ValueError("decision policy_revision is not accepted by host")
        if not isinstance(decision.reason, str) or not decision.reason.strip():
            raise ValueError("decision reason is malformed")
        if not isinstance(decision.provenance, Mapping):
            raise TypeError("decision provenance is malformed")
        if decision.approval_id is not None and not isinstance(decision.approval_id, str):
            raise TypeError("decision approval_id is malformed")
        if decision.approval_id is not None:
            if not isinstance(approval, Approval) or decision.approval_id != approval.approval_id:
                raise ValueError("decision approval_id does not match presented approval")
        return decision

    @staticmethod
    def _error_decision(request: OperationRequest, reason: str) -> DecisionRecord:
        return _decision(
            request,
            "ERROR",
            reason,
            provenance={"host_validation": "fail_closed"},
        )

    def admit(self, request: OperationRequest, approval: Approval | None = None) -> AdmissionReceipt:
        try:
            raw_decision = self._evaluator(request, approval)
        except PolicyUnavailable as error:
            decision = _decision(request, "UNAVAILABLE", str(error))
        except Exception as error:
            decision = self._error_decision(
                request,
                f"policy evaluation failed: {type(error).__name__}",
            )
        else:
            try:
                decision = self._validate_decision(request, approval, raw_decision)
            except Exception as error:
                decision = self._error_decision(
                    request,
                    f"invalid policy decision: {type(error).__name__}",
                )

        if decision.decision != "ALLOW":
            return AdmissionReceipt(decision=decision, executed=False, side_effect_count=self.side_effect_count)

        if request.action_category == "destructive":
            decision = _decision(
                request,
                "DENY",
                "destructive action is denied by the host admission invariant",
                provenance={"host_validation": "destructive_deny"},
            )
            return AdmissionReceipt(decision=decision, executed=False, side_effect_count=self.side_effect_count)

        if request.action_category in {"write", "external"}:
            if not isinstance(approval, Approval) or decision.approval_id != approval.approval_id:
                decision = self._error_decision(
                    request,
                    "ALLOW for write/external action lacks a matching approval",
                )
                return AdmissionReceipt(decision=decision, executed=False, side_effect_count=self.side_effect_count)
            if not self.approval_authority.consume(request, approval):
                decision = _decision(
                    request,
                    "DENY",
                    "approval was not issued by this host authority or was already consumed",
                    provenance={"host_validation": "approval_authority_rejected"},
                )
                return AdmissionReceipt(decision=decision, executed=False, side_effect_count=self.side_effect_count)

        self.side_effect_count += 1
        self.executed_action_ids.append(request.action_id)
        return AdmissionReceipt(decision=decision, executed=True, side_effect_count=self.side_effect_count)


def _request(action_id: str, category: str, *, target: str = "fixture-target", **context: Any) -> OperationRequest:
    return OperationRequest(
        action_id=action_id,
        tool_identity="fixture-tool",
        action_category=category,
        target=target,
        scope="fixture-scope",
        trust_origin="user",
        policy_context=context,
    )


def selftest() -> dict[str, Any]:
    host = GuardedHostMock()
    safe = host.admit(_request("safe-read", "read"))
    destructive = host.admit(_request("delete-data", "destructive"))
    ask = host.admit(_request("write-data", "write"))
    approved_request = _request("approved-write", "write")
    approved = host.admit(approved_request, host.issue_approval(approved_request))
    unavailable = host.admit(_request("unavailable", "write", policy_state="unavailable"))
    error = host.admit(_request("error", "write", policy_state="error"))
    return {
        "execution_mode": EXECUTION_MODE,
        "model_calls": 0,
        "generated_code_executed": False,
        "real_commands_executed": False,
        "side_effect_count": host.side_effect_count,
        "decisions": {
            "safe": safe.decision.decision,
            "destructive": destructive.decision.decision,
            "ask": ask.decision.decision,
            "approved": approved.decision.decision,
            "unavailable": unavailable.decision.decision,
            "error": error.decision.decision,
        },
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), ensure_ascii=False, indent=2))
