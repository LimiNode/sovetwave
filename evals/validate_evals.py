#!/usr/bin/env python3
"""Validate Sovetwave eval-suite fixtures without running a model."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from eval_schema import (
    rubric_axis_ids,
    validate_applicable_axes,
    validate_capability_stage,
    validate_decision_impact,
    validate_evidence_access,
)


REQUIRED_SUITE_FIELDS = {"version": str, "suite": str, "cases": list}
REQUIRED_CASE_FIELDS = {"id": str, "prompt": str, "assertions": list}
CASE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
EXECUTION_MODES = {"prompt_only", "repository_grounded"}
RUBRIC_AXES = rubric_axis_ids()


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)


def validate_suite(path: Path, seen_ids: set[str]) -> int:
    errors = 0
    try:
        suite = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"{path}: invalid JSON: {error}")
        return 1

    for key, expected_type in REQUIRED_SUITE_FIELDS.items():
        if not isinstance(suite.get(key), expected_type):
            fail(f"{path}: {key!r} must be {expected_type.__name__}")
            errors += 1

    if not isinstance(suite.get("cases"), list) or not suite.get("cases"):
        fail(f"{path}: cases must contain at least one case")
        return errors + 1
    try:
        validate_applicable_axes(suite.get("applicable_axes"), allowed=RUBRIC_AXES)
    except ValueError as error:
        fail(f"{path}: {error}")
        errors += 1
    try:
        validate_capability_stage(suite.get("capability_stage"))
    except ValueError as error:
        fail(f"{path}: {error}")
        errors += 1
    try:
        validate_decision_impact(suite.get("decision_impact"))
    except ValueError as error:
        fail(f"{path}: {error}")
        errors += 1
    try:
        validate_evidence_access(suite.get("evidence_access"))
    except ValueError as error:
        fail(f"{path}: {error}")
        errors += 1
    suite_mode = suite.get("execution_mode", "prompt_only")
    if suite_mode not in EXECUTION_MODES:
        fail(f"{path}: unsupported execution_mode {suite_mode!r}")
        errors += 1

    for case in suite["cases"]:
        if not isinstance(case, dict):
            fail(f"{path}: every case must be an object")
            errors += 1
            continue
        for key, expected_type in REQUIRED_CASE_FIELDS.items():
            if not isinstance(case.get(key), expected_type) or not case.get(key):
                fail(f"{path}: case {case.get('id', '<missing>')!r} has invalid {key!r}")
                errors += 1
        case_id = case.get("id")
        if isinstance(case_id, str):
            if not CASE_ID.fullmatch(case_id):
                fail(f"{path}: case id {case_id!r} must match {CASE_ID.pattern!r}")
                errors += 1
            if case_id in seen_ids:
                fail(f"duplicate eval id: {case_id}")
                errors += 1
            seen_ids.add(case_id)
        assertions = case.get("assertions")
        if isinstance(assertions, list) and not all(isinstance(item, str) and item.strip() for item in assertions):
            fail(f"{path}: assertions for {case_id!r} must be non-empty strings")
            errors += 1
        mode = case.get("execution_mode", suite_mode)
        if mode not in EXECUTION_MODES:
            fail(f"{path}: unsupported execution_mode for {case_id!r}: {mode!r}")
            errors += 1
        fixture = case.get("fixture", suite.get("fixture"))
        if fixture is not None:
            fixture_path = Path(fixture) if isinstance(fixture, str) else None
            if fixture_path is None or not fixture or fixture_path.is_absolute() or ".." in fixture_path.parts:
                fail(f"{path}: fixture for {case_id!r} must be a relative path without '..'")
                errors += 1
            else:
                resolved = (path.parent.parent / "fixtures" / fixture).resolve()
                fixture_root = (path.parent.parent / "fixtures").resolve()
                if fixture_root not in resolved.parents or not resolved.is_dir():
                    fail(f"{path}: fixture directory does not exist for {case_id!r}: {resolved}")
                    errors += 1
        applicable_axes = case.get("applicable_axes", suite.get("applicable_axes"))
        try:
            validate_applicable_axes(applicable_axes, allowed=RUBRIC_AXES)
        except ValueError as error:
            fail(f"{path}: {error}")
            errors += 1
        capability_stage = case.get("capability_stage", suite.get("capability_stage"))
        try:
            validate_capability_stage(capability_stage)
        except ValueError as error:
            fail(f"{path}: case {case_id!r}: {error}")
            errors += 1
        decision_impact = case.get("decision_impact", suite.get("decision_impact"))
        try:
            validate_decision_impact(decision_impact)
        except ValueError as error:
            fail(f"{path}: case {case_id!r}: {error}")
            errors += 1
        evidence_access = case.get("evidence_access", suite.get("evidence_access"))
        try:
            validate_evidence_access(evidence_access)
        except ValueError as error:
            fail(f"{path}: case {case_id!r}: {error}")
            errors += 1
        checks = case.get("checks", {})
        if not isinstance(checks, dict):
            fail(f"{path}: checks for {case_id!r} must be an object")
            errors += 1
            continue
        for name in ("contains_all", "contains_any", "not_contains"):
            if name in checks and (not isinstance(checks[name], list) or not all(isinstance(item, str) for item in checks[name])):
                fail(f"{path}: {name} for {case_id!r} must be an array of strings")
                errors += 1
        prior_turns = case.get("prior_turns")
        if prior_turns is not None:
            if not isinstance(prior_turns, list) or not prior_turns:
                fail(f"{path}: prior_turns for {case_id!r} must be a non-empty array")
                errors += 1
            elif not all(
                isinstance(turn, dict)
                and isinstance(turn.get("prompt"), str)
                and turn["prompt"].strip()
                and isinstance(turn.get("expected_state"), str)
                and turn["expected_state"].strip()
                for turn in prior_turns
            ):
                fail(f"{path}: prior_turns for {case_id!r} must contain prompt and expected_state strings")
                errors += 1
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-dir", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    paths = sorted(path for path in args.eval_dir.glob("*.json") if path.name != "schema.json")
    behavioral_dir = args.eval_dir / "behavioral" / "cases"
    paths.extend(sorted(behavioral_dir.glob("*.json")))
    if not paths:
        fail("no eval suite JSON files found")
        return 1

    seen_ids: set[str] = set()
    errors = sum(validate_suite(path, seen_ids) for path in paths)
    if errors:
        fail(f"{errors} validation error(s)")
        return 1
    print(f"Validated {len(paths)} suites and {len(seen_ids)} cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
