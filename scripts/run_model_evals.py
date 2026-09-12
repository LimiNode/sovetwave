#!/usr/bin/env python3
"""Run controlled behavioral evaluations through a local agent CLI."""

from __future__ import annotations

import argparse
import atexit
from functools import lru_cache
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from eval_schema import rubric_axis_ids, validate_applicable_axes
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "evals" / "behavioral" / "cases"
DEFAULT_RESULTS = ROOT / "evals" / "behavioral" / "results"
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]+|Bearer\s+[A-Za-z0-9._-]+|(?:api[_ -]?key|access[_ -]?token)\s*[=:]\s*\S+)", re.IGNORECASE)
URL_CREDENTIAL = re.compile(r"(https?://)([^/@\s]+@)", re.IGNORECASE)
SAFE_PROVIDER_KEYS = frozenset({
    "name", "base_url", "wire_api", "requires_openai_auth", "supports_websockets", "env_key",
})
SENSITIVE_PROVIDER_KEYS = frozenset({
    "experimental_bearer_token",
    "http_headers",
    "env_http_headers",
    "query_params",
    "auth",
})
FAILED_STATUSES = frozenset({"failed", "invalid_empty_response", "timeout"})
THEMATIC_REFERENCES = frozenset({
    "agent-instructions.md",
    "architecture-decisions.md",
    "c-engineering.md",
    "code-economy.md",
    "cpp-callback-async-lifetime.md",
    "cpp-engineering.md",
    "cpp-application-architecture.md",
    "cpp-lifetime-and-queues.md",
    "cpp-review-workflow.md",
    "development-workflow-russian.md",
    "engineering-workflow.md",
    "history-and-sources.md",
    "house-conventions.md",
    "messaging-and-distributed-systems.md",
    "pedagogy-and-dialogue.md",
    "python-engineering.md",
    "python-backend-architecture.md",
    "qt-cpp-engineering.md",
    "verification-discipline.md",
})
CASE_RELATION_KINDS = frozenset({"contrast", "directional", "invariance"})
EXECUTION_MODES = frozenset({"prompt_only", "repository_grounded"})
CLAUDE_VARIANTS = ("baseline", "sovetwave_style_only", "sovetwave")
CORE_ABLATION = "__core__"
RUBRIC_AXES = rubric_axis_ids()


def validate_case_relations(
    cases: list[dict[str, Any]],
    case_sources: dict[str, Path],
) -> None:
    """Validate optional within-suite relationships between behavioral cases."""
    indexed = {case["id"]: case for case in cases}
    relations: dict[str, dict[str, str]] = {}
    for case in cases:
        case_id = case["id"]
        relation = case.get("relation")
        if relation is None:
            continue
        if not isinstance(relation, dict) or not set(relation).issubset({"kind", "base_case", "expect"}) or not {"kind", "base_case"}.issubset(relation):
            raise ValueError(f"{case_sources[case_id]}: relation for {case_id!r} needs kind, base_case, and optional expect")
        kind = relation.get("kind")
        base_case = relation.get("base_case")
        if kind not in CASE_RELATION_KINDS:
            raise ValueError(f"{case_sources[case_id]}: unsupported relation kind for {case_id!r}: {kind!r}")
        if not isinstance(base_case, str) or not base_case:
            raise ValueError(f"{case_sources[case_id]}: relation base_case for {case_id!r} must be a string")
        expect = relation.get("expect")
        if expect is not None and (not isinstance(expect, str) or not expect.strip()):
            raise ValueError(f"{case_sources[case_id]}: relation expect for {case_id!r} must be a non-empty string")
        if base_case == case_id:
            raise ValueError(f"{case_sources[case_id]}: case {case_id!r} cannot relate to itself")
        if base_case not in indexed:
            raise ValueError(f"{case_sources[case_id]}: unknown relation base_case {base_case!r} for {case_id!r}")
        if case_sources[base_case] != case_sources[case_id]:
            raise ValueError(f"{case_sources[case_id]}: relation for {case_id!r} must stay within one suite")
        normalized = {"kind": kind, "base_case": base_case}
        if expect is not None:
            normalized["expect"] = expect
        relations[case_id] = normalized

    for case_id in relations:
        path: list[str] = []
        current = case_id
        while current in relations:
            if current in path:
                cycle = " -> ".join(path[path.index(current):] + [current])
                raise ValueError(f"case relation cycle: {cycle}")
            path.append(current)
            current = relations[current]["base_case"]


