#!/usr/bin/env python3
"""Test deterministic, low-risk selection for the public voice-card corpus."""

from __future__ import annotations

import json
import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "skills" / "sovetwave" / "scripts" / "select_voice_cards.py"
CORPUS = ROOT / "skills" / "sovetwave" / "references" / "voice-cards.json"
STATIC_ROUTING = ROOT / "skills" / "sovetwave" / "references" / "voice-card-routing.json"
SOURCE_REGISTRY = ROOT / "research" / "sources.md"


def run_selector(*arguments: str, expected_returncode: int = 0) -> object:
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


def assert_selector_error(*arguments: str, fragment: str) -> None:
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, str(SELECTOR), *arguments, "--json"],
        capture_output=True,
        encoding="utf-8",
        env=environment,
    )
    if result.returncode != 2 or fragment not in result.stderr:
        raise SystemExit(result.stderr or "selector did not report the expected error")


def main() -> int:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    routing = json.loads(STATIC_ROUTING.read_text(encoding="utf-8"))
    if routing.get("source_sha256") != hashlib.sha256(CORPUS.read_bytes()).hexdigest():
        raise SystemExit("static routing source hash does not match voice-card corpus")
    card_ids = {card["id"] for card in corpus["cards"]}
    tags = run_selector("--list-tags")
    selector_spec = importlib.util.spec_from_file_location("voice_card_selector", SELECTOR)
    if selector_spec is None or selector_spec.loader is None:
        raise SystemExit("cannot load selector implementation for routing coverage validation")
    selector_module = importlib.util.module_from_spec(selector_spec)
    selector_spec.loader.exec_module(selector_module)
    expected_routing = {}
    for scene in tags["scenes"]:
        for domain in tags["domains"]:
            ids = [
                card["id"]
                for card in selector_module.select(
                    corpus["cards"], {"scenes": {scene}, "domains": {domain}, "traits": set()}, 2
                )
            ]
            if ids:
                expected_routing[(scene, domain)] = ids
    seen_pairs = set()
    for pair in routing.get("canonical_pairs", []):
        key = (pair.get("scene"), pair.get("domain"))
        if key in seen_pairs:
            raise SystemExit(f"duplicate static routing pair: {key}")
        seen_pairs.add(key)
        expected_ids = pair.get("card_ids")
        if not isinstance(expected_ids, list) or not expected_ids or not set(expected_ids) <= card_ids:
            raise SystemExit(f"static routing has invalid card IDs: {key}")
        selected_ids = [card["id"] for card in run_selector("--scene", key[0], "--domain", key[1], "--max", "2")]
        if selected_ids != expected_ids:
            raise SystemExit(f"static routing differs from selector for {key}: {expected_ids} != {selected_ids}")
    actual_routing = {(pair["scene"], pair["domain"]): pair["card_ids"] for pair in routing.get("canonical_pairs", [])}
    if actual_routing != expected_routing:
        raise SystemExit("static routing does not exactly cover the selector scene/domain cross-product")
    source_refs = corpus["source_refs"]
    source_registry = SOURCE_REGISTRY.read_text(encoding="utf-8")
    if any(not card.get("source_refs") for card in corpus["cards"]):
        raise SystemExit("every voice card must keep provenance references")
    if any(ref not in source_refs for card in corpus["cards"] for ref in card["source_refs"]):
        raise SystemExit("voice-card provenance reference is not registered")
    for reference in source_refs.values():
        if reference.startswith("research/sources.md: ") and reference.removeprefix("research/sources.md: ") not in source_registry:
            raise SystemExit(f"voice-card provenance is absent from the source registry: {reference}")
    if any("production" in card["domains"] for card in corpus["cards"]):
        raise SystemExit("use manufacturing or production-ops instead of ambiguous production")
    if any("safety" in card["scenes"] for card in corpus["cards"]):
        raise SystemExit("safety guidance belongs in guard_metadata, not a voice card")
    for card in corpus["cards"]:
        if "source_example" in card:
            if card.get("source_example_policy") == "attributed_unverified_style_example":
                if not card.get("claimed_attribution") or card.get("output_attribution") is not False:
                    raise SystemExit("unverified short examples must keep attribution provenance and suppress output attribution")

    tags = run_selector("--list-tags")
    if not isinstance(tags, dict) or {"scenes", "domains", "traits", "blocked_contexts"} != set(tags):
        raise SystemExit("--list-tags must return the complete tag vocabulary")
    if "review" not in tags["scenes"] or "programming" not in tags["domains"]:
        raise SystemExit("--list-tags omitted a canonical review/programming tag")

    cards = run_selector("--scene", "acceptance", "--domain", "manufacturing")
    if not isinstance(cards, list):
        raise SystemExit("selector must return a card list")
    if not cards or len(cards) > 2:
        raise SystemExit("selector must return one to two matching cards by default")
    if not all("acceptance" in card["scenes"] and "manufacturing" in card["domains"] for card in cards):
        raise SystemExit("every selected card must match every supplied high-signal tag")
    if len({card["source_group"] for card in cards}) != len(cards):
        raise SystemExit("selector did not diversify source groups when alternatives existed")
    if len({tuple(card["moves"]) for card in cards}) != len(cards):
        raise SystemExit("selector did not diversify moves when alternatives existed")

    strong_cards = run_selector("--scene", "acceptance", "--domain", "manufacturing", "--max", "3")
    if len(strong_cards) != 3:
        raise SystemExit("explicit --max 3 must retain the stronger-calibration option")

    service_cards = run_selector("--scene", "integration", "--domain", "systems", "--max", "2")
    if not service_cards or any("integration" not in card["scenes"] or "systems" not in card["domains"] for card in service_cards):
        raise SystemExit("service-boundary selection must use integration + systems cards")
    if any(card["id"] == "radio-propagation-context" for card in service_cards):
        raise SystemExit("service-boundary selection must not use the radio-propagation card")

    repeated = run_selector("--scene", "acceptance", "--domain", "manufacturing")
    if cards != repeated:
        raise SystemExit("selector tie-breaking must be deterministic")
    assert_selector_error("--scene", "nowhere", "--domain", "nothing", fragment="unknown scene")
    assert_selector_error("--scene", "code_review", "--domain", "cpp", fragment="unknown scene")
    assert_selector_error(fragment="provide at least one")
    assert_selector_error("--trait", "nonexistent", fragment="unknown trait")
    trait_cards = run_selector("--trait", "dry")
    if not trait_cards or not all("dry" in card["traits"] for card in trait_cards):
        raise SystemExit("trait-only selection must return only matching cards")
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
