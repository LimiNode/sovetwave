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


def selector_invocations(stream: str) -> int:
    """Count unique selector command items in a Codex JSON event stream."""
    seen: set[str] = set()
    anonymous = 0
    for line in (stream or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if not isinstance(item, dict):
            continue
        fields = [item.get(key) for key in ("command", "cmd", "input", "arguments")]
        text = " ".join(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False) for value in fields if value is not None)
        if "select_voice_cards.py" not in text.replace("\\", "/"):
            continue
        item_id = item.get("id")
        if isinstance(item_id, str) and item_id:
            seen.add(item_id)
        else:
            anonymous += 1
    return len(seen) + anonymous


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
            "tag_inference_measured": envelope["tag_inference_measured"],
            "list_tags_discovery_measured": envelope["list_tags_discovery_measured"],
            "card_payload_supplied": bool(envelope["card_payload"]),
            "validation_oracle_payload": envelope["validation_oracle_payload"],
            "expected_selector_invocations": 1 if case["selector_eligible"] and row["arm"] == "A" else 0,
        })
    return planned


def append_treatment(skill_path: Path, envelope: dict[str, Any]) -> None:
    """Add an arm-specific host instruction without changing the user prompt."""
    scene_domain = envelope["fixed_tags"]
    if envelope["arm"] == "A":
        block = (
            "\n\n## Fixed-tag ablation treatment\n"
            f"For this measured observation use the authoritative tags scene={scene_domain['scene']!r}, domain={scene_domain['domain']!r}. "
            "Do not run --list-tags or infer replacement tags. Invoke the bundled select_voice_cards.py selector exactly once "
            "with these tags and use its returned ordered id/use/anchor payload. This selector invocation is part of the measured turn."
        )
    elif envelope["arm"] == "B":
        payload = json.dumps(envelope["card_payload"], ensure_ascii=False, indent=2)
        block = (
            "\n\n## Fixed-tag ablation treatment\n"
            f"The authoritative tags are scene={scene_domain['scene']!r}, domain={scene_domain['domain']!r}. "
            "Do not run --list-tags or select_voice_cards.py. Use this exact ordered id/use/anchor payload as the voice-card context:\n\n"
            f"```json\n{payload}\n```"
        )
    else:
        block = (
            "\n\n## Fixed-tag ablation treatment\n"
            f"The experiment metadata tags are scene={scene_domain['scene']!r}, domain={scene_domain['domain']!r}. "
            "Voice cards are disabled for this observation. Do not run --list-tags, select_voice_cards.py, or load card data."
        ) if scene_domain else "\n\n## Fixed-tag ablation treatment\nVoice-card selection is inapplicable for this control. Do not inspect tags or load card data."
    skill_path.write_text(skill_path.read_text(encoding="utf-8") + block + "\n", encoding="utf-8")


def metadata(manifest: dict[str, Any], model: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "experiment_id": manifest["experiment_id"],
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "model": model,
        "case_ids": manifest["pilot"]["case_ids"],
        "repetitions": manifest["pilot"]["repetitions"],
        "provenance": planner.git_provenance(),
    }


def execute_one(runner: Any, row: dict[str, Any], model: str, timeout: int, overrides: list[str]) -> dict[str, Any]:
    envelope = materializer.materialize(row["case_id"], row["arm"])
    cases = planner.behavioral_cases()
    case = cases[row["case_id"]]
    started = time.monotonic()
    with runner.make_workspace(ROOT, True, None, False, None) as temporary:
        workspace = Path(temporary)
        append_treatment(workspace / ".agents" / "skills" / "sovetwave" / "SKILL.md", envelope)
        response_path = workspace / "last-message.txt"
        command = runner.command_for("codex", workspace, case["prompt"], True, model, response_path, overrides)
        completed = runner.execute_command("codex", command, cwd=workspace, timeout=timeout)
        response = response_path.read_text(encoding="utf-8") if response_path.exists() else ""
        telemetry = runner.parse_codex_json_stream(completed.stdout or "")
        recorded = selector_invocations(completed.stdout or "")
        status = "completed" if completed.returncode == 0 and response.strip() else "failed"
        return {
            "case_id": row["case_id"],
            "variant": f"voice_card_{row['arm']}",
            "arm": row["arm"],
            "repetition": row["repetition"],
            "sequence": row["sequence"],
            "prompt": case["prompt"],
            "fixed_tags": envelope["fixed_tags"],
            "card_payload_supplied": bool(envelope["card_payload"]),
            "validation_oracle_payload": envelope["validation_oracle_payload"],
            "expected_selector_invocations": 1 if case["selector_eligible"] and row["arm"] == "A" else 0,
            "recorded_selector_invocations": recorded,
            "selector_invocation_match": recorded == (1 if case["selector_eligible"] and row["arm"] == "A" else 0),
            "codex_tool_calls": telemetry["tool_calls"],
            "codex_usage": telemetry["usage"],
            "codex_usage_status": telemetry["usage_status"],
            "status": status,
            "process_status": status,
            "returncode": completed.returncode,
            "response": response.strip(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--codex-provider-config", type=Path)
    parser.add_argument("--execute", action="store_true", help="perform model calls; omit for design-only dry-run")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    manifest = load_manifest()
    rows = invocation_plan()
    meta = metadata(manifest, args.model)
    if not args.execute:
        payload = {**meta, "status": "planned_no_model_runs", "observations": rows}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {len(rows)} planned observations to {args.output}")
        return 0
    if args.codex_provider_config is None:
        parser.error("--codex-provider-config is required with --execute")
    runner = load_module("voice_ablation_runner", ROOT / "scripts" / "run_model_evals.py")
    overrides = runner.codex_provider_overrides(args.codex_provider_config)
    checkpoint = args.output.with_suffix(".jsonl")
    checkpoint_meta = checkpoint.with_suffix(".meta.json")
    if args.resume:
        if not checkpoint.exists() or not checkpoint_meta.exists() or json.loads(checkpoint_meta.read_text(encoding="utf-8")) != meta:
            parser.error("--resume requires a matching checkpoint provenance")
        results = runner.load_checkpoint(checkpoint)
    elif checkpoint.exists() or checkpoint_meta.exists():
        parser.error("checkpoint exists; use --resume or choose another output")
    else:
        results = []
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    seen = {(r.get("case_id"), r.get("repetition"), r.get("sequence"), r.get("arm")) for r in results}
    lock = runner.acquire_checkpoint_lock(checkpoint)
    try:
        for row in rows:
            key = (row["case_id"], row["repetition"], row["sequence"], row["arm"])
            if key in seen:
                continue
            result = execute_one(runner, row, args.model, args.timeout, overrides)
            runner.append_checkpoint(checkpoint, result)
            results.append(result)
            seen.add(key)
            print(f"[{len(results)}] {row['case_id']} r{row['repetition']} {row['arm']} process={result['process_status']}", flush=True)
    finally:
        runner.release_checkpoint_lock(lock)
    payload = {**meta, "status": "completed", "observations": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(results)} observations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
