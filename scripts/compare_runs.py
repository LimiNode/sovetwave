#!/usr/bin/env python3
"""Render a human scoring sheet from a behavioral eval run."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUBRIC = ROOT / "evals" / "behavioral" / "rubric.json"


def text_or_placeholder(value: str | None) -> str:
    return value if value else "_Нет ответа: вариант ещё не запускался._"


def variant_label(variant: str, result: dict[str, Any], ablation_reference: str | None = None) -> str:
    if variant == "baseline":
        return "Baseline"
    if variant == "sovetwave":
        return "Sovetwave"
    if variant == "sovetwave_style_only":
        return "Sovetwave (voice only)"
    if variant == "sovetwave_without_reference":
        reference = result.get("ablated_reference", ablation_reference or "thematic reference")
        return f"Sovetwave without `{reference}`"
    if variant == "sovetwave_without_core":
        return "Sovetwave without core skill"
    return variant


def result_text(result: dict[str, Any]) -> str:
    if not result:
        return "_Не проверялось: вариант отсутствует в файле прогона._"
    status = result.get("status", "completed")
    if status != "completed":
        return f"_Не проверялось: статус варианта — `{status}`._"
    return text_or_placeholder(result.get("response"))


def _resolve_case_metadata(
    payload: dict[str, Any],
    case_ids: list[str],
    *,
    declared_key: str,
    row_key: str,
) -> dict[str, str]:
    """Resolve case metadata, falling back to observation rows for interleaved runs."""
    declared = payload.get(declared_key)
    declared = declared if isinstance(declared, dict) else {}
    if payload.get("variant_set") == "sovetwave_revision_interleaved":
        declared = {}
    observed: dict[str, set[str]] = defaultdict(set)
    for result in payload.get("results", []):
        case_id = result.get("case_id") if isinstance(result, dict) else None
        value = result.get(row_key) if isinstance(result, dict) else None
        if isinstance(case_id, str) and isinstance(value, str):
            observed[case_id].add(value)
    resolved: dict[str, str] = {}
    for case_id in case_ids:
        value = declared.get(case_id)
        if isinstance(value, str):
            resolved[case_id] = value
            continue
        candidates = observed.get(case_id, set())
        if len(candidates) == 1:
            resolved[case_id] = next(iter(candidates))
        elif len(candidates) > 1:
            resolved[case_id] = "mixed / revision-dependent"
    return resolved


def resolve_capability_stages(payload: dict[str, Any], case_ids: list[str]) -> dict[str, str]:
    """Resolve stage coverage, including interleaved runs without a top-level map."""
    return _resolve_case_metadata(
        payload, case_ids, declared_key="case_capability_stages", row_key="capability_stage"
    )


def resolve_decision_impacts(payload: dict[str, Any], case_ids: list[str]) -> dict[str, str]:
    """Resolve decision-impact coverage from run metadata or observation rows."""
    return _resolve_case_metadata(
        payload, case_ids, declared_key="case_decision_impacts", row_key="decision_impact"
    )


def resolve_evidence_access(payload: dict[str, Any], case_ids: list[str]) -> dict[str, str]:
    """Resolve evidence-access coverage from run metadata or observation rows."""
    return _resolve_case_metadata(
        payload, case_ids, declared_key="case_evidence_access", row_key="evidence_access"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload: dict[str, Any] = json.loads(args.run.read_text(encoding="utf-8"))
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    grouped: dict[str, dict[int, dict[str, dict[str, Any]]]] = defaultdict(lambda: defaultdict(dict))
    for result in payload.get("results", []):
        grouped[result["case_id"]][int(result.get("repetition", 1))][result["variant"]] = result
    if not grouped:
        raise SystemExit("run contains no results")

    ablation = payload.get("ablation")
    ablation_reference = ablation.get("reference") if isinstance(ablation, dict) else None
    variant_orders = {
        int(item["repetition"]): item["variants"]
        for item in payload.get("variant_orders", [])
        if isinstance(item, dict)
        and isinstance(item.get("repetition"), int)
        and isinstance(item.get("variants"), list)
        and all(isinstance(variant, str) for variant in item["variants"])
    }
    variant_set = payload.get("variant_set")
    observed_variants = {result.get("variant") for result in payload.get("results", [])}
    expected_variants = ["baseline"]
    if variant_set == "claude_three_arm" or "sovetwave_style_only" in observed_variants:
        expected_variants.extend(["sovetwave_style_only", "sovetwave"])
    else:
        expected_variants.append("sovetwave")
    if ablation is not None:
        expected_variants.append(
            "sovetwave_without_core"
            if ablation.get("reference") == "core skill"
            else "sovetwave_without_reference"
        )
    case_ids = payload.get("case_ids") or list(grouped)
    case_capability_stages = resolve_capability_stages(payload, case_ids)
    case_decision_impacts = resolve_decision_impacts(payload, case_ids)
    case_evidence_access = resolve_evidence_access(payload, case_ids)
    case_relations = {
        case_id: relation
        for case_id, relation in payload.get("case_relations", {}).items()
        if isinstance(case_id, str)
        and isinstance(relation, dict)
        and relation.get("kind") in {"contrast", "directional", "invariance"}
        and isinstance(relation.get("base_case"), str)
    }
    repetitions = int(payload.get("repetitions", max((max(items) for items in grouped.values()), default=1)))
    lines = ["# Behavioral eval comparison", "", f"Run: `{args.run.name}`", ""]
    if ablation is None:
        lines.extend(["Ablation: **не проверялось** (вариант без тематической справки не запускался).", ""])
    else:
        lines.extend([
            f"Ablation: `{ablation.get('reference', 'unknown')}` — **{ablation.get('status', 'not_tested')}**.",
            f"Method: {ablation.get('method', 'not recorded')}",
            f"Order balance: **{payload.get('order_balance', ablation.get('order_balance', 'not_recorded'))}**.",
            "",
        ])
    stage_counts = Counter(case_capability_stages.get(case_id, "unclassified") for case_id in case_ids)
    lines.extend([
        "## Capability coverage",
        "",
        "`capability_stage` classifies the primary agent capability exercised by a case; it is coverage metadata, not a semantic score.",
        "",
        "| Capability stage | Cases |",
        "|---|---:|",
    ])
    for stage, count in sorted(stage_counts.items()):
        lines.append(f"| `{stage}` | {count} |")
    lines.append("")
    for title, field, description, values in (
        (
            "Decision impact coverage",
            "Decision impact",
            "`decision_impact` describes the consequence of a decision; it is coverage metadata, not a semantic score.",
            case_decision_impacts,
        ),
        (
            "Evidence access coverage",
            "Evidence access",
            "`evidence_access` describes how the relevant evidence can be obtained; it is coverage metadata, not a semantic score.",
            case_evidence_access,
        ),
    ):
        counts = Counter(values.get(case_id, "unclassified") for case_id in case_ids)
        lines.extend([
            f"## {title}",
            "",
            description,
            "",
            f"| {field} | Cases |",
            "|---|---:|",
        ])
        for value, count in sorted(counts.items()):
            lines.append(f"| `{value}` | {count} |")
        lines.append("")
    if case_relations:
        lines.extend([
            "## Case relationships",
            "",
            "Relations are declared in the case schema and validated structurally (kind, base case, and optional expectation). Semantic agreement is **not evaluated** by this renderer.",
            "",
            "| Case | Relation | Base case | Declared expectation | Semantic status |",
            "|---|---|---|---|---|",
        ])
        for case_id in case_ids:
            relation = case_relations.get(case_id)
            if relation is not None:
                expectation = str(relation.get("expect", "")).replace("|", "\\|") or "—"
                lines.append(f"| `{case_id}` | `{relation['kind']}` | `{relation['base_case']}` | {expectation} | `not_evaluated` |")
        lines.append("")
    for case_id in case_ids:
        case_repetitions = grouped.get(case_id, {})
        known_prompt = next(
            (result.get("prompt", "") for variants in case_repetitions.values() for result in variants.values()),
            "",
        )
        mode = payload.get("case_execution_modes", {}).get(case_id)
        capability_stage = case_capability_stages.get(case_id)
        decision_impact = case_decision_impacts.get(case_id)
        evidence_access = case_evidence_access.get(case_id)
        lines.extend([f"## {case_id}", ""])
        if mode:
            lines.extend([f"Execution mode: `{mode}`.", ""])
        if capability_stage:
            lines.extend([f"Capability stage: `{capability_stage}`.", ""])
        if decision_impact:
            lines.extend([f"Decision impact: `{decision_impact}`.", ""])
        if evidence_access:
            lines.extend([f"Evidence access: `{evidence_access}`.", ""])
        relation = case_relations.get(case_id)
        if relation is not None:
            lines.extend([
                f"Relation: **{relation['kind']}** relative to `{relation['base_case']}`.",
                f"Declared expectation: {relation.get('expect', 'not specified')}.",
                "Semantic relation status: **not_evaluated** (schema metadata is not a model-behaviour verdict).",
                "",
            ])
        for repetition in range(1, repetitions + 1):
            variants = case_repetitions.get(repetition, {})
            baseline = variants.get("baseline", {})
            sovetwave = variants.get("sovetwave", {})
            ordered_variants = list(expected_variants)
            ordered_variants.extend(sorted(variant for variant in variants if variant not in ordered_variants))
            sample = baseline or sovetwave or next(iter(variants.values()), {})
            lines.extend([f"### Repetition {repetition}", ""])
            if repetition in variant_orders:
                execution_order = " → ".join(
                    variant_label(variant, {}, ablation_reference)
                    for variant in variant_orders[repetition]
                )
                lines.extend([f"Planned execution order: {execution_order}", ""])
            lines.extend(["#### Prompt", "", sample.get("prompt", known_prompt)])
            for variant in ordered_variants:
                result = variants.get(variant, {})
                lines.extend(["", f"#### {variant_label(variant, result, ablation_reference)}", ""])
                if result:
                    status = result.get("process_status", result.get("status", "unknown"))
                    semantic = result.get("semantic_status", "not_recorded")
                    trace = ", ".join(result.get("tool_trace", [])) if isinstance(result.get("tool_trace"), list) else ""
                    lines.append(f"Process: `{status}`; semantic: `{semantic}`; tools observed: `{trace or 'not recorded'}`.")
                    lines.append("")
                lines.append(result_text(result))
            headings = " | ".join(
                variant_label(variant, variants.get(variant, {}), ablation_reference)
                for variant in ordered_variants
            )
            separators = " | ".join("---:" for _ in ordered_variants)
            blanks = " | ".join(" " for _ in ordered_variants)
            lines.extend([
                "", "#### Human score (0–4)", "",
                f"| Axis | Weight | {headings} | Notes |",
                f"|---|---:|{separators}|---|",
            ])
            applicable_axes = sample.get("applicable_axes")
            for axis in rubric["axes"]:
                if isinstance(applicable_axes, list) and axis["id"] not in applicable_axes:
                    continue
                lines.append(f"| {axis['label']} | {axis['weight']} | {blanks} |  |")
            lines.extend(["", "Assertions:"])
            lines.extend(f"- {assertion}" for assertion in sample.get("assertions", []))
            lines.append("")
    output = args.output or args.run.with_suffix(".md")
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote comparison sheet to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
