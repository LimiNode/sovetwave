#!/usr/bin/env python3
"""Build a deterministic, non-semantic scoring packet for the A/B/C pilot."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def observations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("observations")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("run must contain an observations array")
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    arms: dict[str, dict[str, Any]] = {}
    for arm in ("A", "B", "C"):
        subset = [row for row in rows if row.get("arm") == arm]
        completed = [row for row in subset if row.get("process_status") == "completed"]
        eligible = [row for row in subset if row.get("causal_eligible") is True]
        usage = [row.get("codex_usage") for row in eligible if row.get("codex_usage_status") == "valid" and isinstance(row.get("codex_usage"), dict)]
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
            "selector_invocations": sum(int(row.get("recorded_selector_invocations", 0)) for row in subset),
            "valid_usage_observations": len(usage),
            "input_tokens": {"observations": len(input_tokens), "median": statistics.median(input_tokens) if input_tokens else None},
            "cached_input_tokens": {"observations": len(cached_tokens), "median": statistics.median(cached_tokens) if cached_tokens else None},
            "uncached_input_tokens": {"observations": len(input_tokens), "median": statistics.median([a - b for a, b in zip(input_tokens, cached_tokens)]) if input_tokens else None},
            "elapsed_seconds": {"observations": len(elapsed), "median": statistics.median(elapsed) if elapsed else None},
        }
    keys = {(row.get("case_id"), row.get("repetition"), row.get("sequence")) for row in rows}
    return {"total_observations": len(rows), "unique_paired_keys": len(keys), "arms": arms}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.run.read_text(encoding="utf-8"))
    rows = observations(payload)
    summary = summarize(rows)
    packet = {
        "schema_version": "1.0",
        "experiment_id": payload.get("experiment_id"),
        "protocol_revision": payload.get("protocol_revision", 2),
        "source": str(args.run),
        "provenance": {key: payload.get(key) for key in ("requested_model", "resolved_model", "provider_overrides_sha256", "sandbox_mode", "provenance")},
        "operational_summary": summary,
        "semantic_scoring": {
            "full_observation_pass": "not_scored",
            "pointwise_assertion_pass_rate": "not_scored",
            "applicable_voice_language_axes": "not_scored",
            "instructions": "A human/independent grader must fill these fields from responses and preregistered assertions; this adapter performs no semantic judgement.",
        },
        "observations": [
            {key: row.get(key) for key in ("case_id", "arm", "repetition", "sequence", "response", "assertions", "applicable_axes", "process_status", "first_attempt_completion", "treatment_status", "causal_eligible", "codex_usage", "codex_usage_status", "codex_tool_calls", "elapsed_seconds", "selector_trace", "effective_skill_sha256", "resolved_model", "resolved_model_source")}
            for row in rows
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote deterministic scoring packet to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
