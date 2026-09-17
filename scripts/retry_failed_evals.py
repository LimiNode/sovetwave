#!/usr/bin/env python3
"""Retry only failed invocations from a behavioral-eval JSON/JSONL run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_model_evals import (
    CORE_ABLATION,
    DEFAULT_CASES,
    FAILED_STATUSES,
    codex_provider_overrides,
    load_cases,
    repository_material_inputs_dirty,
    repository_revision,
    run_variant,
)


def retry_parameters(
    previous: dict,
    current_revision: str | None,
    *,
    current_inputs_dirty: bool | None = False,
    allow_revision_change: bool = False,
) -> tuple[bool, str | None, str | None]:
    """Recover the exact Codex arm represented by one failed observation."""
    if previous.get("provider") != "codex":
        raise ValueError("retry supports only observations produced by the codex provider")
    source_revision = previous.get("skill_revision")
    source_inputs_dirty = previous.get("material_inputs_dirty")
    incompatible_revision = source_revision != current_revision
    incompatible_dirty_state = source_inputs_dirty is not False or current_inputs_dirty is not False
    if (incompatible_revision or incompatible_dirty_state) and not allow_revision_change:
        raise ValueError(
            "material inputs cannot be shown to match the failed observation "
            f"(revision {source_revision!r} != {current_revision!r}; "
            f"source dirty={source_inputs_dirty!r}; current dirty={current_inputs_dirty!r}); "
            "pass --allow-revision-change to retry explicitly"
        )
    variant = previous.get("variant")
    model = previous.get("requested_model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ValueError(f"invalid requested_model in failed observation: {model!r}")
    if variant == "baseline":
        return False, None, model
    if variant == "sovetwave":
        return True, None, model
    if variant == "sovetwave_without_reference":
        reference = previous.get("ablated_reference")
        if not isinstance(reference, str) or not reference:
            raise ValueError("reference ablation is missing ablated_reference")
        return True, reference, model
    if variant == "sovetwave_without_core":
        return True, CORE_ABLATION, model
    raise ValueError(f"unsupported failed experimental variant: {variant!r}")


def retryable_rows(source_rows: list[dict]) -> list[dict]:
    """Select executed failures and reject non-executed or unknown states."""
    allowed = FAILED_STATUSES | {"completed"}
    unexpected = [row for row in source_rows if row.get("process_status") not in allowed]
    if unexpected:
        statuses = sorted({str(row.get("process_status")) for row in unexpected})
        raise ValueError(
            "source contains non-retryable observations "
            f"({', '.join(statuses)}); planned or otherwise non-executed observations cannot be recovered"
        )
    return [row for row in source_rows if row.get("process_status") in FAILED_STATUSES]


def verify_case_snapshot(previous: dict, case: dict) -> None:
    """Refuse a retry when the current case no longer matches its observation."""
    for field in (
        "prompt",
        "assertions",
        "execution_mode",
        "fixture",
        "capability_stage",
        "decision_impact",
        "evidence_access",
    ):
        if previous.get(field) != case.get(field):
            raise ValueError(f"case {previous.get('case_id')!r} changed field {field!r} since the observation")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="completed JSON result or append-only JSONL checkpoint")
    parser.add_argument("--output", type=Path, required=True, help="JSONL file for retried observations")
    parser.add_argument("--codex-provider-config", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--allow-revision-change", action="store_true")
    args = parser.parse_args()

    if args.source.resolve() == args.output.resolve():
        raise ValueError("recovery output must differ from the source audit file")
    if args.output.exists():
        raise FileExistsError(f"recovery output already exists; refusing to overwrite audit file: {args.output}")

    source_payload = json.loads(args.source.read_text(encoding="utf-8")) if args.source.suffix.lower() == ".json" else None
    source_rows = source_payload["results"] if source_payload is not None else [json.loads(line) for line in args.source.read_text(encoding="utf-8").splitlines() if line.strip()]
    source_revision = source_payload.get("skill_revision") if source_payload is not None else None
    source_dirty = source_payload.get("material_inputs_dirty") if source_payload is not None else None
    current_revision = repository_revision()
    current_inputs_dirty = repository_material_inputs_dirty()
    failed = retryable_rows(source_rows)
    if not failed:
        print("No failed invocations to retry.")
        return 0
    cases = {case["id"]: case for case in load_cases(DEFAULT_CASES)}
    overrides = codex_provider_overrides(args.codex_provider_config)
    prepared: list[tuple[dict, dict, bool, str | None, str | None, str | None]] = []
    for previous_row in failed:
        case_id = previous_row.get("case_id")
        if case_id not in cases:
            raise ValueError(f"source refers to unknown behavioral case: {case_id!r}")
        case = cases[case_id]
        previous = previous_row
        if "skill_revision" not in previous and source_revision is not None:
            previous = dict(previous, skill_revision=source_revision)
        if "material_inputs_dirty" not in previous and source_dirty is not None:
            previous = dict(previous, material_inputs_dirty=source_dirty)
        verify_case_snapshot(previous, case)
        styled, ablated_reference, model = retry_parameters(
            previous, current_revision,
            current_inputs_dirty=current_inputs_dirty,
            allow_revision_change=args.allow_revision_change,
        )
        original_process_status = previous.get(
            "original_process_status",
            previous.get("process_status"),
        )
        prepared.append((previous, case, styled, ablated_reference, model, original_process_status))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        for index, (previous, case, styled, ablated_reference, model, original_process_status) in enumerate(prepared, start=1):
            result = run_variant(
                "codex",
                case,
                styled,
                model,
                args.timeout,
                False,
                overrides,
                ablated_reference=ablated_reference,
                repetition=previous["repetition"],
                sequence=previous["sequence"],
                activation=previous.get("activation", "explicit"),
                attempt=int(previous.get("attempt", 1)) + 1,
                recovered=True,
                original_process_status=original_process_status,
            )
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"[{index}/{len(failed)}] {case['id']} r{previous['repetition']} {previous['variant']} {result['process_status']}", flush=True)
    return 0 if all(json.loads(line).get("process_status") == "completed" for line in args.output.read_text(encoding="utf-8").splitlines()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
