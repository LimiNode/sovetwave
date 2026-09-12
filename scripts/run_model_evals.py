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


def load_cases(case_dir: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
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
            cases.append(case)
    if not cases:
        raise ValueError(f"no behavioral cases in {case_dir}")
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
) -> tempfile.TemporaryDirectory[str]:
    workspace = tempfile.TemporaryDirectory(prefix="sovetwave-eval-")
    if styled:
        destination = Path(workspace.name) / ".agents" / "skills" / "sovetwave"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root / "skills" / "sovetwave", destination)
        if ablated_reference is not None:
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
        return command + (["$sovetwave\n" + prompt] if styled else [prompt])
    if provider == "claude":
        command = ["claude", "--print", "--bare", "--tools", "", "--permission-mode", "plan"]
        if styled:
            command.extend(["--append-system-prompt-file", str(ROOT / "output-styles" / "sovetwave.md")])
        if model:
            command.extend(["--model", model])
        return command + [prompt]
    raise ValueError(f"unsupported provider: {provider}")


def variant_name(styled: bool, ablated_reference: str | None) -> str:
    if ablated_reference is not None:
        return "sovetwave_without_reference"
    return "sovetwave" if styled else "baseline"


def variant_plan(
    ablated_reference: str | None,
    repetition: int,
) -> list[tuple[bool, str | None]]:
    """Keep baseline first and balance full versus ablated order over repeats."""
    plan = [(False, None), (True, None)]
    if ablated_reference is None:
        return plan
    ablated = (True, ablated_reference)
    if repetition % 2 == 0:
        return [(False, None), ablated, (True, None)]
    return plan + [ablated]


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
) -> dict[str, Any]:
    if ablated_reference is not None and not styled:
        raise ValueError("a reference can be ablated only from a Sovetwave variant")
    with make_workspace(ROOT, styled, ablated_reference) as temp_dir:
        workspace = Path(temp_dir)
        response_path = workspace / "last-message.txt"
        command = command_for(provider, workspace, case["prompt"], styled, model, response_path, codex_overrides)
        result: dict[str, Any] = {
            "case_id": case["id"],
            "variant": variant_name(styled, ablated_reference),
            "repetition": repetition,
            "sequence": sequence,
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
    ablated = [result for result in results if result["variant"] == "sovetwave_without_reference"]
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
    parser.add_argument("--case-id", help="run exactly one behavioral case by id")
    parser.add_argument(
        "--ablate-reference",
        help="for Codex only, remove this conditional skill reference from the ablated variant (for example cpp-engineering.md)",
    )
    parser.add_argument("--repetitions", type=int, default=1, help="number of independent runs per case and variant")
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
    if args.ablate_reference is not None and args.provider != "codex":
        parser.error("--ablate-reference is currently supported only for provider codex")
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if args.ablate_reference is not None and args.repetitions < 2:
        parser.error("--ablate-reference requires at least 2 repetitions")
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
    if args.case_id is not None:
        if args.limit is not None:
            parser.error("--limit cannot be combined with explicit --case-id selection")
        cases = [case for case in cases if case["id"] == args.case_id]
        if not cases:
            parser.error(f"no behavioral case with id {args.case_id!r}")
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
                for styled, ablated_reference in variant_plan(args.ablate_reference, repetition)
            ],
        }
        for repetition in range(1, args.repetitions + 1)
    ]
    for case in cases:
        for repetition in range(1, args.repetitions + 1):
            for sequence, (styled, ablated_reference) in enumerate(
                variant_plan(args.ablate_reference, repetition),
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
    if args.ablate_reference is not None:
        ablation_status = summarize_ablation(
            results,
            expected_ablations=len(cases) * args.repetitions,
            dry_run=args.dry_run,
        )
    payload = {
        "schema_version": "1.2",
        "created_at": datetime.now(UTC).isoformat(),
        "provider": args.provider,
        "model": args.model,
        "dry_run": args.dry_run,
        "repetitions": args.repetitions,
        "case_ids": [case["id"] for case in cases],
        "variant_orders": variant_orders,
        "stopped_early": stopped_early,
        "results": results,
    }
    if args.ablate_reference is not None:
        payload["ablation"] = {
            "reference": args.ablate_reference,
            "status": ablation_status,
            "method": "Removed from the isolated Codex skill copy; the core skill remains enabled.",
            "order_policy": "baseline first; full and ablated Sovetwave alternate by repetition",
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['results'])} variants to {output}")
    return 2 if any(result.get("status") in FAILED_STATUSES for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
