#!/usr/bin/env python3
"""Materialize the three voice-card treatments without running a model.

The returned envelope is the effective context a future runner must provide to
the agent.  A invokes the current selector with preregistered tags, B uses the
committed equivalent payload, and C disables cards.  User prompts are kept
separate from treatment metadata so the arm is not disclosed to the model.
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
SELECTOR = ROOT / "skills" / "sovetwave" / "scripts" / "select_voice_cards.py"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cases() -> dict[str, dict[str, Any]]:
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    path = ROOT / "scripts" / "run_model_evals.py"
    spec = importlib.util.spec_from_file_location("voice_ablation_eval_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load behavioral runner from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {case["id"]: case for case in module.load_cases(module.DEFAULT_CASES)}


def card_payload(cards: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{key: card[key] for key in ("id", "use", "anchor")} for card in cards]


def static_payload(scene: str, domain: str) -> list[dict[str, str]]:
    planner = load_planner()
    mapping = planner.validate_static_map()
    if (scene, domain) in mapping:
        return [dict(card) for card in mapping[(scene, domain)]]
    raise ValueError(f"no static routing entry for {(scene, domain)!r}")


def load_planner() -> Any:
    path = ROOT / "scripts" / "plan_voice_card_ablation.py"
    spec = importlib.util.spec_from_file_location("voice_card_ablation_planner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load planner from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dynamic_payload(scene: str, domain: str) -> tuple[list[dict[str, str]], list[str]]:
    command = [sys.executable, str(SELECTOR), "--scene", scene, "--domain", domain, "--max", "2", "--json"]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return card_payload(json.loads(completed.stdout)), command


def materialize(case_id: str, arm: str) -> dict[str, Any]:
    manifest = read_json(MANIFEST)
    cases = {case["id"]: case for case in manifest["cases"]}
    if case_id not in cases:
        raise ValueError(f"unknown pilot case: {case_id}")
    if arm not in {"A", "B", "C"}:
        raise ValueError(f"unknown arm: {arm}")
    case = cases[case_id]
    behavioral = load_cases()
    if case_id not in behavioral:
        raise ValueError(f"unknown behavioral case: {case_id}")

    eligible = case["selector_eligible"]
    scene, domain = case.get("scene"), case.get("domain")
    selector_invoked = False
    oracle_selector_invoked = False
    selector_command: list[str] | None = None
    payload: list[dict[str, str]] | None = []
    oracle_payload: list[dict[str, str]] | None = None
    mode = "disabled"
    routing_instruction = "Voice-card selection is inapplicable. Do not inspect tags, invoke the selector, or load cards."
    if eligible and arm == "A":
        if not scene or not domain:
            raise ValueError(f"selector-positive case has no fixed tags: {case_id}")
        oracle_payload, selector_command = dynamic_payload(scene, domain)
        oracle_selector_invoked = True
        payload = None
        mode = "runtime_selector"
        routing_instruction = (
            f"Use the fixed preregistered tags scene={scene!r}, domain={domain!r}. "
            "Do not infer replacement tags or run --list-tags. Invoke exactly this command once: "
            f"py -3 .agents/skills/sovetwave/scripts/select_voice_cards.py --scene {scene} --domain {domain} --max 2 --json. "
            "Use only the ordered id/use/anchor payload it returns."
        )
    elif eligible and arm == "B":
        if not scene or not domain:
            raise ValueError(f"selector-positive case has no fixed tags: {case_id}")
        payload = static_payload(scene, domain)
        mode = "static_payload"
        routing_instruction = (
            f"Use the fixed preregistered tags scene={scene!r}, domain={domain!r}. "
            "Do not invoke --list-tags or select_voice_cards.py. Use only the supplied ordered id/use/anchor payload."
        )
    elif eligible and arm == "C":
        routing_instruction = (
            f"Keep the fixed preregistered tags scene={scene!r}, domain={domain!r} as experiment metadata only. "
            "Voice cards are disabled: do not invoke --list-tags or select_voice_cards.py and do not load card data."
        )

    return {
        "case_id": case_id,
        "arm": arm,
        "user_prompt": behavioral[case_id]["prompt"],
        "fixed_tags": {"scene": scene, "domain": domain} if eligible else None,
        "tag_source": "preregistered" if eligible else "inapplicable",
        "tag_inference_measured": False,
        "list_tags_discovery_measured": False,
        "selector_invoked": selector_invoked,
        "oracle_selector_invoked": oracle_selector_invoked,
        "selector_command": selector_command,
        "card_mode": mode,
        "card_payload": payload,
        "validation_oracle_payload": oracle_payload,
        "routing_instruction": routing_instruction,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--arm", choices=("A", "B", "C"), required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    envelope = materialize(args.case_id, args.arm)
    print(json.dumps(envelope, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
