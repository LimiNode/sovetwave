#!/usr/bin/env python3
"""Smoke-test deterministic selection for the public voice-card corpus."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "skills" / "sovetwave" / "scripts" / "select_voice_cards.py"


def main() -> int:
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, str(SELECTOR), "--scene", "acceptance", "--domain", "production", "--json"],
        capture_output=True,
        check=True,
        encoding="utf-8",
        env=environment,
    )
    cards = json.loads(result.stdout)
    if not cards or len(cards) > 3:
        raise SystemExit("selector must return one to three relevant cards")
    if not any("acceptance" in card["scenes"] for card in cards):
        raise SystemExit("selector did not return an acceptance card")
    print(f"Voice-card selector returned {len(cards)} card(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
