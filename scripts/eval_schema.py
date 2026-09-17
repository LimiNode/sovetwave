"""Shared behavioral-evaluation schema helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUBRIC = ROOT / "evals" / "behavioral" / "rubric.json"
CAPABILITY_STAGES = frozenset({
    "instruction_interpretation",
    "grounding",
    "inquiry",
    "action_selection",
    "implementation",
    "verification_selection",
    "evidence_interpretation",
    "reporting",
    "voice_realization",
})
DECISION_IMPACTS = frozenset({"low", "medium", "high"})
EVIDENCE_ACCESS_LEVELS = frozenset({
    "direct",
    "repository_inferable",
    "executable",
    "external_required",
    "unavailable",
})


def rubric_axis_ids(path: Path = RUBRIC) -> frozenset[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(axis["id"] for axis in payload["axes"] if isinstance(axis, dict) and isinstance(axis.get("id"), str))


def validate_applicable_axes(value: Any, *, allowed: frozenset[str]) -> None:
    if value is None:
        return
    if not isinstance(value, list) or not value or not all(isinstance(axis, str) and axis.strip() for axis in value):
        raise ValueError("applicable_axes must be a non-empty array of strings")
    if len(set(value)) != len(value):
        raise ValueError("applicable_axes must not contain duplicate rubric axes")
    unknown = [axis for axis in value if axis not in allowed]
    if unknown:
        raise ValueError(f"applicable_axes contains unknown rubric axis: {unknown[0]!r}")


def validate_capability_stage(value: Any) -> None:
    """Validate an optional primary capability classification for an eval case."""
    if value is None:
        return
    if not isinstance(value, str) or value not in CAPABILITY_STAGES:
        allowed = ", ".join(sorted(CAPABILITY_STAGES))
        raise ValueError(f"capability_stage must be one of: {allowed}")


def validate_decision_impact(value: Any) -> None:
    """Validate optional metadata describing the consequence of a decision."""
    if value is None:
        return
    if not isinstance(value, str) or value not in DECISION_IMPACTS:
        allowed = ", ".join(sorted(DECISION_IMPACTS))
        raise ValueError(f"decision_impact must be one of: {allowed}")


def validate_evidence_access(value: Any) -> None:
    """Validate optional metadata describing how evidence can be obtained."""
    if value is None:
        return
    if not isinstance(value, str) or value not in EVIDENCE_ACCESS_LEVELS:
        allowed = ", ".join(sorted(EVIDENCE_ACCESS_LEVELS))
        raise ValueError(f"evidence_access must be one of: {allowed}")
