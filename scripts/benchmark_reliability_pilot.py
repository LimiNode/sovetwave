#!/usr/bin/env python3
"""Run a deterministic evidence-grade benchmark pilot without model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "behavioral" / "fixtures" / "benchmark-reliability"
TRAJECTORY_STATUSES = {"complete", "incomplete", "truncated", "unavailable", "parse_error"}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def _load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"event line {line_number} is not a JSON object")
        events.append(value)
    return events


def _relative_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or (len(normalized) >= 3 and normalized[1:3] == ":/"):
        return None
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if ".." in PurePosixPath(normalized).parts:
        return None
    return normalized


def _safe_workspace_path(workspace: Path, relative: str) -> Path:
    root = workspace.resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ValueError(f"artifact path escapes workspace: {relative!r}") from error
    return target


def _artifact_identity(task: dict[str, Any], workspace: Path) -> dict[str, Any]:
    relative = _relative_path(task.get("artifact_path"))
    if relative is None:
        raise ValueError("task must define a non-empty artifact_path")
    expected_sha = task.get("expected_sha256")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise ValueError("task must define a 64-character expected_sha256")
    target = _safe_workspace_path(workspace, relative)
    identity: dict[str, Any] = {
        "path": relative,
        "expected_sha256": expected_sha,
        "exists": target.is_file(),
        "actual_sha256": None,
    }
    if target.is_file():
        identity["actual_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    identity["verified"] = identity["actual_sha256"] == expected_sha
    return identity


def _event_targets(event: dict[str, Any], artifact_path: str, tool_name: str | None) -> bool:
    event_path = _relative_path(event.get("path") or event.get("artifact_path"))
    if event_path != artifact_path:
        return False
    if tool_name is not None and event.get("tool_name") != tool_name:
        return False
    return True


def _validate_event_sequences(events: list[dict[str, Any]]) -> tuple[bool, str, str | None]:
    """Validate optional telemetry sequence fields without trusting them for ordering."""
    lifecycle_events = [
        event for event in events
        if event.get("event") in {"invoked", "updated", "completed", "unknown"}
    ]
    sequenced = [event for event in lifecycle_events if "sequence" in event]
    if not sequenced:
        return True, "not_provided", None
    if len(sequenced) != len(lifecycle_events):
        return False, "invalid_missing", "sequence_missing_for_lifecycle_event"
    values: list[int] = []
    for event in sequenced:
        value = event.get("sequence")
        if not isinstance(value, int) or isinstance(value, bool):
            return False, "invalid_type", "sequence_must_be_integer"
        if value <= 0:
            return False, "invalid_value", "sequence_must_be_positive"
        values.append(value)
    if len(values) != len(set(values)):
        return False, "invalid_duplicate", "sequence_values_must_be_unique"
    if any(current <= previous for previous, current in zip(values, values[1:])):
        return False, "invalid_order", "sequence_must_increase_with_jsonl_order"
    return True, "valid", None


def _artifact_report(event: dict[str, Any]) -> tuple[str | None, str | None]:
    reported = event.get("artifact_sha256")
    action = event.get("artifact_action")
    artifact = event.get("artifact")
    if isinstance(artifact, dict):
        reported = artifact.get("sha256", reported)
        action = artifact.get("action", action)
    return (
        reported.lower() if isinstance(reported, str) else None,
        action if isinstance(action, str) else None,
    )


def evaluate(
    task: dict[str, Any],
    events: list[dict[str, Any]],
    workspace: Path,
    trajectory_status: str = "complete",
) -> dict[str, Any]:
    """Score only observed evidence; an agent claim is never sufficient."""
    if trajectory_status not in TRAJECTORY_STATUSES:
        raise ValueError(f"unknown trajectory status: {trajectory_status}")
    artifact = _artifact_identity(task, workspace)
    artifact_path = artifact["path"]
    required_tool = task.get("tool_name")
    if required_tool is not None and not isinstance(required_tool, str):
        raise ValueError("task tool_name must be a string when present")
    sequence_valid, sequence_status, sequence_diagnostic = _validate_event_sequences(events)
    claims = [event for event in events if event.get("event") == "agent_result"]
    invocations = [event for index, event in enumerate(events, 1)
                   if event.get("event") == "invoked"
                   and _event_targets(event, artifact_path, required_tool)]
    completions = [event for index, event in enumerate(events, 1)
                   if event.get("event") == "completed"
                   and _event_targets(event, artifact_path, required_tool)]
    positions = {id(event): index for index, event in enumerate(events, 1)}
    valid_call_ids = {
        event.get("call_id") for event in invocations
        if isinstance(event.get("call_id"), str) and event.get("call_id")
    }
    attempts: list[dict[str, Any]] = []
    attempt_completions: list[dict[str, Any] | None] = []
    for invocation in invocations:
        call_id = invocation.get("call_id")
        if not isinstance(call_id, str) or not call_id:
            attempts.append({
                "call_id": None,
                "status": "not_assessable",
                "reason": "missing_call_id",
            })
            attempt_completions.append(None)
            continue
        linked = [
            completion for completion in completions
            if completion.get("call_id") == call_id
            and positions[id(completion)] > positions[id(invocation)]
        ]
        if len(linked) != 1:
            attempts.append({
                "call_id": call_id,
                "status": "not_assessable",
                "reason": "missing_or_ambiguous_completion",
            })
            attempt_completions.append(None)
            continue
        completion = linked[0]
        attempt_completions.append(completion)
        exit_code = completion.get("exit_code")
        if completion.get("status") == "failed" or (
            isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0
        ):
            status = "failed"
            reason = "tool_failed"
        elif completion.get("status") != "completed" or exit_code != 0:
            status = "not_assessable"
            reason = "completion_contract_incomplete"
        else:
            reported_sha, action = _artifact_report(completion)
            actual_sha = artifact.get("actual_sha256")
            if action not in {"created", "updated"} or reported_sha is None:
                status = "not_assessable"
                reason = "artifact_provenance_unavailable"
            elif reported_sha != actual_sha or actual_sha != artifact.get("expected_sha256"):
                status = "failed"
                reason = "artifact_digest_mismatch"
            else:
                status = "passed"
                reason = "observed_completion_and_artifact_provenance"
        attempts.append({"call_id": call_id, "status": status, "reason": reason})

    permission_values = [event.get("permission") for event in invocations]
    if "denied" in permission_values:
        permission_status = "denied"
    elif "allowed" in permission_values:
        permission_status = "allowed"
    elif invocations:
        permission_status = "not_available"
    else:
        permission_status = "not_available"

    linked_completions = [
        completion for completion in completions
        if completion.get("call_id") in valid_call_ids
        and any(
            invocation.get("call_id") == completion.get("call_id")
            and positions[id(completion)] > positions[id(invocation)]
            for invocation in invocations
        )
    ]
    attempt_statuses = [attempt["status"] for attempt in attempts]
    if not invocations:
        process_status = "not_observed"
    elif trajectory_status != "complete":
        process_status = "not_assessable"
    elif not linked_completions:
        process_status = "not_observed"
    elif attempt_statuses and all(status == "failed" for status in attempt_statuses):
        process_status = "failed"
    elif len(attempt_statuses) == 1 and attempt_statuses == ["passed"]:
        process_status = "completed"
    else:
        process_status = "ambiguous"

    if len(attempts) == 1:
        assertion_status = attempts[0]["status"]
    elif not attempts:
        assertion_status = "not_assessable"
    elif all(status == "failed" for status in attempt_statuses):
        assertion_status = "failed"
    else:
        assertion_status = "not_assessable"
    if trajectory_status != "complete":
        assertion_status = "not_assessable"

    producer_values: list[bool] = []
    for attempt, completion in zip(attempts, attempt_completions):
        if completion is None:
            continue
        if attempt["status"] not in {"passed", "failed"}:
            continue
        reported_sha, action = _artifact_report(completion)
        producer_values.append(
            action in {"created", "updated"}
            and reported_sha == artifact.get("actual_sha256") == artifact.get("expected_sha256")
        )
    if assertion_status == "passed" and producer_values == [True]:
        artifact_produced = True
    elif producer_values and any(value is False for value in producer_values):
        artifact_produced = False
    else:
        artifact_produced = None

    if permission_status == "denied" and assertion_status == "passed":
        assertion_status = "failed"
    if not sequence_valid:
        process_status = "not_assessable"
        assertion_status = "not_assessable"
        artifact_produced = None

    return {
        "agent_claimed": any(event.get("claimed") is True for event in claims),
        "tool_invoked": bool(invocations),
        "tool_completed": bool(linked_completions),
        "call_identity_status": (
            "unavailable" if not valid_call_ids else
            "valid" if len(attempts) == 1 and attempts[0].get("call_id") else "ambiguous"
        ),
        "permission_status": permission_status,
        "process_status": process_status,
        "trajectory_status": trajectory_status,
        "sequence_status": sequence_status,
        "sequence_diagnostic": sequence_diagnostic,
        "attempts": attempts,
        "artifact_identity": artifact,
        "artifact_verified": artifact["verified"],
        "artifact_produced_by_observed_call": artifact_produced,
        "assertion_status": assertion_status,
    }


def _selftest() -> None:
    task = _load_json(FIXTURE_ROOT / "task.json")
    good = evaluate(task, _load_events(FIXTURE_ROOT / "good-events.jsonl"), FIXTURE_ROOT / "good-workspace")
    bad = evaluate(task, _load_events(FIXTURE_ROOT / "bad-events.jsonl"), FIXTURE_ROOT / "bad-workspace")
    if (
        good["assertion_status"] != "passed"
        or not good["artifact_verified"]
        or good["artifact_produced_by_observed_call"] is not True
    ):
        raise AssertionError(f"good fixture did not pass: {good}")
    if bad["agent_claimed"] is not True or bad["assertion_status"] != "failed":
        raise AssertionError(f"bad fixture incorrectly passed: {bad}")
    print("benchmark reliability pilot self-test: passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--task", type=Path)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trajectory-status", choices=sorted(TRAJECTORY_STATUSES), default="complete")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    if not all((args.task, args.events, args.workspace, args.output)):
        parser.error("--task, --events, --workspace and --output are required unless --selftest is used")
    result = evaluate(
        _load_json(args.task), _load_events(args.events), args.workspace,
        trajectory_status=args.trajectory_status,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
