#!/usr/bin/env python3
"""Retry only failed invocations from a behavioral-eval JSON/JSONL run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_model_evals import DEFAULT_CASES, codex_provider_overrides, load_cases, run_variant


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="completed JSON result or append-only JSONL checkpoint")
    parser.add_argument("--output", type=Path, required=True, help="JSONL file for retried observations")
    parser.add_argument("--codex-provider-config", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    source_rows = (
        json.loads(args.source.read_text(encoding="utf-8"))["results"]
        if args.source.suffix.lower() == ".json"
        else [json.loads(line) for line in args.source.read_text(encoding="utf-8").splitlines() if line.strip()]
    )
    failed = [row for row in source_rows if row.get("process_status") != "completed"]
    if not failed:
        print("No failed invocations to retry.")
        return 0
    cases = {case["id"]: case for case in load_cases(DEFAULT_CASES)}
    overrides = codex_provider_overrides(args.codex_provider_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for index, previous in enumerate(failed, start=1):
            case = cases[previous["case_id"]]
            result = run_variant(
                "codex",
                case,
                previous["variant"] == "sovetwave",
                None,
                args.timeout,
                False,
                overrides,
                repetition=previous["repetition"],
                sequence=previous["sequence"],
                activation=previous.get("activation", "explicit"),
            )
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"[{index}/{len(failed)}] {case['id']} r{previous['repetition']} {previous['variant']} {result['process_status']}", flush=True)
    return 0 if all(json.loads(line).get("process_status") == "completed" for line in args.output.read_text(encoding="utf-8").splitlines()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
