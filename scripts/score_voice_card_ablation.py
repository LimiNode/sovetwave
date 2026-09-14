#!/usr/bin/env python3
"""Build a deterministic, non-semantic scoring packet for the A/B/C pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "evals" / "experiments" / "voice-card-selector-ablation.json"
CASES_DIR = ROOT / "evals" / "behavioral" / "cases"
RUBRIC_PATH = ROOT / "evals" / "behavioral" / "rubric.json"
ARMS = ("A", "B", "C")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON fixture {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON fixture must contain an object: {path}")
    return value


def load_canonical_cases(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Load prompts/assertions/axes from the behavioral case registry.

    The experiment manifest owns treatment metadata (group and selector eligibility),
    while behavioral case files are the canonical source for grading content.
    """
    cases: dict[str, dict[str, Any]] = {}
    for path in sorted(CASES_DIR.glob("*.json")):
        document = read_json(path)
        suite_axes = document.get("applicable_axes")
        if suite_axes is not None and not isinstance(suite_axes, list):
            raise ValueError(f"applicable_axes must be a list or null: {path}")
        for case in document.get("cases", []):
            if not isinstance(case, dict) or not isinstance(case.get("id"), str):
                continue
            case_id = case["id"]
            if case_id in cases:
                raise ValueError(f"duplicate canonical case id: {case_id}")
            assertions = case.get("assertions")
            if not isinstance(assertions, list) or not assertions:
                raise ValueError(f"canonical case has no assertions: {case_id}")
            prompt = case.get("prompt")
            if not isinstance(prompt, str) or not prompt:
                raise ValueError(f"canonical case has no prompt: {case_id}")
            # Preserve None: the behavioral harness defines it as the default
            # full rubric, while an explicit list restricts applicable axes.
            axes = case["applicable_axes"] if "applicable_axes" in case else suite_axes
            if axes is not None and (not isinstance(axes, list) or not axes or not all(isinstance(axis, str) and axis.strip() for axis in axes)):
                raise ValueError(f"canonical axes must be a list or null: {case_id}")
            cases[case_id] = {
                "prompt": prompt,
                "assertions": list(assertions),
                "applicable_axes": None if axes is None else list(axes),
                "suite": document.get("suite"),
                "source": str(path.relative_to(ROOT)).replace("\\", "/"),
            }

    for spec in manifest.get("cases", []):
        case_id = spec.get("id")
        if case_id not in cases:
            raise ValueError(f"manifest case is missing from behavioral registry: {case_id}")
        cases[case_id].update(
            case_group=spec.get("group"),
            selector_eligible=spec.get("selector_eligible"),
        )
    return cases


def observations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("observations")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("run must contain an observations array")
    return rows


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"cannot hash artifact {path}: {exc}") from exc


