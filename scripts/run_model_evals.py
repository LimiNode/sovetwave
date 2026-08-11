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


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "evals" / "behavioral" / "cases"
DEFAULT_RESULTS = ROOT / "evals" / "behavioral" / "results"
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]+|Bearer\s+[A-Za-z0-9._-]+|(?:api[_ -]?key|access[_ -]?token)\s*[=:]\s*\S+)", re.IGNORECASE)


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
            if case["id"] in seen:
                raise ValueError(f"duplicate behavioral case id: {case['id']}")
            seen.add(case["id"])
            cases.append(case)
    if not cases:
        raise ValueError(f"no behavioral cases in {case_dir}")
    return cases


def redact_secrets(text: str) -> str:
    return SECRET.sub("[redacted credential]", text)


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
        overrides.extend(["--config", f"model_providers.{provider}.{key}={toml_scalar(value)}"])
    return overrides


def make_workspace(root: Path, styled: bool) -> tempfile.TemporaryDirectory[str]:
    workspace = tempfile.TemporaryDirectory(prefix="sovetwave-eval-")
    if styled:
        destination = Path(workspace.name) / ".agents" / "skills" / "sovetwave"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root / "skills" / "sovetwave", destination)
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


def run_variant(
    provider: str,
    case: dict[str, Any],
    styled: bool,
    model: str | None,
    timeout: int,
    dry_run: bool,
    codex_overrides: list[str] | None = None,
) -> dict[str, Any]:
    with make_workspace(ROOT, styled) as temp_dir:
        workspace = Path(temp_dir)
        response_path = workspace / "last-message.txt"
        command = command_for(provider, workspace, case["prompt"], styled, model, response_path, codex_overrides)
        result: dict[str, Any] = {
            "case_id": case["id"],
            "variant": "sovetwave" if styled else "baseline",
            "prompt": case["prompt"],
            "assertions": case.get("assertions", []),
            "command": command,
        }
        if dry_run:
            result["status"] = "planned"
            return result
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
        response = response_path.read_text(encoding="utf-8") if response_path.exists() else (completed.stdout or "")
        result.update({
            "status": "completed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "response": response.strip(),
            "stderr": redact_secrets((completed.stderr or "").strip()),
        })
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("codex", "claude"), required=True)
    parser.add_argument("--model")
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASES)
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
    try:
        codex_overrides = (
            codex_provider_overrides(args.codex_provider_config)
            if args.codex_provider_config is not None
            else None
        )
    except ValueError as error:
        parser.error(str(error))

    cases = load_cases(args.case_dir)
    if args.limit is not None:
        cases = cases[:args.limit]
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or DEFAULT_RESULTS / f"{timestamp}-{args.provider}.json"
    results: list[dict[str, Any]] = []
    stopped_early = False
    for case in cases:
        for styled in (False, True):
            result = run_variant(
                args.provider,
                case,
                styled,
                args.model,
                args.timeout,
                args.dry_run,
                codex_overrides,
            )
            results.append(result)
            if result.get("status") == "failed" and not args.continue_on_error:
                stopped_early = True
                break
        if stopped_early:
            break
    payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "provider": args.provider,
        "model": args.model,
        "dry_run": args.dry_run,
        "stopped_early": stopped_early,
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['results'])} planned or completed variants to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
