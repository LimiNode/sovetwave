#!/usr/bin/env python3
"""Select Sovetwave voice cards by explicit scene and domain metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", action="append", default=[])
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--trait", action="append", default=[])
    parser.add_argument("--max", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.max < 0 or args.max > 3:
        parser.error("--max must be between 0 and 3")

    cards_path = Path(__file__).parents[1] / "references" / "voice-cards.json"
    cards = json.loads(cards_path.read_text(encoding="utf-8"))["cards"]
    requested = {
        "scenes": set(args.scene),
        "domains": set(args.domain),
        "traits": set(args.trait),
    }

    ranked = []
    for card in cards:
        score = sum(3 * len(requested[key].intersection(card[key])) for key in ("scenes", "domains"))
        score += len(requested["traits"].intersection(card["traits"]))
        if score:
            ranked.append((score, card))
    selected = [card for _, card in sorted(ranked, key=lambda item: (-item[0], item[1]["id"]))[: args.max]]

    if args.json:
        print(json.dumps(selected, ensure_ascii=False, indent=2))
    else:
        for card in selected:
            print(f"- {card['id']} [{card['use']}]: {card['anchor']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
