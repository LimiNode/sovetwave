#!/usr/bin/env python3
"""Test deterministic, low-risk selection for the public voice-card corpus."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "skills" / "sovetwave" / "scripts" / "select_voice_cards.py"
CORPUS = ROOT / "skills" / "sovetwave" / "references" / "voice-cards.json"


def run_selector(*arguments: str, expected_returncode: int = 0) -> list[dict[str, object]]:
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, str(SELECTOR), *arguments, "--json"],
        capture_output=True,
        encoding="utf-8",
        env=environment,
    )
    if result.returncode != expected_returncode:
        raise SystemExit(result.stderr or f"selector exited with {result.returncode}")
    return json.loads(result.stdout) if result.stdout else []


def main() -> int:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    source_refs = corpus["source_refs"]
    if any(not card.get("source_refs") for card in corpus["cards"]):
        raise SystemExit("every voice card must keep provenance references")
    if any(ref not in source_refs for card in corpus["cards"] for ref in card["source_refs"]):
        raise SystemExit("voice-card provenance reference is not registered")
    if any("production" in card["domains"] for card in corpus["cards"]):
        raise SystemExit("use manufacturing or production-ops instead of ambiguous production")
    if any("safety" in card["scenes"] for card in corpus["cards"]):
        raise SystemExit("safety guidance belongs in guard_only, not a voice card")

    cards = run_selector("--scene", "acceptance", "--domain", "manufacturing")
    if not cards or len(cards) > 3:
        raise SystemExit("selector must return one to three matching cards")
    if not all("acceptance" in card["scenes"] and "manufacturing" in card["domains"] for card in cards):
        raise SystemExit("every selected card must match every supplied high-signal tag")
    if len({card["source_group"] for card in cards}) != len(cards):
        raise SystemExit("selector did not diversify source groups when alternatives existed")
    if len({tuple(card["moves"]) for card in cards}) != len(cards):
        raise SystemExit("selector did not diversify moves when alternatives existed")

    repeated = run_selector("--scene", "acceptance", "--domain", "manufacturing")
    if cards != repeated:
        raise SystemExit("selector tie-breaking must be deterministic")
    if run_selector("--scene", "nowhere", "--domain", "nothing") != []:
        raise SystemExit("selector must return [] when no card matches")
    if run_selector("--max", "0", "--scene", "acceptance", "--domain", "manufacturing") != []:
        raise SystemExit("selector must return [] for --max 0")
    if run_selector("--scene", "safety", "--domain", "laboratory") != []:
        raise SystemExit("selector must return [] for blocked safety contexts")
    if run_selector("--scene", "acceptance", "--domain", "production-ops") != []:
        raise SystemExit("production-ops must not match manufacturing cards")
    run_selector("--max", "4", expected_returncode=2)
    print(f"Voice-card selector returned {len(cards)} relevant card(s) deterministically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
