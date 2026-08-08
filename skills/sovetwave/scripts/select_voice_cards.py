#!/usr/bin/env python3
"""Select low-risk Sovetwave voice cards by explicit metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def matches(card: dict[str, object], requested: dict[str, set[str]]) -> bool:
    """Require every supplied high-signal axis to match the candidate."""
    for key in ("scenes", "domains"):
        if requested[key] and not requested[key].intersection(card[key]):
            return False
    if requested["traits"] and not requested["scenes"] and not requested["domains"]:
        return bool(requested["traits"].intersection(card["traits"]))
    return bool(requested["scenes"] or requested["domains"] or requested["traits"])


def select(cards: list[dict[str, object]], requested: dict[str, set[str]], maximum: int) -> list[dict[str, object]]:
    ranked: list[tuple[int, dict[str, object]]] = []
    for card in cards:
        if not matches(card, requested):
            continue
        score = sum(3 * len(requested[key].intersection(card[key])) for key in ("scenes", "domains"))
        score += len(requested["traits"].intersection(card["traits"]))
        ranked.append((score, card))

    candidates = [card for _, card in sorted(ranked, key=lambda item: (-item[0], item[1]["id"]))]
    selected: list[dict[str, object]] = []
    used_sources: set[str] = set()
    used_moves: set[str] = set()
    while candidates and len(selected) < maximum:
        candidate = next(
            (
                card
                for card in candidates
                if card["source_group"] not in used_sources and not set(card["moves"]).intersection(used_moves)
            ),
            candidates[0],
        )
        candidates.remove(candidate)
        selected.append(candidate)
        used_sources.add(candidate["source_group"])
        used_moves.update(candidate["moves"])
    return selected


def vocabulary(corpus: dict[str, object]) -> dict[str, list[str]]:
    cards = corpus["cards"]
    return {
        "scenes": sorted({tag for card in cards for tag in card["scenes"]}),
        "domains": sorted({tag for card in cards for tag in card["domains"]}),
        "traits": sorted({tag for card in cards for tag in card["traits"]}),
        "blocked_contexts": sorted(corpus["blocked_contexts"]),
    }


def reject_unknown(parser: argparse.ArgumentParser, label: str, supplied: set[str], known: set[str]) -> None:
    unknown = sorted(supplied - known)
    if unknown:
        parser.error(f"unknown {label}: {', '.join(unknown)}; known {label}s: {', '.join(sorted(known))}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", action="append", default=[])
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--trait", action="append", default=[])
    parser.add_argument("--max", type=int, default=3)
    parser.add_argument("--list-tags", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.max < 0 or args.max > 3:
        parser.error("--max must be between 0 and 3")

    cards_path = Path(__file__).parents[1] / "references" / "voice-cards.json"
    corpus = json.loads(cards_path.read_text(encoding="utf-8"))
    known = vocabulary(corpus)
    if args.list_tags:
        if args.scene or args.domain or args.trait:
            parser.error("--list-tags cannot be combined with --scene, --domain, or --trait")
        if args.json:
            print(json.dumps(known, ensure_ascii=False, indent=2))
        else:
            for label, values in known.items():
                print(f"{label}: {', '.join(values)}")
        return 0

    requested = {
        "scenes": set(args.scene),
        "domains": set(args.domain),
        "traits": set(args.trait),
    }
    if not any(requested.values()):
        parser.error("provide at least one --scene, --domain, or --trait; use --list-tags to inspect the vocabulary")
    reject_unknown(parser, "scene", requested["scenes"], set(known["scenes"]) | set(known["blocked_contexts"]))
    reject_unknown(parser, "domain", requested["domains"], set(known["domains"]) | set(known["blocked_contexts"]))
    reject_unknown(parser, "trait", requested["traits"], set(known["traits"]))
    blocked = set(corpus["blocked_contexts"])
    if blocked.intersection(requested["scenes"] | requested["domains"]):
        selected: list[dict[str, object]] = []
    else:
        selected = select(corpus["cards"], requested, args.max)

    if args.json:
        print(json.dumps(selected, ensure_ascii=False, indent=2))
    else:
        for card in selected:
            print(f"- {card['id']} [{card['use']}]: {card['anchor']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
