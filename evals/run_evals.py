#!/usr/bin/env python3
"""Validate Sovetwave eval suites and optionally check deterministic fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_SUITE_FIELDS = {"version": str, "suite": str, "cases": list}
REQUIRED_CASE_FIELDS = {"id": str, "prompt": str, "assertions": list}


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
            if case_id in seen_ids:
                fail(f"duplicate eval id: {case_id}")
                errors += 1
            seen_ids.add(case_id)
        checks = case.get("checks", {})
        if not isinstance(checks, dict):
            fail(f"{path}: checks for {case_id!r} must be an object")
            errors += 1
            continue
        for name in ("contains_all", "contains_any", "not_contains"):
            if name in checks and (not isinstance(checks[name], list) or not all(isinstance(item, str) for item in checks[name])):
                fail(f"{path}: {name} for {case_id!r} must be an array of strings")
                errors += 1
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-dir", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    paths = sorted(path for path in args.eval_dir.glob("*.json") if path.name != "schema.json")
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