def normalize_rows(rows: list[dict[str, Any]], canonical: dict[str, dict[str, Any]], voice_axes: list[str]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, Any, str]] = set()
    for row in rows:
        case_id = row.get("case_id")
        if case_id not in canonical:
            raise ValueError(f"unknown case_id in run: {case_id}")
        reference = canonical[case_id]
        raw_prompt = row.get("prompt")
        if raw_prompt is not None and raw_prompt != reference["prompt"]:
            raise ValueError(f"prompt mismatch for canonical case {case_id}")
        arm = row.get("arm")
        if arm not in ARMS:
            raise ValueError(f"unknown arm for {case_id}: {arm}")
        key = (case_id, row.get("repetition"), arm)
        if key in seen:
            raise ValueError(f"duplicate arm observation: {key}")
        seen.add(key)
        process_status = row.get("process_status")
        semantic_status = "censored" if process_status == "timeout" else "not_scored"
        applicable_axes = reference["applicable_axes"]
        voice_language_axes = list(voice_axes) if applicable_axes is None else [axis for axis in voice_axes if axis in applicable_axes]
        normalized.append(
            {
                key_name: row.get(key_name)
                for key_name in (
                    "case_id", "arm", "repetition", "sequence", "response", "process_status",
                    "first_attempt_completion", "treatment_status", "causal_eligible", "codex_usage",
                    "codex_usage_status", "codex_tool_calls", "recorded_selector_invocations", "elapsed_seconds", "selector_trace",
                    "effective_skill_sha256", "resolved_model", "resolved_model_source",
                )
            }
            | {
                "prompt": reference["prompt"],
                "assertions": reference["assertions"],
                "applicable_axes": applicable_axes,
                "voice_language_axes": voice_language_axes,
                "case_group": reference.get("case_group"),
                "selector_eligible": reference.get("selector_eligible"),
                "semantic_status": semantic_status,
                "semantic_outcome": "not_observed" if semantic_status == "censored" else "not_scored",
            }
        )
    return normalized


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    arms: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        subset = [row for row in rows if row.get("arm") == arm]
        completed = [row for row in subset if row.get("process_status") == "completed"]
        eligible = [row for row in subset if row.get("causal_eligible") is True]
        usage = [
            row.get("codex_usage")
            for row in eligible
            if row.get("codex_usage_status") == "valid" and isinstance(row.get("codex_usage"), dict)
        ]
        elapsed = [float(row["elapsed_seconds"]) for row in eligible if isinstance(row.get("elapsed_seconds"), (int, float))]
        input_tokens = [int(item.get("input_tokens", 0)) for item in usage]
        cached_tokens = [int(item.get("cached_input_tokens", 0)) for item in usage]
        arms[arm] = {
            "observations": len(subset),
            "causal_eligible": len(eligible),
            "process_completed": len(completed),
            "first_attempt_completed": sum(row.get("first_attempt_completion") is True for row in subset),
            "timeouts": sum(row.get("process_status") == "timeout" for row in subset),
            "failed": sum(row.get("process_status") == "failed" for row in subset),
            "invalid_treatment": sum(row.get("treatment_status") == "invalid" for row in subset),
            "selector_invocations": sum(int(row.get("recorded_selector_invocations", 0) or 0) for row in subset),
            "valid_usage_observations": len(usage),
            "input_tokens": {"observations": len(input_tokens), "median": statistics.median(input_tokens) if input_tokens else None},
            "cached_input_tokens": {"observations": len(cached_tokens), "median": statistics.median(cached_tokens) if cached_tokens else None},
            "uncached_input_tokens": {"observations": len(input_tokens), "median": statistics.median([a - b for a, b in zip(input_tokens, cached_tokens)]) if input_tokens else None},
            "elapsed_seconds": {"observations": len(elapsed), "median": statistics.median(elapsed) if elapsed else None},
        }
    pairs: dict[tuple[Any, Any], set[str]] = {}
    for row in rows:
        pairs.setdefault((row.get("case_id"), row.get("repetition")), set()).add(row.get("arm"))
    incomplete = [key for key, arms_seen in pairs.items() if arms_seen != set(ARMS)]
    if incomplete:
        raise ValueError(f"incomplete paired groups: {incomplete}")
    return {
        "total_observations": len(rows),
        "unique_paired_keys": len(pairs),
        "paired_groups": len(pairs),
        "complete_paired_groups": len(pairs) - len(incomplete),
        "arms": arms,
    }