def load_cases(case_dir: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    case_sources: dict[str, Path] = {}
    for path in sorted(case_dir.glob("*.json")):
        suite = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(suite.get("cases"), list):
            raise ValueError(f"{path}: cases must be an array")
        suite_axes = suite.get("applicable_axes")
        suite_execution_mode = suite.get("execution_mode", "prompt_only")
        if suite_execution_mode not in EXECUTION_MODES:
            raise ValueError(f"{path}: unsupported execution_mode {suite_execution_mode!r}")
        try:
            validate_applicable_axes(suite_axes, allowed=RUBRIC_AXES)
        except ValueError as error:
            raise ValueError(f"{path}: {error}") from error
        for case in suite["cases"]:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not isinstance(case.get("prompt"), str):
                raise ValueError(f"{path}: every case needs string id and prompt")
            if not isinstance(case.get("assertions"), list) or not all(
                isinstance(assertion, str) and assertion.strip() for assertion in case["assertions"]
            ):
                raise ValueError(f"{path}: every case needs non-empty string assertions")
            applicable_axes = case.get("applicable_axes", suite_axes)
            execution_mode = case.get("execution_mode", suite_execution_mode)
            if execution_mode not in EXECUTION_MODES:
                raise ValueError(f"{path}: unsupported execution_mode for {case['id']!r}: {execution_mode!r}")
            fixture = case.get("fixture", suite.get("fixture"))
            if fixture is not None:
                if not isinstance(fixture, str) or not fixture or Path(fixture).is_absolute() or ".." in Path(fixture).parts:
                    raise ValueError(f"{path}: fixture for {case['id']!r} must be a relative path without '..'")
                fixture_path = (path.parent.parent / "fixtures" / fixture).resolve()
                fixture_root = (path.parent.parent / "fixtures").resolve()
                if fixture_root not in fixture_path.parents and fixture_path != fixture_root:
                    raise ValueError(f"{path}: fixture for {case['id']!r} escapes the fixtures directory")
                if not fixture_path.is_dir():
                    raise ValueError(f"{path}: fixture directory does not exist for {case['id']!r}: {fixture_path}")
            try:
                validate_applicable_axes(applicable_axes, allowed=RUBRIC_AXES)
            except ValueError as error:
                raise ValueError(f"{path}: {error}") from error
            if "applicable_axes" not in case and suite_axes is not None:
                case["applicable_axes"] = list(suite_axes)
            case["execution_mode"] = execution_mode
            if fixture is not None:
                case["fixture"] = fixture
                case["_fixture_path"] = str(fixture_path)
            if case["id"] in seen:
                raise ValueError(f"duplicate behavioral case id: {case['id']}")
            seen.add(case["id"])
            case_sources[case["id"]] = path
            cases.append(case)
    if not cases:
        raise ValueError(f"no behavioral cases in {case_dir}")
    validate_case_relations(cases, case_sources)
    return cases


def redact_secrets(text: str) -> str:
    return URL_CREDENTIAL.sub(r"\1[redacted]@", SECRET.sub("[redacted credential]", text))


def redact_command(command: list[str]) -> list[str]:
    """Return a safe-to-store representation of an executable command."""
    return [redact_secrets(argument) for argument in command]


def resolved_model_from_stderr(stderr: str) -> str | None:
    """Extract the non-secret model label printed by Codex/Claude CLIs."""
    match = re.search(r"(?:^|\n)model:\s*([^\s\r\n]+)", stderr, re.IGNORECASE)
    return match.group(1) if match else None


def reported_tokens_from_stderr(stderr: str) -> int | None:
    """Extract the CLI's reported token count without depending on separators."""
    match = re.search(r"tokens used[ \t]*\r?\n[ \t]*([0-9 ,\u00a0\u202f]+)", stderr, re.IGNORECASE)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


def classify_semantic_response(response: str, status: str) -> str:
    """Apply a conservative service-level class before human semantic grading."""
    if not response.strip():
        return "empty"
    lowered = response.strip().lower()
    first_line = lowered.splitlines()[0]
    # Recognise only strict leading templates; qualified statements and
    # quoted service errors remain ordinary task answers.
    if first_line.startswith(("cannot comply", "i can't perform", "i cannot perform", "не могу выполнить", "невозможно выполнить")):
        return "premise_refusal"
    if first_line.startswith(("permission denied", "authentication required", "unauthorized", "tool error")):
        return "tool_failure_answer"
    if first_line.startswith(("план:", "plan:", "шаг 1:", "step 1:")) and len(response.splitlines()) < 8:
        return "plan_only"
    return "task_answer" if status == "completed" else "partial"


@lru_cache(maxsize=1)
def repository_revision() -> str | None:
    """Return the evaluated skill revision without failing an eval run."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            encoding="utf-8", errors="replace", capture_output=True,
            timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    revision = (completed.stdout or "").strip()
    return revision if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{7,40}", revision) else None


@lru_cache(maxsize=1)
def repository_revision_dirty() -> bool | None:
    """Report whether tracked Sovetwave skill files differ from HEAD."""
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no", "--", "skills/sovetwave"],
            cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return bool((completed.stdout or "").strip()) if completed.returncode == 0 else None


@lru_cache(maxsize=1)
def repository_material_inputs_dirty() -> bool | None:
    """Report whether tracked or untracked skill, case, or fixture inputs are dirty."""
    try:
        completed = subprocess.run(
            [
                "git", "status", "--porcelain", "--untracked-files=all", "--",
                "skills/sovetwave", "evals/behavioral/cases", "evals/behavioral/fixtures",
            ],
            cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return bool((completed.stdout or "").strip()) if completed.returncode == 0 else None


def result_key(result: dict[str, Any]) -> tuple[str, int, int, str]:
    """Identify one deterministic case/repetition/variant invocation."""
    return (
        str(result.get("case_id", "")),
        int(result.get("repetition", 0)),
        int(result.get("sequence", 0)),
        str(result.get("variant", "")),
    )


def append_checkpoint(path: Path, result: dict[str, Any]) -> None:
    """Persist one completed invocation before scheduling the next one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def acquire_checkpoint_lock(checkpoint: Path) -> Path:
    """Reserve a checkpoint for one runner, preventing mixed observations."""
    lock_path = checkpoint.with_suffix(checkpoint.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as error:
        raise ValueError(
            f"checkpoint is already in use: {checkpoint}; wait for its runner or choose another --checkpoint"
        ) from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as lock:
        json.dump({"pid": os.getpid(), "created_at": datetime.now(UTC).isoformat()}, lock)
        lock.flush()
        os.fsync(lock.fileno())
    return lock_path


def release_checkpoint_lock(lock_path: Path) -> None:
    """Remove this runner's advisory lock after a normal process exit."""
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def write_partial(path: Path, metadata: dict[str, Any], results: list[dict[str, Any]]) -> None:
    """Atomically publish a readable partial run for live inspection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = dict(metadata)
    payload["partial"] = True
    payload["results"] = results
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_checkpoint(path: Path) -> list[dict[str, Any]]:
    """Load append-only results, tolerating a truncated final line."""
    if not path.is_file():
        return []
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(result, dict) and "case_id" in result and "variant" in result:
            key = result_key(result)
            if key in seen:
                raise ValueError(
                    f"checkpoint contains duplicate invocation {key}; do not use it for a statistical run"
                )
            seen.add(key)
            results.append(result)
    return results


def toml_scalar(value: Any) -> str:
    """Render the subset of TOML values accepted by Codex --config."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    raise ValueError(f"unsupported provider configuration value: {value!r}")


def codex_provider_overrides(config_path: Path) -> list[str]:
    """Copy only the selected model provider from a user Codex config.

    Eval runs deliberately ignore all ordinary user configuration. A local
    provider is an explicit exception: its endpoint definition must accompany
    the isolated invocation, while credentials continue to come from
    CODEX_HOME in the usual Codex way.
    """
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"cannot read Codex provider config {config_path}: {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"invalid TOML in Codex provider config {config_path}: {error}") from error

    provider = config.get("model_provider")
    providers = config.get("model_providers")
    if not isinstance(provider, str) or not provider:
        raise ValueError(f"{config_path}: expected top-level string model_provider")
    if not isinstance(providers, dict) or not isinstance(providers.get(provider), dict):
        raise ValueError(f"{config_path}: no [model_providers.{provider}] section")

    overrides = ["--config", f"model_provider={toml_scalar(provider)}"]
    for key, value in providers[provider].items():
        if not isinstance(key, str):
            raise ValueError(f"{config_path}: provider keys must be strings")
        if key not in SAFE_PROVIDER_KEYS:
            if key in SENSITIVE_PROVIDER_KEYS:
                raise ValueError(
                    f"{config_path}: provider key {key!r} is sensitive; use env_key instead of copying credentials"
                )
            raise ValueError(f"{config_path}: unsupported provider key {key!r}; refusing to copy it")
        if key == "base_url":
            if not isinstance(value, str) or not value:
                raise ValueError(f"{config_path}: base_url must be a non-empty string")
            parsed = urlsplit(value)
            if parsed.username or parsed.password:
                raise ValueError(f"{config_path}: base_url must not contain URL credentials")
        overrides.extend(["--config", f"model_providers.{provider}.{key}={toml_scalar(value)}"])
    return overrides


def disable_reference(skill_dir: Path, reference_name: str) -> None:
    """Remove one conditional reference from an isolated skill copy."""
    if reference_name not in THEMATIC_REFERENCES:
        raise ValueError(f"reference is not available for thematic ablation: {reference_name!r}")
    reference = skill_dir / "references" / reference_name
    if reference.name != reference_name or not reference.is_file():
        raise ValueError(f"unknown skill reference for ablation: {reference_name!r}")

    skill_file = skill_dir / "SKILL.md"
    marker = f"[{reference_name}](references/{reference_name})"
    lines = skill_file.read_text(encoding="utf-8").splitlines(keepends=True)
    retained = [line for line in lines if marker not in line]
    if len(retained) == len(lines):
        raise ValueError(f"{reference_name!r} is not a conditional reference in {skill_file}")
    skill_file.write_text("".join(retained), encoding="utf-8")
    reference.unlink()


def make_workspace(
    root: Path,
    styled: bool,
    ablated_reference: str | None = None,
    claude_full_skill: bool = False,
    fixture: Path | None = None,
) -> tempfile.TemporaryDirectory[str]:
    workspace = tempfile.TemporaryDirectory(prefix="sovetwave-eval-")
    if fixture is not None:
        fixture_path = Path(fixture).resolve()
        if not fixture_path.is_dir():
            workspace.cleanup()
            raise ValueError(f"fixture directory does not exist: {fixture_path}")
        shutil.copytree(fixture_path, workspace.name, dirs_exist_ok=True)
    if styled:
        destination = Path(workspace.name) / ".agents" / "skills" / "sovetwave"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root / "skills" / "sovetwave", destination)
        if claude_full_skill:
            claude_destination = Path(workspace.name) / ".claude" / "skills" / "sovetwave"
            claude_destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(root / "skills" / "sovetwave", claude_destination)
        if ablated_reference == CORE_ABLATION:
            (destination / "SKILL.md").unlink()
        elif ablated_reference is not None:
            disable_reference(destination, ablated_reference)
    return workspace


def claude_variant_plan(repetition: int, *, full_skill: bool) -> list[str]:
    """Return a rotated Claude arm order for one repetition.

    The two-arm style-only comparison alternates its first position. A full
    Claude comparison uses a three-arm Latin-square cycle so voice-only and
    full-skill effects are not conflated with a fixed position.
    """
    if full_skill:
        cycle = ["baseline", "sovetwave_style_only", "sovetwave"]
        return cycle[(repetition - 1) % 3:] + cycle[:(repetition - 1) % 3]
    return ["baseline", "sovetwave_style_only"] if repetition % 2 else ["sovetwave_style_only", "baseline"]


def parse_claude_stream(stream: str) -> tuple[str, list[str]]:
    """Extract the final answer and observed tool names from Claude JSONL."""
    response, tool_names, _ = parse_claude_stream_metadata(stream)
    return response, tool_names


def parse_claude_stream_metadata(stream: str) -> tuple[str, list[str], list[str]]:
    """Extract answer, tools, and model names from Claude JSONL."""
    if not stream:
        return "", [], []
    text_parts: list[str] = []
    tool_names: list[str] = []
    model_names: list[str] = []
    parsed_any = False
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        parsed_any = True
        for candidate in (event.get("model"), event.get("message", {}).get("model") if isinstance(event.get("message"), dict) else None):
            if isinstance(candidate, str) and candidate:
                model_names.append(candidate)
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            text_parts = [event["result"]]
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else event.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    text_parts.append(block["text"])
                if block.get("type") == "tool_use" and isinstance(block.get("name"), str):
                    tool_names.append(block["name"])
    if not parsed_any:
        return stream, tool_names, model_names
    # A result event is authoritative; otherwise concatenate assistant text
    # blocks while removing duplicate final-result text.
    response = text_parts[-1] if text_parts else ""
    return response, list(dict.fromkeys(tool_names)), list(dict.fromkeys(model_names))


def parse_codex_json_stream(stream: str) -> dict[str, Any]:
    """Extract structured usage and tool telemetry from Codex ``--json`` events.

    Codex event schemas evolve, so unknown events are ignored and numeric usage
    fields are copied only when present. The final answer still comes from
    ``--output-last-message``; this parser is telemetry-only.
    """
    usage: dict[str, int] = {}
    usage_events = 0
    duplicate_usage_events = 0
    event_types: list[str] = []
    items_by_id: dict[str, str] = {}
    anonymous_items = 0
    reference_reads: list[str] = []

    def safe_reference_path(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.replace("\\", "/")
        marker = "skills/sovetwave/"
        if marker not in normalized:
            return None
        return normalized[normalized.index(marker):]
    for line in (stream or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if isinstance(event_type, str) and event_type not in event_types:
            event_types.append(event_type)
        # Codex reports aggregate turn usage on turn.completed. Do not sum
        # arbitrary nested usage objects from progress events.
        if event_type == "turn.completed":
            if usage_events:
                duplicate_usage_events += 1
            usage_events += 1
            candidate_usage = event.get("usage")
            allowed_usage = {
                "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                "output_tokens", "reasoning_output_tokens",
            }
            if isinstance(candidate_usage, dict):
                for key in allowed_usage:
                    value = candidate_usage.get(key)
                    if isinstance(value, int) and not isinstance(value, bool):
                        # Keep each aggregate snapshot separate.  A second
                        # ``turn.completed`` is ambiguous and must never
                        # silently double the turn-level usage.
                        if usage_events == 1:
                            usage[key] = value
        item = event.get("item")
        if isinstance(item, dict):
            item_type = item.get("type", "")
            item_id = item.get("id")
            if isinstance(item_type, str) and isinstance(item_id, str) and item_id:
                items_by_id[item_id] = item_type
            elif isinstance(item_type, str) and ("tool" in item_type or "command" in item_type):
                # Without item.id this is an anonymous lifecycle event, not a
                # deduplicated tool-call count; retain it only as defensive
                # telemetry for malformed/older streams.
                anonymous_items += 1
            path = item.get("path") or item.get("file")
            explicit_read = isinstance(item_type, str) and item_type.lower() in {
                "file_read", "file_read_result", "read_file", "file_read_request",
            }
            safe_path = safe_reference_path(path)
            if explicit_read and safe_path and safe_path not in reference_reads:
                reference_reads.append(safe_path)
        if event_type in {"file_read", "file_read_result", "read_file"}:
            path = event.get("path") or event.get("file")
            safe_path = safe_reference_path(path)
            if safe_path and safe_path not in reference_reads:
                reference_reads.append(safe_path)
    item_counts: dict[str, int] = {}
    for item_type in items_by_id.values():
        item_counts[item_type] = item_counts.get(item_type, 0) + 1
    # A tool call is one unique item.id whose type is an explicitly known
    # tool item.  Lifecycle events for the same id are therefore counted once.
    tool_types = {
        "command_execution", "mcp_tool_call", "collab_tool_call",
        "web_search", "file_change",
    }
    unique_tool_calls = sum(count for item_type, count in item_counts.items() if item_type in tool_types)
    if usage_events == 0:
        usage_status = "not_available"
    elif usage_events > 1:
        usage = {}
        usage_status = "ambiguous_duplicate_turn_completed"
    elif usage:
        usage_status = "valid"
    else:
        usage_status = "missing"
    return {
        "usage": usage or None,
        "usage_status": usage_status,
        "usage_events": usage_events,
        "duplicate_usage_events": duplicate_usage_events,
        "event_types": event_types,
        "tool_calls": unique_tool_calls if items_by_id else None,
        "anonymous_tool_items": anonymous_items,
        "item_counts_by_type": item_counts,
        "reference_files_read": reference_reads,
    }


def prepare_claude_settings(source: Path | None, workspace: Path) -> Path | None:
    """Create an ephemeral settings file containing only proxy-safe settings.

    Claude's ``user`` source also exposes personal skills. Copying only the
    environment and model fields preserves a proxy endpoint without allowing
    personal skill/plugin discovery to contaminate the experiment. The file
    lives below the temporary workspace and is removed with it.
    """
    if source is None:
        return None
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise ValueError(f"cannot read Claude settings {source}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid Claude settings JSON {source}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"Claude settings must be a JSON object: {source}")
    isolated: dict[str, Any] = {}
    for key in ("env", "model"):
        value = payload.get(key)
        if value is not None:
            isolated[key] = value
    destination = workspace / ".claude" / "eval-settings.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(isolated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def claude_settings_metadata(source: Path | None) -> dict[str, str | None]:
    """Return non-sensitive model/endpoint provenance from Claude settings."""
    if source is None:
        return {"configured_model": None, "proxy_host": None}
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"configured_model": None, "proxy_host": None}
    env = payload.get("env", {}) if isinstance(payload, dict) else {}
    configured_model = env.get("ANTHROPIC_MODEL") if isinstance(env, dict) else None
    if not isinstance(configured_model, str):
        configured_model = payload.get("model") if isinstance(payload, dict) and isinstance(payload.get("model"), str) else None
    base_url = env.get("ANTHROPIC_BASE_URL") if isinstance(env, dict) else None
    proxy_host = None
    if isinstance(base_url, str):
        try:
            proxy_host = urlsplit(base_url).hostname
        except ValueError:
            proxy_host = None
    return {"configured_model": configured_model, "proxy_host": proxy_host}


def execute_command(
    provider: str,
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Run a model command and reap its child tree on timeout."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        else:
            process.kill()
        try:
            stdout, stderr = process.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            # A provider child can keep an inherited pipe open even after
            # taskkill. Never let cleanup defeat the invocation timeout.
            process.kill()
            stdout, stderr = "", "cleanup timed out after terminating the process tree"
        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr) from error
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def command_for(
    provider: str,
    workspace: Path,
    prompt: str,
    styled: bool,
    model: str | None,
    output_path: Path,
    codex_overrides: list[str] | None = None,
    activation: str = "explicit",
    claude_full_skill: bool = False,
    claude_setting_sources: str = "project",
    claude_variant: str | None = None,
    execution_mode: str | None = None,
    claude_settings: Path | None = None,
) -> list[str]:
    if provider == "codex":
        command = [
            "codex", "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
            "--sandbox", "read-only", "-C", str(workspace),
            "--json",
            "--output-last-message", str(output_path),
        ]
        if codex_overrides:
            command.extend(codex_overrides)
        if model:
            command.extend(["--model", model])
        marker_allowed = styled and activation == "explicit" and (workspace / ".agents" / "skills" / "sovetwave" / "SKILL.md").is_file()
        return command + (["$sovetwave\n" + prompt] if marker_allowed else [prompt])
    if provider == "claude":
        if execution_mode is None:
            execution_mode = "repository_grounded" if claude_full_skill else "prompt_only"
        if execution_mode not in EXECUTION_MODES:
            raise ValueError(f"unsupported Claude execution mode: {execution_mode!r}")
        if claude_variant is None:
            claude_variant = "sovetwave" if claude_full_skill and styled else ("sovetwave_style_only" if styled else "baseline")
        if claude_variant not in CLAUDE_VARIANTS:
            raise ValueError(f"unsupported Claude variant: {claude_variant!r}")
        full_skill = claude_variant == "sovetwave"
        # Prompt-only cases need only the Skill tool so every arm has the same
        # minimal surface. Repository-grounded cases additionally need Read
        # and Bash to inspect the supplied fixture and run its checks.
        tool_set = "Skill" if execution_mode == "prompt_only" else "Skill,Read,Bash"
        # Keep the prompt immediately after --print. Claude's variadic
        # --allowedTools and --add-dir options otherwise consume a trailing
        # positional prompt as another list item.
        command = ["claude", "--print", prompt]
        command.extend([
            "--output-format", "stream-json",
            "--verbose",
            "--tools", tool_set,
            "--allowedTools", tool_set,
            "--setting-sources", "project" if claude_settings is not None else claude_setting_sources,
        ])
        if claude_settings is not None:
            command.extend(["--settings", str(claude_settings)])
        if execution_mode == "repository_grounded":
            # Avoid Plan mode, which turns a review prompt into a plan-only
            # interaction. dontAsk is safe here because the fixture is
            # isolated and the allowed tool set excludes editing tools.
            command.extend(["--permission-mode", "dontAsk"])
        if styled:
            command.extend(["--append-system-prompt-file", str(ROOT / "output-styles" / "sovetwave.md")])
        if full_skill or execution_mode == "repository_grounded":
            command.extend(["--add-dir", str(workspace)])
        if model:
            command.extend(["--model", model])
        return command
    raise ValueError(f"unsupported provider: {provider}")


def variant_name(styled: bool, ablated_reference: str | None) -> str:
    if ablated_reference == CORE_ABLATION:
        return "sovetwave_without_core"
    if ablated_reference is not None:
        return "sovetwave_without_reference"
    return "sovetwave" if styled else "baseline"


def variant_plan(
    ablated_reference: str | None,
    repetition: int,
) -> list[tuple[bool, str | None]]:
    """Rotate variant order to reduce position and temporal bias."""
    plan = [(False, None), (True, None)] if repetition % 2 else [(True, None), (False, None)]
    if ablated_reference is None:
        return plan
    ablated = (True, ablated_reference)
    return {
        1: [(False, None), (True, None), ablated],
        2: [(True, None), ablated, (False, None)],
        0: [ablated, (False, None), (True, None)],
    }[repetition % 3]


def run_variant(
    provider: str,
    case: dict[str, Any],
    styled: bool,
    model: str | None,
    timeout: int,
    dry_run: bool,
    codex_overrides: list[str] | None = None,
    ablated_reference: str | None = None,
    repetition: int = 1,
    sequence: int = 1,
    activation: str = "explicit",
    claude_full_skill: bool = False,
    claude_setting_sources: str = "project",
    claude_variant: str | None = None,
    claude_settings_source: Path | None = None,
    attempt: int = 1,
    recovered: bool = False,
    original_process_status: str | None = None,
) -> dict[str, Any]:
    if ablated_reference is not None and not styled:
        raise ValueError("a reference can be ablated only from a Sovetwave variant")
    fixture = Path(case["_fixture_path"]) if case.get("_fixture_path") else None
    effective_full_skill = (
        claude_variant == "sovetwave"
        if provider == "claude" and claude_variant is not None
        else claude_full_skill
    )
    started = time.monotonic()
    with make_workspace(ROOT, styled, ablated_reference, effective_full_skill, fixture) as temp_dir:
        workspace = Path(temp_dir)
        isolated_settings = prepare_claude_settings(claude_settings_source, workspace) if provider == "claude" else None
        response_path = workspace / "last-message.txt"
        command = command_for(
            provider, workspace, case["prompt"], styled, model, response_path,
            codex_overrides, activation, effective_full_skill, claude_setting_sources,
            claude_variant, case.get("execution_mode", "prompt_only"), isolated_settings,
        )
        selected_variant = claude_variant or variant_name(styled, ablated_reference)
        result: dict[str, Any] = {
            "case_id": case["id"],
            "variant": selected_variant,
            "repetition": repetition,
            "sequence": sequence,
            "activation": activation,
            "execution_mode": case.get("execution_mode", "prompt_only"),
            "prompt": redact_secrets(case["prompt"]),
            "assertions": case.get("assertions", []),
            "applicable_axes": case.get("applicable_axes"),
            "command": redact_command(command),
            "provider": provider,
            "requested_model": model,
            "attempt": attempt,
            "recovered": recovered,
            "reference_files_read": [],
            "reference_trace_status": "not_available",
            "skill_revision": repository_revision(),
            "skill_revision_dirty": repository_revision_dirty(),
            "material_inputs_dirty": repository_material_inputs_dirty(),
            "fixture": case.get("fixture"),
        }
        if original_process_status is not None:
            result["original_process_status"] = original_process_status
        if provider == "claude":
            result.update({
                "claude_variant": claude_variant or ("sovetwave" if styled and claude_full_skill else "sovetwave_style_only" if styled else "baseline"),
                "skill_available": bool((workspace / ".claude" / "skills" / "sovetwave" / "SKILL.md").is_file()),
                "tool_trace": [],
                "skill_invoked": False,
                "resolved_models": [],
            })
        if ablated_reference is not None:
            result["ablated_reference"] = ablated_reference
        if dry_run:
            result["status"] = "planned"
            result["process_status"] = "planned"
            result["semantic_status"] = "not_run"
            result["semantic_class"] = "not_run"
            return result
        try:
            completed = execute_command(provider, command, cwd=workspace, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            result.update({
                "status": "timeout",
                "process_status": "timeout",
                "semantic_status": "not_run",
                "returncode": None,
                "response": "",
                "stderr": redact_secrets(str(error)),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "semantic_class": "empty",
            })
            return result
        except OSError as error:
            result.update({
                "status": "failed",
                "process_status": "failed",
                "semantic_status": "not_run",
                "returncode": None,
                "response": "",
                "stderr": redact_secrets(str(error)),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "semantic_class": "tool_failure_answer",
            })
            return result
        response = response_path.read_text(encoding="utf-8") if response_path.exists() else (completed.stdout or "")
        if provider == "codex":
            codex_telemetry = parse_codex_json_stream(completed.stdout or "")
            result["codex_usage"] = codex_telemetry["usage"]
            result["codex_usage_status"] = codex_telemetry["usage_status"]
            result["codex_usage_events"] = codex_telemetry["usage_events"]
            result["codex_duplicate_usage_events"] = codex_telemetry["duplicate_usage_events"]
            result["codex_event_types"] = codex_telemetry["event_types"]
            result["codex_tool_calls"] = codex_telemetry["tool_calls"]
            result["codex_anonymous_tool_items"] = codex_telemetry["anonymous_tool_items"]
            result["codex_item_counts_by_type"] = codex_telemetry["item_counts_by_type"]
            if codex_telemetry["reference_files_read"]:
                result["reference_files_read"] = codex_telemetry["reference_files_read"]
                result["reference_trace_status"] = "observed"
        if provider == "claude":
            response, tool_trace, resolved_models = parse_claude_stream_metadata(response)
            result["tool_trace"] = tool_trace
            result["skill_invoked"] = "Skill" in tool_trace
            result["resolved_models"] = resolved_models
        stderr_model = resolved_model_from_stderr(completed.stderr or "")
        if provider == "claude" and len(result.get("resolved_models", [])) == 1:
            result["resolved_model"] = result["resolved_models"][0]
        else:
            result["resolved_model"] = stderr_model
        result["reported_tokens"] = reported_tokens_from_stderr(completed.stderr or "")
        response = response.strip()
        if completed.returncode != 0:
            status = "failed"
        elif not response:
            status = "invalid_empty_response"
        else:
            status = "completed"
        result.update({
            "status": status,
            "process_status": status,
            "semantic_status": "unrated" if status == "completed" else "not_run",
            "semantic_class": classify_semantic_response(response, status),
            "returncode": completed.returncode,
            "response": response,
            "stderr": redact_secrets((completed.stderr or "").strip()),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        })
        return result


def summarize_ablation(
    results: list[dict[str, Any]],
    expected_ablations: int,
    dry_run: bool,
) -> str:
    """State whether every planned ablated variant was actually observed."""
    ablated = [result for result in results if result["variant"].startswith("sovetwave_without_")]
    if dry_run:
        return "planned"
    if not ablated:
        return "not_tested"
    if len(ablated) == expected_ablations and all(result.get("status") == "completed" for result in ablated):
        return "completed"
    return "partial"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("codex", "claude"), required=True)
    parser.add_argument("--model")
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASES)
    parser.add_argument(
        "--case-id",
        action="append",
        help="run a behavioral case by id; repeat the option to run a related pair",
    )
    parser.add_argument(
        "--ablate-reference",
        help="for Codex only, remove this conditional skill reference from the ablated variant (for example cpp-engineering.md)",
    )
    parser.add_argument("--ablate-core", action="store_true", help="remove the whole core skill from the ablated variant")
    parser.add_argument(
        "--claude-full-skill",
        action="store_true",
        help="for Claude, run vanilla, voice-only, and full-skill arms (without it, run vanilla vs voice-only)",
    )
    parser.add_argument(
        "--claude-setting-sources",
        default="project",
        help="Claude setting sources when no isolated settings file is supplied (default: project)",
    )
    parser.add_argument(
        "--claude-settings",
        type=Path,
        help="optional user settings JSON; only env/model are copied into an ephemeral project settings file, isolating personal skills while preserving a proxy",
    )
    parser.add_argument("--repetitions", type=int, default=1, help="number of independent runs per case and variant")
    parser.add_argument(
        "--activation",
        choices=("explicit", "natural"),
        default="explicit",
        help="Codex activation condition: inject $sovetwave explicitly or leave activation to the prompt",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="append one JSON result per invocation here (default: output with .jsonl suffix)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume from an existing checkpoint and skip already recorded invocations",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true", help="run remaining variants after a failed model invocation")
    parser.add_argument(
        "--codex-provider-config",
        type=Path,
        help="copy the selected model provider from this Codex config into isolated Codex runs",
    )
    args = parser.parse_args()

    if args.codex_provider_config is not None and args.provider != "codex":
        parser.error("--codex-provider-config is only valid with --provider codex")
    if args.claude_full_skill and args.provider != "claude":
        parser.error("--claude-full-skill is only valid with --provider claude")
    if args.claude_setting_sources != "project" and args.provider != "claude":
        parser.error("--claude-setting-sources is only valid with --provider claude")
    if args.claude_settings is not None and args.provider != "claude":
        parser.error("--claude-settings is only valid with --provider claude")
    if args.claude_settings is not None and not args.claude_settings.is_file():
        parser.error(f"Claude settings file does not exist: {args.claude_settings}")
    if args.provider == "claude":
        sources = [item.strip() for item in args.claude_setting_sources.split(",") if item.strip()]
        if not sources or any(item not in {"user", "project", "local"} for item in sources):
            parser.error("--claude-setting-sources must contain only user, project, and local")
    if args.ablate_reference is not None and args.provider != "codex":
        parser.error("--ablate-reference is currently supported only for provider codex")
    if args.ablate_core and args.provider != "codex":
        parser.error("--ablate-core is currently supported only for provider codex")
    if args.ablate_core and args.ablate_reference is not None:
        parser.error("--ablate-core cannot be combined with --ablate-reference")
    if args.provider == "claude" and args.activation == "natural":
        parser.error("--activation natural is currently supported only for Codex")
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if (args.ablate_reference is not None or args.ablate_core) and args.repetitions < 2:
        parser.error("ablation requires at least 2 repetitions")
    if args.ablate_reference is not None:
        reference = ROOT / "skills" / "sovetwave" / "references" / args.ablate_reference
        if (
            args.ablate_reference not in THEMATIC_REFERENCES
            or reference.name != args.ablate_reference
            or not reference.is_file()
            or f"[{args.ablate_reference}](references/{args.ablate_reference})"
            not in (ROOT / "skills" / "sovetwave" / "SKILL.md").read_text(encoding="utf-8")
        ):
            parser.error(f"--ablate-reference must name a conditional skill reference: {args.ablate_reference!r}")
    try:
        codex_overrides = (
            codex_provider_overrides(args.codex_provider_config)
            if args.codex_provider_config is not None
            else None
        )
    except ValueError as error:
        parser.error(str(error))

    cases = load_cases(args.case_dir)
    ablation_target = CORE_ABLATION if args.ablate_core else args.ablate_reference
    if args.case_id is not None:
        if len(set(args.case_id)) != len(args.case_id):
            parser.error("--case-id values must be unique")
        indexed_cases = {case["id"]: case for case in cases}
        missing = [case_id for case_id in args.case_id if case_id not in indexed_cases]
        if missing:
            parser.error(f"no behavioral case with id {missing[0]!r}")
        cases = [indexed_cases[case_id] for case_id in args.case_id]
        if args.limit is not None:
            parser.error("--limit cannot be combined with explicit --case-id selection")
    if args.limit is not None:
        cases = cases[:args.limit]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or DEFAULT_RESULTS / f"{timestamp}-{args.provider}.json"
    checkpoint = args.checkpoint or output.with_suffix(".jsonl")
    lock_path = acquire_checkpoint_lock(checkpoint)
    atexit.register(release_checkpoint_lock, lock_path)
    if args.resume:
        results = load_checkpoint(checkpoint)
        if results:
            print(f"Resuming {len(results)} recorded variants from {checkpoint}", flush=True)
    else:
        results = []
        if checkpoint.exists():
            checkpoint.unlink()
    stopped_early = False
    use_claude_arms = args.provider == "claude" and args.claude_full_skill
    variant_orders = []
    for repetition in range(1, args.repetitions + 1):
        if use_claude_arms:
            names = claude_variant_plan(repetition, full_skill=True)
        elif args.provider == "claude":
            names = claude_variant_plan(repetition, full_skill=False)
        else:
            names = [
                variant_name(styled, ablated_reference)
                for styled, ablated_reference in variant_plan(ablation_target, repetition)
            ]
        variant_orders.append({"repetition": repetition, "variants": names})
    resume_keys = {result_key(result) for result in results}
    partial_path = output.with_suffix(".partial.json")
    partial_metadata = {
        "schema_version": "1.5",
        "provider": args.provider,
        "model": args.model,
        "dry_run": args.dry_run,
        "repetitions": args.repetitions,
        "variant_set": "claude_three_arm" if use_claude_arms else "claude_two_arm" if args.provider == "claude" else "codex_two_arm",
        "case_ids": [case["id"] for case in cases],
        "variant_orders": variant_orders,
        "checkpoint": str(checkpoint),
    }
    write_partial(partial_path, partial_metadata, results)
    for case in cases:
        for repetition in range(1, args.repetitions + 1):
            if args.provider == "claude":
                planned_names = claude_variant_plan(repetition, full_skill=args.claude_full_skill)
                planned = [
                    (name != "baseline", None, name)
                    for name in planned_names
                ]
            else:
                planned = [
                    (styled, ablated_reference, None)
                    for styled, ablated_reference in variant_plan(ablation_target, repetition)
                ]
            for sequence, (styled, ablated_reference, claude_variant) in enumerate(planned, start=1):
                planned_variant = claude_variant or variant_name(styled, ablated_reference)
                candidate_key = (case["id"], repetition, sequence, planned_variant)
                if candidate_key in resume_keys:
                    print(f"[skip] {case['id']} r{repetition} {planned_variant} (checkpoint)", flush=True)
                    continue
                result = run_variant(
                    args.provider,
                    case,
                    styled,
                    args.model,
                    args.timeout,
                    args.dry_run,
                    codex_overrides,
                    ablated_reference,
                    repetition,
                    sequence,
                    args.activation,
                    args.claude_full_skill,
                    args.claude_setting_sources,
                    claude_variant,
                    args.claude_settings,
                )
                results.append(result)
                resume_keys.add(result_key(result))
                append_checkpoint(checkpoint, result)
                write_partial(partial_path, partial_metadata, results)
                print(
                    f"[{len(results)}] {case['id']} r{repetition} {result['variant']} "
                    f"process={result.get('process_status', result.get('status'))} "
                    f"semantic={result.get('semantic_status', 'not_recorded')}",
                    flush=True,
                )
                if result.get("status") in FAILED_STATUSES and not args.continue_on_error:
                    stopped_early = True
                    break
            if stopped_early:
                break
        if stopped_early:
            break
    ablation_status: str | None = None
    if ablation_target is not None:
        ablation_status = summarize_ablation(
            results,
            expected_ablations=len(cases) * args.repetitions,
            dry_run=args.dry_run,
        )
    arm_cycle = 3 if use_claude_arms or ablation_target is not None else 2
    claude_meta = claude_settings_metadata(args.claude_settings) if args.provider == "claude" else {}
    cli_version = None
    if not args.dry_run:
        try:
            version_result = subprocess.run(
                [args.provider, "--version"],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=20,
                check=False,
            )
            cli_version = redact_secrets((version_result.stdout or version_result.stderr or "").strip())
        except (OSError, subprocess.TimeoutExpired):
            cli_version = "unavailable"
    payload = {
        "schema_version": "1.5",
        "created_at": datetime.now(UTC).isoformat(),
        "provider": args.provider,
        "model": args.model,
        "cli_version": cli_version,
        "skill_revision": repository_revision(),
        "skill_revision_dirty": repository_revision_dirty(),
        "material_inputs_dirty": repository_material_inputs_dirty(),
        "claude_configured_model": claude_meta.get("configured_model"),
        "claude_proxy_host": claude_meta.get("proxy_host"),
        "dry_run": args.dry_run,
        "repetitions": args.repetitions,
        "activation": args.activation,
        "claude_full_skill": args.claude_full_skill,
        "claude_setting_sources": args.claude_setting_sources,
        "claude_effective_setting_sources": "project" if args.claude_settings is not None else args.claude_setting_sources,
        "claude_settings_isolated": args.claude_settings is not None,
        "variant_set": "claude_three_arm" if use_claude_arms else "claude_two_arm" if args.provider == "claude" else "codex_two_arm",
        "case_execution_modes": {case["id"]: case.get("execution_mode", "prompt_only") for case in cases},
        "case_ids": [case["id"] for case in cases],
        "case_relations": {
            case["id"]: case["relation"]
            for case in cases
            if "relation" in case
        },
        "variant_orders": variant_orders,
        "order_balance": (
            "complete"
            if args.repetitions % arm_cycle == 0
            else "partial"
        ),
        "stopped_early": stopped_early,
        "checkpoint": str(checkpoint),
        "partial": False,
        "results": results,
    }
    if ablation_target is not None:
        payload["ablation"] = {
            "reference": "core skill" if args.ablate_core else args.ablate_reference,
            "status": ablation_status,
            "method": "Removed from the isolated Codex skill copy; this is a whole-layer control." if args.ablate_core else "Removed from the isolated Codex skill copy; the core skill remains enabled.",
            "order_policy": "Latin-square rotation across baseline, full, and ablated variants",
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if partial_path.exists():
        partial_path.unlink()
    print(f"Wrote {len(payload['results'])} variants to {output}")
    return 2 if any(result.get("status") in FAILED_STATUSES for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
