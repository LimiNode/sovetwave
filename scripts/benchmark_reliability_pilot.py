#!/usr/bin/env python3
"""Run a deterministic evidence-grade benchmark pilot without model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "behavioral" / "fixtures" / "benchmark-reliability"


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
    return value.replace("\\", "/").lstrip("./")


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


def evaluate(task: dict[str, Any], events: list[dict[str, Any]], workspace: Path) -> dict[str, Any]:
    """Score only observed evidence; an agent claim is never sufficient."""
    artifact = _artifact_identity(task, workspace)
    artifact_path = artifact["path"]
    required_tool = task.get("tool_name")
    if required_tool is not None and not isinstance(required_tool, str):
        raise ValueError("task tool_name must be a string when present")
    claims = [event for event in events if event.get("event") == "agent_result"]
    invocations = [
        event for event in events
        if event.get("event") == "invoked" and _event_targets(event, artifact_path, required_tool)
    ]
    completions = [
        event for event in events
        if event.get("event") == "completed" and _event_targets(event, artifact_path, required_tool)
    ]
    call_ids = {event.get("call_id") for event in invocations if event.get("call_id")}
    linked_completions = [
        event for event in completions
        if not call_ids or event.get("call_id") in call_ids
    ]
    permission_values = [event.get("permission") for event in invocations]
    if "denied" in permission_values:
        permission_status = "denied"
    elif "allowed" in permission_values:
        permission_status = "allowed"
    elif invocations:
        permission_status = "not_available"
    else:
        permission_status = "not_available"

    failed_completion = any(
        event.get("status") == "failed"
        or (isinstance(event.get("exit_code"), int) and event.get("exit_code") != 0)
        for event in linked_completions
    )
    successful_completion = any(
        event.get("status") == "completed"
        and event.get("exit_code") == 0
        for event in linked_completions
    )
    if not invocations:
        process_status = "not_observed"
    elif not linked_completions:
        process_status = "not_observed"
    elif failed_completion:
        process_status = "failed"
    elif successful_completion:
        process_status = "completed"
    else:
        process_status = "not_observed"

    if not invocations or not linked_completions:
        assertion_status = "not_assessable"
    elif permission_status == "denied" or failed_completion:
        assertion_status = "failed"
    elif successful_completion and artifact["verified"]:
        assertion_status = "passed"
    else:
        assertion_status = "failed"

    return {
        "agent_claimed": any(event.get("claimed") is True for event in claims),
        "tool_invoked": bool(invocations),
        "tool_completed": bool(linked_completions),
        "permission_status": permission_status,
        "process_status": process_status,
        "artifact_identity": artifact,
        "artifact_verified": artifact["verified"],
        "assertion_status": assertion_status,
    }


def _selftest() -> None:
    task = _load_json(FIXTURE_ROOT / "task.json")
    good = evaluate(task, _load_events(FIXTURE_ROOT / "good-events.jsonl"), FIXTURE_ROOT / "good-workspace")
    bad = evaluate(task, _load_events(FIXTURE_ROOT / "bad-events.jsonl"), FIXTURE_ROOT / "bad-workspace")
    if good["assertion_status"] != "passed" or not good["artifact_verified"]:
        raise AssertionError(f"good fixture did not pass: {good}")
    if bad["agent_claimed"] is not True or bad["assertion_status"] == "passed":
        raise AssertionError(f"bad fixture incorrectly passed: {bad}")
    print("benchmark reliability pilot self-test: passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--task", type=Path)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    if not all((args.task, args.events, args.workspace, args.output)):
        parser.error("--task, --events, --workspace and --output are required unless --selftest is used")
    result = evaluate(_load_json(args.task), _load_events(args.events), args.workspace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
