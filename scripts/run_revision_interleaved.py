#!/usr/bin/env python3
"""Interleave Sovetwave-only observations from two checked-out revisions."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def load_runner(root: Path, label: str):
    path = root / "scripts" / "run_model_evals.py"
    spec = importlib.util.spec_from_file_location(f"run_model_evals_{label}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load runner from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def interleaved_orders(repetitions: int) -> list[dict[str, object]]:
    """Return balanced AB/BA pairs (AB, BA, BA, AB over four repeats)."""
    pattern = [
        ["revision_a", "revision_b"],
        ["revision_b", "revision_a"],
        ["revision_b", "revision_a"],
        ["revision_a", "revision_b"],
    ]
    return [
        {
            "repetition": repetition,
            "revisions": pattern[(repetition - 1) % len(pattern)],
        }
        for repetition in range(1, repetitions + 1)
    ]


def git_provenance(root: Path) -> dict[str, object]:
    """Return immutable checkout identity plus its current dirty-state."""
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
        check=True, capture_output=True, text=True,
    ).stdout
    return {"head": head, "dirty": bool(status)}


def prepare_checkpoint(checkpoint: Path, metadata: dict[str, object]) -> Path:
    """Create checkpoint storage before writing its provenance sidecar."""
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = checkpoint.with_suffix(".meta.json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision-a", type=Path, required=True)
    parser.add_argument("--revision-b", type=Path, required=True)
    parser.add_argument("--case-id", action="append", required=True)
    parser.add_argument("--repetitions", type=int, default=4)
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--codex-provider-config", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path,
                        help="append one JSON result per observation (defaults to output .jsonl)")
    parser.add_argument("--resume", action="store_true",
                        help="skip observations already present in the checkpoint")
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    roots = {"revision_a": args.revision_a.resolve(), "revision_b": args.revision_b.resolve()}
    provenance = {label: git_provenance(root) for label, root in roots.items()}
    runners = {label: load_runner(root, label) for label, root in roots.items()}
    cases_by_label = {}
    for label, runner in runners.items():
        cases = {case["id"]: case for case in runner.load_cases(runner.DEFAULT_CASES)}
        missing = [case_id for case_id in args.case_id if case_id not in cases]
        if missing:
            parser.error(f"{label}: unknown case {missing[0]!r}")
        cases_by_label[label] = cases
    overrides = {
        label: runner.codex_provider_overrides(args.codex_provider_config)
        for label, runner in runners.items()
    }

    # Alternate the two revisions within each repetition.  Across four
    # repetitions this yields AB, BA, BA, AB: an ABBA/BAAB-balanced sequence
    # with exactly two calls per case and repetition.
    orders = interleaved_orders(args.repetitions)

    checkpoint = (args.checkpoint or args.output.with_suffix(".jsonl")).resolve()
    metadata_path = checkpoint.with_suffix(".meta.json")
    expected_metadata = {
        "revision_roots": {key: str(value) for key, value in roots.items()},
        "revision_provenance": provenance,
        "model": args.model,
        "case_ids": args.case_id,
        "repetitions": args.repetitions,
    }
    results = []
    if args.resume:
        if not checkpoint.exists() or not metadata_path.exists():
            parser.error("--resume requires an existing checkpoint and provenance metadata")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata != expected_metadata:
            parser.error("checkpoint provenance does not match revisions, model, cases, or repetitions")
        results = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in results:
            label = row.get("revision_label")
            if (
                label not in roots
                or row.get("revision_root") != str(roots[label])
                or row.get("requested_model") != args.model
                or row.get("case_id") not in args.case_id
            ):
                parser.error("checkpoint observation provenance does not match the requested experiment")
    elif checkpoint.exists() or metadata_path.exists():
        parser.error("checkpoint already exists; use --resume with matching provenance or choose a new path")
    seen = {(r.get("case_id"), r.get("repetition"), r.get("sequence"), r.get("revision_label")) for r in results}
    prepare_checkpoint(checkpoint, expected_metadata)
    for case_id in args.case_id:
        for repetition in range(1, args.repetitions + 1):
            for sequence, label in enumerate(orders[repetition - 1]["revisions"], start=1):
                key = (case_id, repetition, sequence, label)
                if key in seen:
                    continue
                runner = runners[label]
                result = runner.run_variant(
                    "codex", cases_by_label[label][case_id], True, args.model,
                    args.timeout, False, overrides[label], None, repetition, sequence,
                    "explicit", False, "project", None, None,
                )
                result["revision_label"] = label
                result["revision_root"] = str(roots[label])
                results.append(result)
                with checkpoint.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(result, ensure_ascii=False) + "\n")
                    stream.flush()
                seen.add(key)
                print(f"[{len(results)}] {case_id} r{repetition} {label} process={result.get('process_status')}", flush=True)

    payload = {
        "schema_version": "1.0",
        "provider": "codex",
        "model": args.model,
        "variant_set": "sovetwave_revision_interleaved",
        "repetitions": args.repetitions,
        "case_ids": args.case_id,
        "revision_roots": {k: str(v) for k, v in roots.items()},
        "variant_orders": orders,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(results)} observations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
