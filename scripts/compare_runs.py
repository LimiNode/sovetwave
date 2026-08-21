#!/usr/bin/env python3
"""Render a human scoring sheet from a behavioral eval run."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUBRIC = ROOT / "evals" / "behavioral" / "rubric.json"


def text_or_placeholder(value: str | None) -> str:
    return value if value else "_Нет ответа: вариант ещё не запускался._"


def variant_label(variant: str, result: dict[str, Any]) -> str:
    if variant == "baseline":
        return "Baseline"
    if variant == "sovetwave":
        return "Sovetwave"
    if variant == "sovetwave_without_reference":
        reference = result.get("ablated_reference", "thematic reference")
        return f"Sovetwave without `{reference}`"
    return variant


def result_text(result: dict[str, Any]) -> str:
    if not result:
        return "_Не проверялось: вариант отсутствует в файле прогона._"
    status = result.get("status", "completed")
    if status != "completed":
        return f"_Не проверялось: статус варианта — `{status}`._"
    return text_or_placeholder(result.get("response"))


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
    lines = ["# Behavioral eval comparison", "", f"Run: `{args.run.name}`", ""]
    if ablation is None:
        lines.extend(["Ablation: **не проверялось** (вариант без тематической справки не запускался).", ""])
    else:
        lines.extend([
            f"Ablation: `{ablation.get('reference', 'unknown')}` — **{ablation.get('status', 'not_tested')}**.",
            f"Method: {ablation.get('method', 'not recorded')}",
            "",
        ])
    for case_id, repetitions in grouped.items():
        lines.extend([f"## {case_id}", ""])
        for repetition, variants in sorted(repetitions.items()):
            baseline = variants.get("baseline", {})
            sovetwave = variants.get("sovetwave", {})
            ordered_variants = [variant for variant in ("baseline", "sovetwave") if variant in variants]
            ordered_variants.extend(sorted(variant for variant in variants if variant not in ordered_variants))
            sample = baseline or sovetwave or next(iter(variants.values()))
            lines.extend([f"### Repetition {repetition}", "", "#### Prompt", "", sample.get("prompt", "")])
            for variant in ordered_variants:
                result = variants[variant]
                lines.extend(["", f"#### {variant_label(variant, result)}", "", result_text(result)])
            headings = " | ".join(variant_label(variant, variants[variant]) for variant in ordered_variants)
            separators = " | ".join("---:" for _ in ordered_variants)
            blanks = " | ".join(" " for _ in ordered_variants)
            lines.extend([
                "", "#### Human score (0–4)", "",
                f"| Axis | Weight | {headings} | Notes |",
                f"|---|---:|{separators}|---|",
            ])
            for axis in rubric["axes"]:
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
