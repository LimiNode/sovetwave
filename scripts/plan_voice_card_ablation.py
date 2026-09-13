#!/usr/bin/env python3
"""Validate and materialize the design-only voice-card ablation pilot.

This planner never invokes a model.  It produces the 54 planned observations
and checks that the static arm is an exact snapshot of the current selector.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evals" / "experiments" / "voice-card-selector-ablation.json"
STATIC_MAP = ROOT / "evals" / "experiments" / "voice-card-static-routing.json"
CORPUS = ROOT / "skills" / "sovetwave" / "references" / "voice-cards.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def selector_module():
    path = ROOT / "skills" / "sovetwave" / "scripts" / "select_voice_cards.py"
    spec = importlib.util.spec_from_file_location("sovetwave_voice_selector", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load selector from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def behavioral_cases() -> dict[str, dict[str, Any]]:
    """Resolve IDs through the same loader used by the model-eval runner."""
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    path = ROOT / "scripts" / "run_model_evals.py"
    spec = importlib.util.spec_from_file_location("sovetwave_eval_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load behavioral runner from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {case["id"]: case for case in module.load_cases(module.DEFAULT_CASES)}


def selected_ids(selector: Any, corpus: dict[str, Any], scene: str, domain: str, maximum: int) -> list[str]:
    requested = {"scenes": {scene}, "domains": {domain}, "traits": set()}
    return [card["id"] for card in selector.select(corpus["cards"], requested, maximum)]


def validate_static_map() -> dict[tuple[str, str], list[str]]:
    static = read_json(STATIC_MAP)
    digest = hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    if static.get("source_sha256") != digest:
        raise ValueError("static routing map does not match the current voice-card corpus")
    corpus = read_json(CORPUS)
    known_ids = {card["id"] for card in corpus["cards"]}
    selector = selector_module()
    maximum = static.get("selector_max")
    if not isinstance(maximum, int) or maximum < 0:
        raise ValueError("selector_max must be a non-negative integer")
    mapping: dict[tuple[str, str], list[str]] = {}
    for entry in static.get("canonical_pairs", []):
        pair = (entry.get("scene"), entry.get("domain"))
        if pair in mapping or not all(isinstance(part, str) and part for part in pair):
            raise ValueError(f"invalid or duplicate canonical pair: {pair!r}")
        ids = entry.get("card_ids")
        if not isinstance(ids, list) or len(ids) > maximum or len(set(ids)) != len(ids):
            raise ValueError(f"invalid card_ids for {pair!r}")
        if not set(ids).issubset(known_ids):
            raise ValueError(f"static map contains an unknown card for {pair!r}")
        expected = selected_ids(selector, corpus, pair[0], pair[1], maximum)
        if ids != expected:
            raise ValueError(f"static map differs from selector for {pair!r}: {ids!r} != {expected!r}")
        mapping[pair] = ids
    if not mapping:
        raise ValueError("static routing map has no canonical pairs")
    return mapping


def validate_manifest(manifest: dict[str, Any], mapping: dict[tuple[str, str], list[str]]) -> None:
    arms = manifest.get("arms", [])
    if [arm.get("id") for arm in arms] != ["A", "B", "C"]:
        raise ValueError("arms must be ordered A, B, C")
    pilot = manifest.get("pilot", {})
    if pilot.get("repetitions") != 3 or pilot.get("expected_observations") != 54:
        raise ValueError("pilot must define three repetitions and 54 observations")
    cases = manifest.get("cases", [])
    if len(cases) != 6 or len({case.get("id") for case in cases}) != 6:
        raise ValueError("pilot must contain six unique cases")
    positive = [case for case in cases if case.get("selector_eligible")]
    controls = [case for case in cases if not case.get("selector_eligible")]
    if len(positive) != 4 or len(controls) != 2:
        raise ValueError("pilot must contain four selector-positive cases and two controls")
    case_ids = [case.get("id") for case in cases]
    if pilot.get("case_ids") != case_ids:
        raise ValueError("pilot.case_ids must match the case definitions in order")
    available = behavioral_cases()
    missing = [case_id for case_id in case_ids if case_id not in available]
    if missing:
        raise ValueError(f"pilot references unknown behavioral case: {missing[0]}")
    for case in cases:
        if case["selector_eligible"]:
            pair = (case.get("scene"), case.get("domain"))
            if pair not in mapping:
                raise ValueError(f"positive case has no canonical static pair: {case['id']}")
        elif case.get("scene") is not None or case.get("domain") is not None:
            raise ValueError(f"negative control must not provide selector tags: {case['id']}")


def interleaved_plan(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    cases = manifest["cases"]
    rows: list[dict[str, Any]] = []
    arms = ["A", "B", "C"]
    for repetition in range(1, manifest["pilot"]["repetitions"] + 1):
        for index, case in enumerate(cases):
            rotation = (repetition - 1 + index) % len(arms)
            order = arms[rotation:] + arms[:rotation]
            for sequence, arm in enumerate(order, start=1):
                rows.append({
                    "case_id": case["id"],
                    "case_group": case["group"],
                    "repetition": repetition,
                    "sequence": sequence,
                    "arm": arm,
                    "selector_eligible": case["selector_eligible"],
                    "scene": case["scene"],
                    "domain": case["domain"],
                })
    return rows


def git_provenance(root: Path = ROOT) -> dict[str, object]:
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"], check=True, capture_output=True, text=True).stdout
    return {"root": str(root), "head": head, "dirty": bool(status)}


def build_plan() -> dict[str, Any]:
    manifest = read_json(MANIFEST)
    mapping = validate_static_map()
    validate_manifest(manifest, mapping)
    observations = interleaved_plan(manifest)
    if len(observations) != 54:
        raise ValueError(f"expected 54 observations, got {len(observations)}")
    counts = {arm: sum(row["arm"] == arm for row in observations) for arm in ("A", "B", "C")}
    if counts != {"A": 18, "B": 18, "C": 18}:
        raise ValueError(f"unbalanced arm counts: {counts}")
    return {
        "schema_version": "1.0",
        "experiment_id": manifest["experiment_id"],
        "status": "planned_no_model_runs",
        "manifest": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "static_map": str(STATIC_MAP.relative_to(ROOT)).replace("\\", "/"),
        "provenance": git_provenance(),
        "checkpoint_contract": manifest["provenance"]["requirements"],
        "arm_counts": counts,
        "observations": observations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write the deterministic pilot plan as JSON")
    args = parser.parse_args()
    payload = build_plan()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {len(payload['observations'])} planned observations to {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
