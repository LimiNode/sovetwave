#!/usr/bin/env python3
"""Execute or dry-run the fixed-tag voice-card ablation pilot.

Execution is opt-in: without ``--execute`` this command only materializes a
plan.  The A arm asks the agent to invoke the selector inside its measured
Codex session; its host-side selector result is retained only as a validation
oracle and is never injected into A's context.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evals" / "experiments" / "voice-card-selector-ablation.json"
PLANNER_PATH = ROOT / "scripts" / "plan_voice_card_ablation.py"
MATERIALIZER_PATH = ROOT / "scripts" / "materialize_voice_card_arms.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner = load_module("voice_ablation_planner", PLANNER_PATH)
materializer = load_module("voice_ablation_materializer", MATERIALIZER_PATH)


def _selector_items(stream: str) -> list[dict[str, Any]]:
    """Return unique command_execution items which invoke the selector."""
    seen: set[str] = set()
    indexed: dict[str, int] = {}
    anonymous: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for line in (stream or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if not isinstance(item, dict):
            continue
        if item.get("type") != "command_execution":
            continue
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            if item_id not in seen:
                seen.add(item_id)
                indexed[item_id] = len(items)
                items.append(item)
            else:
                items[indexed[item_id]] = {**items[indexed[item_id]], **item}
        else:
            anonymous.append(item)
    return [item for item in items + anonymous if "select_voice_cards.py" in _command_text(item).replace("\\", "/")]


def selector_invocations(stream: str) -> int:
    """Count unique selector command items in a Codex JSON event stream."""
    return len(_selector_items(stream))


def _command_text(item: dict[str, Any]) -> str:
    fields = [item.get(key) for key in ("command", "cmd", "input", "arguments")]
    return " ".join(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False) for value in fields if value is not None)


def _selector_output(item: dict[str, Any]) -> Any | None:
    """Extract selector stdout when the provider exposes it on the item."""
    for key in ("aggregated_output", "output", "stdout", "result"):
        value = item.get(key)
        if isinstance(value, (list, dict)):
            return _normalize_selector_payload(value)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            try:
                parsed = json.loads(text)
                return _normalize_selector_payload(parsed)
            except json.JSONDecodeError:
                start, end = text.find("["), text.rfind("]")
                if start >= 0 and end > start:
                    try:
                        return _normalize_selector_payload(json.loads(text[start:end + 1]))
                    except json.JSONDecodeError:
                        return {"_unparseable": True}
    return None


def _normalize_selector_payload(value: Any) -> Any:
    if not isinstance(value, list) or not all(isinstance(card, dict) for card in value):
        return value
    return [{key: card.get(key) for key in ("id", "use", "anchor")} for card in value]


def _resolved_model_value(results: list[dict[str, Any]]) -> str | None:
    resolved = sorted({r.get("resolved_model") for r in results if isinstance(r.get("resolved_model"), str) and r.get("resolved_model")})
    return resolved[0] if len(resolved) == 1 else ("ambiguous" if resolved else None)


def _resolved_model_from_stream(stream: str) -> str | None:
    for line in (stream or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        for candidate in (event.get("model"), event.get("resolved_model"), event.get("resolvedModel")):
            if isinstance(candidate, str) and candidate:
                return candidate
        thread = event.get("thread")
        if isinstance(thread, dict) and isinstance(thread.get("model"), str):
            return thread["model"]
    return None


def validate_selector_trace(
    stream: str,
    *,
    expected: int,
    fixed_tags: dict[str, str] | None,
    oracle_payload: list[dict[str, str]] | None,
) -> dict[str, Any]:
    """Validate the preregistered selector treatment in a Codex event stream."""
    items = _selector_items(stream)
    traces: list[dict[str, Any]] = []
    for item in items:
        command = _command_text(item).replace("\\", "/")
        try:
            item_tokens = [token.strip("'\"") for token in shlex.split(command, posix=False)]
        except ValueError:
            item_tokens = command.split()
        if "--list-tags" in item_tokens:
            kind = "list_tags"
        elif all(flag in item_tokens for flag in ("--scene", "--domain", "--max", "--json")):
            kind = "fixed_select"
        else:
            kind = "other_selector"
        payload = _selector_output(item)
        payload_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest() if payload is not None else None
        traces.append({
            "item_id": item.get("id"),
            "kind": kind,
            "normalized_command": command,
            "scene": item_tokens[item_tokens.index("--scene") + 1] if "--scene" in item_tokens and item_tokens.index("--scene") + 1 < len(item_tokens) else None,
            "domain": item_tokens[item_tokens.index("--domain") + 1] if "--domain" in item_tokens and item_tokens.index("--domain") + 1 < len(item_tokens) else None,
            "max": item_tokens[item_tokens.index("--max") + 1] if "--max" in item_tokens and item_tokens.index("--max") + 1 < len(item_tokens) else None,
            "json": "--json" in item_tokens,
            "list_tags": "--list-tags" in item_tokens,
            "exit_code": item.get("exit_code", item.get("exitCode")),
            "output_status": "observed" if payload is not None else "not_available",
            "payload_sha256": payload_hash,
            "oracle_match": payload == oracle_payload if payload is not None and expected else None,
        })
    result: dict[str, Any] = {
        "recorded_selector_invocations": len(items),
        "selector_trace": traces,
        "selector_invocation_match": False,
        "selector_trace_status": "not_expected" if expected == 0 else "invalid",
        "selector_output_status": "not_available",
        "selector_oracle_equivalence": "not_applicable" if expected == 0 else "exact_command_pinned_revision",
    }
    if expected == 0:
        result["selector_invocation_match"] = len(items) == 0
        result["selector_trace_status"] = "valid" if not items else "unexpected_invocation"
        return result
    if len(items) != 1 or not fixed_tags:
        result["selector_trace_status"] = "wrong_invocation_count" if len(items) != 1 else "missing_fixed_tags"
        return result
    text = _command_text(items[0]).replace("\\", "/")
    try:
        tokens = [token.strip("'\"") for token in shlex.split(text, posix=False)]
    except ValueError:
        tokens = text.split()
    try:
        scene = tokens[tokens.index("--scene") + 1]
        domain = tokens[tokens.index("--domain") + 1]
        maximum = tokens[tokens.index("--max") + 1]
    except (ValueError, IndexError):
        result["selector_trace_status"] = "missing_required_args"
        return result
    if (
        tokens.count("--scene") != 1
        or tokens.count("--domain") != 1
        or tokens.count("--max") != 1
        or scene != fixed_tags.get("scene")
        or domain != fixed_tags.get("domain")
        or maximum != "2"
        or "--json" not in tokens
        or "--list-tags" in tokens
        or len(tokens) != 9
        or tokens[0].replace("\\", "/").rsplit("/", 1)[-1].lower() not in {"python", "python.exe", "python3", "python3.exe", "py", "py.exe"}
        or tokens[1].replace("\\", "/").rsplit("/", 1)[-1].lower() != "select_voice_cards.py"
    ):
        result["selector_trace_status"] = "wrong_selector_args"
        return result
    result["selector_invocation_match"] = True
    result["selector_trace_status"] = "valid"
    observed = _selector_output(items[0])
    if observed is not None:
        result["selector_output_status"] = "observed"
        if observed == oracle_payload:
            result["selector_oracle_equivalence"] = "matched"
        else:
            result["selector_invocation_match"] = False
            result["selector_trace_status"] = "oracle_payload_mismatch"
    return result


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def invocation_plan() -> list[dict[str, Any]]:
    manifest = load_manifest()
    mapping = planner.validate_static_map()
    planner.validate_manifest(manifest, mapping)
    rows = planner.interleaved_plan(manifest)
    cases = {case["id"]: case for case in manifest["cases"]}
    planned: list[dict[str, Any]] = []
    for row in rows:
        envelope = materializer.materialize(row["case_id"], row["arm"])
        case = cases[row["case_id"]]
        planned.append({
            **row,
            "fixed_tags": envelope["fixed_tags"],
            "selector_eligible": case["selector_eligible"],
            "tag_inference_measured": envelope["tag_inference_measured"],
            "list_tags_discovery_measured": envelope["list_tags_discovery_measured"],
            "card_payload_supplied": bool(envelope["card_payload"]),
            "validation_oracle_payload": envelope["validation_oracle_payload"],
            "expected_selector_invocations": 1 if row.get("selector_eligible") and row["arm"] == "A" else 0,
        })
    return planned


def append_treatment(skill_path: Path, envelope: dict[str, Any]) -> None:
    """Replace the production selector policy with one arm-specific contract."""
    original = skill_path.read_text(encoding="utf-8")
    start_marker = "For a substantial, low-risk, non-public standard or lecture response, inspect\n"
    end_marker = "[voice-cards.json](references/voice-cards.json)."
    if original.count(start_marker) != 1:
        raise ValueError("expected exactly one production voice-card selector policy")
    start = original.index(start_marker)
    end = original.index(end_marker, start) + len(end_marker)
    scene_domain = envelope["fixed_tags"]
    if scene_domain is None:
        # Negative controls deliberately have no tags or card payload in any
        # arm. Keep this branch before the A/B formatting paths: controls are
        # interleaved with positive cases and must never dereference tags.
        block = "Voice-card selection is inapplicable for this control. Do not inspect tags or load card data."
    elif envelope["arm"] == "A":
        block = (
            "For this measured observation use the authoritative tags "
            f"scene={scene_domain['scene']!r}, domain={scene_domain['domain']!r}. "
            "Do not run --list-tags or infer replacement tags. Invoke exactly this command once and use its returned ordered id/use/anchor payload: "
            f"python .agents/skills/sovetwave/scripts/select_voice_cards.py --scene {scene_domain['scene']} --domain {scene_domain['domain']} --max 2 --json. "
            "This selector invocation is part of the measured turn."
        )
    elif envelope["arm"] == "B":
        payload = json.dumps(envelope["card_payload"], ensure_ascii=False, indent=2)
        block = (
            f"The authoritative tags are scene={scene_domain['scene']!r}, domain={scene_domain['domain']!r}. "
            "Do not run --list-tags or select_voice_cards.py. Use this exact ordered id/use/anchor payload as the voice-card context:\n\n"
            f"```json\n{payload}\n```"
        )
    else:
        block = (
            f"The experiment metadata tags are scene={scene_domain['scene']!r}, domain={scene_domain['domain']!r}. "
            "Voice cards are disabled for this observation. Do not run --list-tags, select_voice_cards.py, or load card data."
        )
    skill_path.write_text(original[:start] + block + "\n\n" + original[end:], encoding="utf-8")


def metadata(manifest: dict[str, Any], model: str, provider_overrides_sha256: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "experiment_id": manifest["experiment_id"],
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "model": model,
        "requested_model": model,
        "resolved_model": None,
        "provider_overrides_sha256": provider_overrides_sha256,
        "case_ids": manifest["pilot"]["case_ids"],
        "repetitions": manifest["pilot"]["repetitions"],
        "provenance": planner.git_provenance(),
    }


def _metadata_identity(metadata_payload: dict[str, Any]) -> dict[str, Any]:
    """Return resume invariants, excluding resolved model observed at runtime."""
    return {key: value for key, value in metadata_payload.items() if key != "resolved_model"}


def _write_checkpoint_metadata(path: Path, meta: dict[str, Any], results: list[dict[str, Any]]) -> None:
    payload = dict(meta)
    payload["resolved_model"] = _resolved_model_value(results)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def execute_one(runner: Any, row: dict[str, Any], model: str, timeout: int, overrides: list[str], provider_overrides_sha256: str | None = None) -> dict[str, Any]:
    envelope = materializer.materialize(row["case_id"], row["arm"])
    cases = planner.behavioral_cases()
    case = cases[row["case_id"]]
    started = time.monotonic()
    with runner.make_workspace(ROOT, True, None, False, None) as temporary:
        workspace = Path(temporary)
        skill_copy = workspace / ".agents" / "skills" / "sovetwave" / "SKILL.md"
        append_treatment(skill_copy, envelope)
        effective_skill_sha256 = hashlib.sha256(skill_copy.read_bytes()).hexdigest()
        response_path = workspace / "last-message.txt"
        command = runner.command_for("codex", workspace, case["prompt"], True, model, response_path, overrides)
        base = {
            "case_id": row["case_id"],
            "variant": f"voice_card_{row['arm']}",
            "arm": row["arm"],
            "repetition": row["repetition"],
            "sequence": row["sequence"],
            "prompt": case["prompt"],
            "fixed_tags": envelope["fixed_tags"],
            "card_payload_supplied": bool(envelope["card_payload"]),
            "validation_oracle_payload": envelope["validation_oracle_payload"],
            "expected_selector_invocations": 1 if row.get("selector_eligible") and row["arm"] == "A" else 0,
            "requested_model": model,
            "provider_overrides_sha256": provider_overrides_sha256,
            "effective_skill_sha256": effective_skill_sha256,
        }
        expected = base["expected_selector_invocations"]
        try:
            completed = runner.execute_command("codex", command, cwd=workspace, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            return {**base, "status": "timeout", "process_status": "timeout", "treatment_status": "not_observed", "causal_eligible": False,
                    "first_attempt_completion": False, "returncode": None, "response": "", "stderr": str(error),
                    "selector_invocation_match": None, "recorded_selector_invocations": 0,
                    "elapsed_seconds": round(time.monotonic() - started, 3)}
        except OSError as error:
            return {**base, "status": "failed", "process_status": "failed", "treatment_status": "not_observed", "causal_eligible": False,
                    "first_attempt_completion": False, "returncode": None, "response": "", "stderr": str(error),
                    "selector_invocation_match": None, "recorded_selector_invocations": 0,
                    "elapsed_seconds": round(time.monotonic() - started, 3)}
        response = response_path.read_text(encoding="utf-8") if response_path.exists() else ""
        telemetry = runner.parse_codex_json_stream(completed.stdout or "")
        trace = validate_selector_trace(completed.stdout or "", expected=expected,
                                        fixed_tags=envelope["fixed_tags"], oracle_payload=envelope["validation_oracle_payload"])
        process_status = "completed" if completed.returncode == 0 and response.strip() else "failed"
        treatment_status = "valid" if trace["selector_invocation_match"] else "invalid"
        status = process_status if treatment_status == "valid" else "invalid_treatment"
        return {**base, **trace,
            "treatment_status": treatment_status, "causal_eligible": treatment_status == "valid", "codex_tool_calls": telemetry["tool_calls"],
            "codex_usage": telemetry["usage"], "codex_usage_status": telemetry["usage_status"],
            "status": status, "process_status": process_status,
            "first_attempt_completion": process_status == "completed", "returncode": completed.returncode,
            "response": response.strip(), "resolved_model": runner.resolved_model_from_stderr(completed.stderr or "") or _resolved_model_from_stream(completed.stdout or ""),
            "elapsed_seconds": round(time.monotonic() - started, 3)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--codex-provider-config", type=Path)
    parser.add_argument("--execute", action="store_true", help="perform model calls; omit for design-only dry-run")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--continue-on-invalid", action="store_true", help="record treatment violations and continue (not recommended)")
    args = parser.parse_args()
    manifest = load_manifest()
    rows = invocation_plan()
    if not args.execute:
        meta = metadata(manifest, args.model, None)
        payload = {**meta, "status": "planned_no_model_runs", "observations": rows}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {len(rows)} planned observations to {args.output}")
        return 0
    if args.codex_provider_config is None:
        parser.error("--codex-provider-config is required with --execute")
    runner = load_module("voice_ablation_runner", ROOT / "scripts" / "run_model_evals.py")
    overrides = runner.codex_provider_overrides(args.codex_provider_config)
    provider_overrides_sha256 = hashlib.sha256(
        json.dumps(runner.redact_command(overrides), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    meta = metadata(manifest, args.model, provider_overrides_sha256)
    checkpoint = args.output.with_suffix(".jsonl")
    checkpoint_meta = checkpoint.with_suffix(".meta.json")
    if args.resume:
        stored_meta = json.loads(checkpoint_meta.read_text(encoding="utf-8")) if checkpoint_meta.exists() else {}
        if not checkpoint.exists() or not checkpoint_meta.exists() or _metadata_identity(stored_meta) != _metadata_identity(meta):
            parser.error("--resume requires a matching checkpoint provenance")
        results = runner.load_checkpoint(checkpoint)
        if any(result.get("treatment_status") == "invalid" for result in results) and not args.continue_on_invalid:
            parser.error("checkpoint contains an invalid treatment; pass --continue-on-invalid to override the stop")
    elif checkpoint.exists() or checkpoint_meta.exists():
        parser.error("checkpoint exists; use --resume or choose another output")
    else:
        results = []
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        _write_checkpoint_metadata(checkpoint_meta, meta, results)
    seen = {(r.get("case_id"), r.get("repetition"), r.get("sequence"), r.get("arm")) for r in results}
    lock = runner.acquire_checkpoint_lock(checkpoint)
    stopped_invalid = False
    try:
        for row in rows:
            key = (row["case_id"], row["repetition"], row["sequence"], row["arm"])
            if key in seen:
                continue
            result = execute_one(runner, row, args.model, args.timeout, overrides, provider_overrides_sha256)
            runner.append_checkpoint(checkpoint, result)
            results.append(result)
            _write_checkpoint_metadata(checkpoint_meta, meta, results)
            seen.add(key)
            print(f"[{len(results)}] {row['case_id']} r{row['repetition']} {row['arm']} process={result['process_status']} treatment={result.get('treatment_status')}", flush=True)
            if result.get("treatment_status") == "invalid" and not args.continue_on_invalid:
                stopped_invalid = True
                break
    finally:
        runner.release_checkpoint_lock(lock)
    payload = {**meta, "resolved_model": _resolved_model_value(results),
               "status": "stopped_invalid_treatment" if 'stopped_invalid' in locals() and stopped_invalid else "completed", "observations": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(results)} observations to {args.output}")
    return 2 if any(r.get("status") in {"timeout", "failed", "invalid_treatment"} for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
