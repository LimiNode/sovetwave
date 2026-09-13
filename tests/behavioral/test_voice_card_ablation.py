import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "plan_voice_card_ablation.py"
spec = importlib.util.spec_from_file_location("plan_voice_card_ablation", SCRIPT)
assert spec is not None and spec.loader is not None
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)

MATERIALIZER = ROOT / "scripts" / "materialize_voice_card_arms.py"
materializer_spec = importlib.util.spec_from_file_location("materialize_voice_card_arms", MATERIALIZER)
assert materializer_spec is not None and materializer_spec.loader is not None
materializer = importlib.util.module_from_spec(materializer_spec)
materializer_spec.loader.exec_module(materializer)


class VoiceCardAblationTests(unittest.TestCase):
    def test_static_map_is_equivalent_for_preregistered_pairs(self) -> None:
        mapping = planner.validate_static_map()
        self.assertEqual(len(mapping), 4)
        self.assertEqual(
            [card["id"] for card in mapping[("review", "analysis")]],
            ["kvant-model-and-measurement", "physics-folklore-requirement"],
        )

    def test_pilot_has_balanced_latin_order(self) -> None:
        payload = planner.build_plan()
        rows = payload["observations"]
        self.assertEqual(payload["status"], "planned_no_model_runs")
        self.assertEqual(len(rows), 54)
        self.assertEqual(payload["arm_counts"], {"A": 18, "B": 18, "C": 18})
        for repetition in range(1, 4):
            for index, case in enumerate(planner.read_json(planner.MANIFEST)["cases"]):
                selected = [row["arm"] for row in rows if row["repetition"] == repetition and row["case_id"] == case["id"]]
                expected = ["A", "B", "C"]
                rotation = (repetition - 1 + index) % 3
                expected = expected[rotation:] + expected[:rotation]
                self.assertEqual(selected, expected)

    def test_case_groups_and_controls_are_explicit(self) -> None:
        cases = planner.read_json(planner.MANIFEST)["cases"]
        self.assertEqual(sum(case["selector_eligible"] for case in cases), 4)
        self.assertEqual(sum(not case["selector_eligible"] for case in cases), 2)
        self.assertTrue(all(case["scene"] and case["domain"] for case in cases if case["selector_eligible"]))
        self.assertTrue(all(case["scene"] is None and case["domain"] is None for case in cases if not case["selector_eligible"]))

    def test_planner_does_not_run_models(self) -> None:
        manifest = planner.read_json(planner.MANIFEST)
        self.assertEqual(manifest["status"], "design_only")
        self.assertEqual(manifest["provenance"]["model_runs"], "not_started")

    def test_unknown_case_id_fails_closed_through_behavioral_loader(self) -> None:
        manifest = planner.read_json(planner.MANIFEST)
        manifest["cases"][0] = dict(manifest["cases"][0], id="case-that-does-not-exist")
        manifest["pilot"] = dict(manifest["pilot"], case_ids=[case["id"] for case in manifest["cases"]])
        with self.assertRaisesRegex(ValueError, "unknown behavioral case"):
            planner.validate_manifest(manifest, planner.validate_static_map())

    def test_positive_effective_treatments_are_fixed_and_isolated(self) -> None:
        manifest = planner.read_json(planner.MANIFEST)
        positives = [case for case in manifest["cases"] if case["selector_eligible"]]
        for case in positives:
            dynamic = materializer.materialize(case["id"], "A")
            static = materializer.materialize(case["id"], "B")
            no_cards = materializer.materialize(case["id"], "C")
            self.assertTrue(dynamic["selector_invoked"])
            self.assertFalse(static["selector_invoked"])
            self.assertFalse(no_cards["selector_invoked"])
            self.assertEqual(dynamic["card_payload"], static["card_payload"])
            self.assertTrue(dynamic["card_payload"])
            self.assertEqual(no_cards["card_payload"], [])
            self.assertTrue(all(set(card) == {"id", "use", "anchor"} for card in dynamic["card_payload"]))
            self.assertEqual(dynamic["fixed_tags"], {"scene": case["scene"], "domain": case["domain"]})
            self.assertIn(case["scene"], dynamic["selector_command"])
            self.assertIn(case["domain"], dynamic["selector_command"])
            self.assertNotIn("--list-tags", dynamic["selector_command"])
            self.assertIn("fixed preregistered tags", dynamic["routing_instruction"])
            self.assertIn("Do not invoke", static["routing_instruction"])
            self.assertIn("cards are disabled", no_cards["routing_instruction"])
            self.assertEqual(dynamic["user_prompt"], static["user_prompt"])
            self.assertEqual(static["user_prompt"], no_cards["user_prompt"])

    def test_controls_have_no_selector_or_cards_in_any_arm(self) -> None:
        manifest = planner.read_json(planner.MANIFEST)
        controls = [case for case in manifest["cases"] if not case["selector_eligible"]]
        for case in controls:
            prompts = set()
            for arm in ("A", "B", "C"):
                treatment = materializer.materialize(case["id"], arm)
                self.assertFalse(treatment["selector_invoked"])
                self.assertIsNone(treatment["selector_command"])
                self.assertEqual(treatment["card_payload"], [])
                self.assertEqual(treatment["card_mode"], "disabled")
                self.assertIn("inapplicable", treatment["routing_instruction"])
                prompts.add(treatment["user_prompt"])
            self.assertEqual(len(prompts), 1)


if __name__ == "__main__":
    unittest.main()