def build_packet(payload: dict[str, Any], source: Path | None = None) -> dict[str, Any]:
    manifest = read_json(MANIFEST_PATH)
    rubric = read_json(RUBRIC_PATH)
    canonical = load_canonical_cases(manifest)
    definitions = manifest.get("metrics", {}).get("definitions", {})
    voice_axes = definitions.get("voice_language_axes", [])
    if not isinstance(voice_axes, list):
        raise ValueError("manifest voice_language_axes must be a list")
    rows = normalize_rows(observations(payload), canonical, voice_axes)
    packet = {
        "schema_version": "1.1",
        "experiment_id": payload.get("experiment_id"),
        "protocol_revision": payload.get("protocol_revision", manifest.get("protocol_revision", 2)),
        "source": str(source) if source is not None else None,
        "source_sha256": sha256_file(source) if source is not None else None,
        "rubric_sha256": sha256_file(RUBRIC_PATH),
        "provenance": {key: payload.get(key) for key in ("requested_model", "resolved_model", "provider_overrides_sha256", "sandbox_mode", "provenance")},
        "preregistered": {
            "metrics": manifest.get("metrics"),
            "decision_criteria": manifest.get("decision_criteria"),
            "contrasts": manifest.get("contrasts"),
            "rubric": manifest.get("metrics", {}).get("definitions", {}),
            "canonical_rubric": rubric,
            "voice_language_scoring": {
                "axes": manifest.get("metrics", {}).get("definitions", {}).get("voice_language_axes", []),
                "scale_min": 0,
                "scale_max": 4,
                "none_applicable_axes": "None means the full canonical rubric applies, matching the behavioral loader and compare_runs.py; an explicit non-empty list restricts axes.",
                "observation_macro": "mean of the applicable voice/language axis scores for that observation",
                "normalize_percent": "100 * observation_macro / 4",
                "positive_case_denominator": 12,
                "positive_case_definition": "four selector-positive cases × three repetitions; controls are reported separately",
                "positive_case_voice_axis_denominator": 12,
            },
        },
        "operational_summary": summarize(rows),
        "semantic_scoring": {
            "full_observation_pass": "not_scored",
            "pointwise_assertion_pass_rate": "not_scored",
            "applicable_voice_language_axes": "not_scored",
            "instructions": "A human/independent grader must fill these fields from canonical assertions and rubric; this adapter performs no semantic judgement.",
        },
        "observations": rows,
    }
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet["operational_summary"]
    lines = [
        "# Voice-card selector ablation scoring packet", "",
        "This packet is deterministic scaffolding; semantic fields are intentionally not scored.", "",
        f"Experiment: `{packet.get('experiment_id')}`", f"Protocol revision: `{packet.get('protocol_revision')}`", "",
        "## Preregistered rubric and decision criteria", "", "```json",
        json.dumps(packet.get("preregistered", {}), ensure_ascii=False, indent=2), "```", "",
        "## Operational summary", "",
        "| Arm | Observations | Causal-eligible | First attempts | Timeouts | Selector calls | Median input | Median uncached input | Median elapsed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        row = summary["arms"][arm]
        lines.append(f"| {arm} | {row['observations']} | {row['causal_eligible']} | {row['first_attempt_completed']} | {row['timeouts']} | {row['selector_invocations']} | {row['input_tokens']['median']} | {row['uncached_input_tokens']['median']} | {row['elapsed_seconds']['median']} |")
    lines.extend(["", f"Paired groups: **{summary['paired_groups']}** (each must contain one A, B, and C).", "", "## Observations", ""])
    for index, row in enumerate(packet["observations"], 1):
        usage = row.get("codex_usage") or {}
        censoring = "censored (timeout; semantic outcome not observed)" if row.get("semantic_status") == "censored" else "not censored"
        lines.extend([
            f"### {index}. {row.get('case_id')} — arm {row.get('arm')}, repetition {row.get('repetition')}", "",
            f"Group: `{row.get('case_group')}`; selector eligible: `{row.get('selector_eligible')}`; applicable axes: `{', '.join(row.get('applicable_axes') or ['default full rubric'] if row.get('applicable_axes') is None else row.get('applicable_axes'))}`; voice axes scored by reviewer: `{', '.join(row.get('voice_language_axes') or [])}`.",
            f"Process: `{row.get('process_status')}`; first attempt: `{row.get('first_attempt_completion')}`; treatment: `{row.get('treatment_status')}`; causal eligible: `{row.get('causal_eligible')}`; semantic status: `{row.get('semantic_status')}`; {censoring}.",
            f"Operational: elapsed `{row.get('elapsed_seconds')}` s; input `{usage.get('input_tokens')}`; cached input `{usage.get('cached_input_tokens')}`; output `{usage.get('output_tokens')}`; reasoning `{usage.get('reasoning_output_tokens')}`; tool calls `{row.get('codex_tool_calls')}`.",
            "", "#### Prompt", "", row.get("prompt", "") or "", "", "#### Assertions", "",
        ])
        lines.extend(f"- {assertion}" for assertion in (row.get("assertions") or []))
        lines.extend(["", "#### Response", "", row.get("response", "") or "_No response recorded._", "", "#### Structured execution trace", "", "```json", json.dumps(row.get("selector_trace") or [], ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    payload = read_json(args.run)
    packet = build_packet(payload, args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(packet), encoding="utf-8")
    print(f"Wrote deterministic scoring packet to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
