import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCORER = ROOT / "scripts" / "score_voice_card_ablation.py"
spec = importlib.util.spec_from_file_location("score_voice_card_ablation", SCORER)
assert spec is not None and spec.loader is not None
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def pilot_payload() -> dict:
    manifest = json.loads((ROOT / "evals/experiments/voice-card-selector-ablation.json").read_text(encoding="utf-8"))
    rows = []
    for repetition in range(1, manifest["pilot"]["repetitions"] + 1):
        for index, case in enumerate(manifest["cases"]):
            rotation = (repetition - 1 + index) % 3
            for sequence, arm in enumerate(("A", "B", "C")[rotation:] + ("A", "B", "C")[:rotation], 1):
                rows.append({
                    "case_id": case["id"], "arm": arm, "repetition": repetition,
                    "sequence": sequence, "process_status": "completed",
                    "first_attempt_completion": True, "treatment_status": "valid",
                    "causal_eligible": True, "codex_usage_status": "valid",
                    "codex_usage": {"input_tokens": 10, "cached_input_tokens": 2},
                })
    return {"experiment_id": manifest["experiment_id"], "observations": rows}


def test_full_pilot_has_18_complete_paired_groups() -> None:
    packet = scorer.build_packet(pilot_payload())
    assert packet["operational_summary"]["unique_paired_keys"] == 18
    groups = {}
    for row in packet["observations"]:
        groups.setdefault((row["case_id"], row["repetition"]), []).append(row["arm"])
    assert len(groups) == 18
    assert all(sorted(arms) == ["A", "B", "C"] for arms in groups.values())


def test_canonical_content_is_restored_when_raw_row_omits_it() -> None:
    packet = scorer.build_packet(pilot_payload())
    positive = next(row for row in packet["observations"] if row["case_id"] == "russian-rag-capacity-analysis")
    assert positive["assertions"]
    assert positive["applicable_axes"]
    assert positive["case_group"] == "selector-positive"
    assert positive["selector_eligible"] is True
    cpp = next(row for row in packet["observations"] if row["case_id"] == "cpp-architecture-event-flow")
    assert cpp["applicable_axes"] is None
    assert cpp["voice_language_axes"]


def test_prompt_mismatch_fails_closed() -> None:
    payload = pilot_payload()
    payload["observations"][0]["prompt"] = "tampered prompt"
    with pytest.raises(ValueError, match="prompt mismatch"):
        scorer.build_packet(payload)


def test_packet_snapshots_manifest_gates() -> None:
    packet = scorer.build_packet(pilot_payload())
    manifest = json.loads((ROOT / "evals/experiments/voice-card-selector-ablation.json").read_text(encoding="utf-8"))
    assert packet["preregistered"]["metrics"] == manifest["metrics"]
    assert packet["preregistered"]["decision_criteria"] == manifest["decision_criteria"]


def test_packet_contains_canonical_rubric_and_hashes() -> None:
    packet = scorer.build_packet(pilot_payload())
    rubric = json.loads((ROOT / "evals/behavioral/rubric.json").read_text(encoding="utf-8"))
    assert packet["preregistered"]["canonical_rubric"] == rubric
    assert packet["rubric_sha256"]
    assert packet["source_sha256"] is None
    voice = packet["preregistered"]["voice_language_scoring"]
    assert voice["scale_min"] == 0 and voice["scale_max"] == 4
    assert voice["positive_case_denominator"] == 12
    assert "None means" in voice["none_applicable_axes"]


def test_timeout_is_censored_and_renderer_does_not_score_it() -> None:
    payload = pilot_payload()
    timeout_row = payload["observations"][0]
    timeout_row["process_status"] = "timeout"
    packet = scorer.build_packet(payload)
    row = packet["observations"][0]
    assert row["semantic_status"] == "censored"
    assert row["semantic_outcome"] == "not_observed"
    markdown = scorer.render_markdown(packet)
    assert "censored (timeout; semantic outcome not observed)" in markdown
    assert "semantic fields are intentionally not scored" in markdown
