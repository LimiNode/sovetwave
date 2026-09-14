#!/usr/bin/env python3
"""Run the three-arm live selector trace preflight outside the pilot dataset."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "voice-card-selector-teaching-explanation"
PROMPT = "Объясни на одном коротком примере, почему измерение должно иметь явно заданную проверяемую границу. Файлы не изменяй."


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load_module("preflight_runtime", ROOT / "scripts" / "run_model_evals.py")
ablation = load_module("preflight_ablation", ROOT / "scripts" / "run_voice_card_ablation.py")
materializer = load_module("preflight_materializer", ROOT / "scripts" / "materialize_voice_card_arms.py")


def resolved_model(stdout: str, stderr: str) -> str | None:
    value = runtime.resolved_model_from_stderr(stderr)
    if value:
        return value
    for line in (stdout or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            for key in ("model", "resolved_model", "resolvedModel"):
                if isinstance(event.get(key), str) and event[key]:
                    return event[key]
    return None


def run_arm(arm: str, model: str, timeout: int, overrides: list[str], provider_hash: str) -> dict[str, Any]:
    envelope = materializer.materialize(CASE_ID, arm)
    started = time.monotonic()
    with runtime.make_workspace(ROOT, True, None, False, None) as temporary:
        workspace = Path(temporary)
        skill_copy = workspace / ".agents" / "skills" / "sovetwave" / "SKILL.md"
        ablation.append_treatment(skill_copy, envelope)
        effective_skill_sha256 = hashlib.sha256(skill_copy.read_bytes()).hexdigest()
        response_path = workspace / "last-message.txt"
        command = runtime.command_for("codex", workspace, PROMPT, True, model, response_path, overrides)
        expected = 1 if arm == "A" else 0
        try:
            completed = runtime.execute_command("codex", command, cwd=workspace, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            return {"arm": arm, "status": "timeout", "process_status": "timeout", "treatment_status": "not_observed",
                    "causal_eligible": False, "first_attempt_completion": False, "returncode": None,
                    "stderr": runtime.redact_secrets(str(error)), "elapsed_seconds": round(time.monotonic() - started, 3)}
        except OSError as error:
            return {"arm": arm, "status": "failed", "process_status": "failed", "treatment_status": "not_observed",
                    "causal_eligible": False, "first_attempt_completion": False, "returncode": None,
                    "stderr": runtime.redact_secrets(str(error)), "elapsed_seconds": round(time.monotonic() - started, 3)}
        response = response_path.read_text(encoding="utf-8") if response_path.exists() else ""
        telemetry = runtime.parse_codex_json_stream(completed.stdout or "")
        trace = ablation.validate_selector_trace(
            completed.stdout or "", expected=expected,
            fixed_tags=envelope["fixed_tags"], oracle_payload=envelope["validation_oracle_payload"],
        )
        process_status = "completed" if completed.returncode == 0 and response.strip() else "failed"
        treatment_status = "valid" if trace["selector_invocation_match"] else "invalid"
        return {
            "case_id": CASE_ID, "arm": arm, "prompt": PROMPT,
            "fixed_tags": envelope["fixed_tags"], "expected_selector_invocations": expected,
            "validation_oracle_payload": envelope["validation_oracle_payload"],
            "effective_skill_sha256": effective_skill_sha256,
            "requested_model": model, "resolved_model": resolved(completed.stdout or "", completed.stderr or ""),
            "provider_overrides_sha256": provider_hash, **trace,
            "codex_tool_calls": telemetry["tool_calls"], "codex_usage": telemetry["usage"],
            "codex_usage_status": telemetry["usage_status"], "status": process_status if treatment_status == "valid" else "invalid_treatment",
            "process_status": process_status, "treatment_status": treatment_status,
            "causal_eligible": treatment_status == "valid", "first_attempt_completion": process_status == "completed",
            "returncode": completed.returncode, "response": response.strip(),
            "stderr": runtime.redact_secrets(completed.stderr or ""),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--codex-provider-config", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        payload = {"protocol_revision": 2, "status": "planned_no_model_runs", "case_id": CASE_ID, "arms": ["A", "B", "C"]}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    if args.codex_provider_config is None:
        parser.error("--codex-provider-config is required with --execute")
    overrides = runtime.codex_provider_overrides(args.codex_provider_config)
    provider_hash = hashlib.sha256(json.dumps(runtime.redact_command(overrides), ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    observations = [run_arm(arm, args.model, args.timeout, overrides, provider_hash) for arm in ("A", "B", "C")]
    payload = {
        "protocol_revision": 2, "status": "completed" if all(row.get("treatment_status") == "valid" for row in observations) else "failed_preflight",
        "case_id": CASE_ID, "requested_model": args.model, "provider_overrides_sha256": provider_hash,
        "provenance": ablation.planner.git_provenance(), "observations": observations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(observations)} preflight observations to {args.output}")
    return 0 if payload["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
