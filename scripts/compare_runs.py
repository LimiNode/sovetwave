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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload: dict[str, Any] = json.loads(args.run.read_text(encoding="utf-8"))
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for result in payload.get("results", []):
        grouped[result["case_id"]][result["variant"]] = result
    if not grouped:
        raise SystemExit("run contains no results")

    lines = ["# Behavioral eval comparison", "", f"Run: `{args.run.name}`", ""]
    for case_id, variants in grouped.items():
        baseline = variants.get("baseline", {})
        sovetwave = variants.get("sovetwave", {})
        lines.extend([
            f"## {case_id}", "", "### Prompt", "", baseline.get("prompt", sovetwave.get("prompt", "")),
            "", "### Baseline", "", text_or_placeholder(baseline.get("response")),
            "", "### Sovetwave", "", text_or_placeholder(sovetwave.get("response")),
            "", "### Human score (0–4)", "", "| Axis | Weight | Baseline | Sovetwave | Notes |",
            "|---|---:|---:|---:|---|",
        ])
        for axis in rubric["axes"]:
            lines.append(f"| {axis['label']} | {axis['weight']} |  |  |  |")
        lines.extend(["", "Assertions:"])
        lines.extend(f"- {assertion}" for assertion in baseline.get("assertions", sovetwave.get("assertions", [])))
        lines.append("")
    output = args.output or args.run.with_suffix(".md")
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote comparison sheet to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
