#!/usr/bin/env python3
"""Run paired baseline/Sovetwave behavioral evaluations through a local agent CLI."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "evals" / "behavioral" / "cases"
DEFAULT_RESULTS = ROOT / "evals" / "behavioral" / "results"
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]+|Bearer\s+[A-Za-z0-9._-]+|(?:api[_ -]?key|access[_ -]?token)\s*[=:]\s*\S+)", re.IGNORECASE)
URL_CREDENTIAL = re.compile(r"(https?://)([^/@\s]+@)", re.IGNORECASE)
SAFE_PROVIDER_KEYS = frozenset({"name", "base_url", "wire_api", "requires_openai_auth", "env_key"})
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
})
CASE_RELATION_KINDS = frozenset({"contrast", "directional", "invariance"})
CORE_ABLATION = "__core__"


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
        for case in suite["cases"]:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not isinstance(case.get("prompt"), str):
                raise ValueError(f"{path}: every case needs string id and prompt")
            if not isinstance(case.get("assertions"), list) or not all(
                isinstance(assertion, str) and assertion.strip() for assertion in case["assertions"]
            ):
                raise ValueError(f"{path}: every case needs non-empty string assertions")
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
) -> tempfile.TemporaryDirectory[str]:
    workspace = tempfile.TemporaryDirectory(prefix="sovetwave-eval-")
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
) -> list[str]:
    if provider == "codex":
        command = [
            "codex", "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
            "--sandbox", "read-only", "-C", str(workspace),
            "--output-last-message", str(output_path),
        ]
        if codex_overrides:
            command.extend(codex_overrides)
        if model:
            command.extend(["--model", model])
        marker_allowed = styled and activation == "explicit" and (workspace / ".agents" / "skills" / "sovetwave" / "SKILL.md").is_file()
        return command + (["$sovetwave\n" + prompt] if marker_allowed else [prompt])
    if provider == "claude":
        # A full-skill run must let Claude discover and invoke the installed
        # skill. Baseline receives the same tool surface so the comparison
        # isolates the skill files rather than a tooling privilege.
        tool_set = "Skill,Read,Bash" if claude_full_skill else ""
        # Keep the prompt immediately after --print. Claude's variadic
        # --allowedTools and --add-dir options otherwise consume a trailing
        # positional prompt as another list item.
        command = ["claude", "--print", prompt]
        if claude_full_skill:
            command.extend([
                "--tools", tool_set,
                "--allowedTools", tool_set,
                "--setting-sources", claude_setting_sources,
                "--permission-mode", "plan",
            ])
        else:
            command.extend(["--bare", "--tools", tool_set, "--permission-mode", "plan"])
        if styled:
            command.extend(["--append-system-prompt-file", str(ROOT / "output-styles" / "sovetwave.md")])
        if claude_full_skill:
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
) -> dict[str, Any]:
    if ablated_reference is not None and not styled:
        raise ValueError("a reference can be ablated only from a Sovetwave variant")
    with make_workspace(ROOT, styled, ablated_reference, claude_full_skill) as temp_dir:
        workspace = Path(temp_dir)
        response_path = workspace / "last-message.txt"
        command = command_for(
            provider, workspace, case["prompt"], styled, model, response_path,
            codex_overrides, activation, claude_full_skill, claude_setting_sources,
        )
        result: dict[str, Any] = {
            "case_id": case["id"],
            "variant": variant_name(styled, ablated_reference),
            "repetition": repetition,
            "sequence": sequence,
            "activation": activation,
            "prompt": redact_secrets(case["prompt"]),
            "assertions": case.get("assertions", []),
            "command": redact_command(command),
        }
        if ablated_reference is not None:
            result["ablated_reference"] = ablated_reference
        if dry_run:
            result["status"] = "planned"
            return result
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            result.update({
                "status": "timeout",
                "returncode": None,
                "response": "",
                "stderr": redact_secrets(str(error)),
            })
            return result
        except OSError as error:
            result.update({
                "status": "failed",
                "returncode": None,
                "response": "",
                "stderr": redact_secrets(str(error)),
            })
            return result
        response = response_path.read_text(encoding="utf-8") if response_path.exists() else (completed.stdout or "")
        response = response.strip()
        if completed.returncode != 0:
            status = "failed"
        elif not response:
            status = "invalid_empty_response"
        else:
            status = "completed"
        result.update({
            "status": status,
            "returncode": completed.returncode,
            "response": response,
            "stderr": redact_secrets((completed.stderr or "").strip()),
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
        help="for Claude, expose the complete Sovetwave skill from the temporary project in addition to its output style",
    )
    parser.add_argument(
        "--claude-setting-sources",
        default="project",
        help="comma-separated Claude setting sources for full-skill runs (default: project; use user,project for proxy settings stored in ~/.claude)",
    )
    parser.add_argument("--repetitions", type=int, default=1, help="number of independent runs per case and variant")
    parser.add_argument(
        "--activation",
        choices=("explicit", "natural"),
        default="explicit",
        help="Codex activation condition: inject $sovetwave explicitly or leave activation to the prompt",
    )
    parser.add_argument("--output", type=Path)
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
    results: list[dict[str, Any]] = []
    stopped_early = False
    variant_orders = [
        {
            "repetition": repetition,
            "variants": [
                variant_name(styled, ablated_reference)
                for styled, ablated_reference in variant_plan(ablation_target, repetition)
            ],
        }
        for repetition in range(1, args.repetitions + 1)
    ]
    for case in cases:
        for repetition in range(1, args.repetitions + 1):
            for sequence, (styled, ablated_reference) in enumerate(
                variant_plan(ablation_target, repetition),
                start=1,
            ):
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
                )
                results.append(result)
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
    payload = {
        "schema_version": "1.3",
        "created_at": datetime.now(UTC).isoformat(),
        "provider": args.provider,
        "model": args.model,
        "dry_run": args.dry_run,
        "repetitions": args.repetitions,
        "activation": args.activation,
        "claude_full_skill": args.claude_full_skill,
        "claude_setting_sources": args.claude_setting_sources,
        "case_ids": [case["id"] for case in cases],
        "case_relations": {
            case["id"]: case["relation"]
            for case in cases
            if "relation" in case
        },
        "variant_orders": variant_orders,
        "order_balance": (
            "complete"
            if args.repetitions % (3 if ablation_target is not None else 2) == 0
            else "partial"
        ),
        "stopped_early": stopped_early,
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
    print(f"Wrote {len(payload['results'])} variants to {output}")
    return 2 if any(result.get("status") in FAILED_STATUSES for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
