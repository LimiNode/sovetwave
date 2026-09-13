import importlib.util
import subprocess
import tempfile
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

RUNNER = ROOT / "scripts" / "run_voice_card_ablation.py"
runner_spec = importlib.util.spec_from_file_location("run_voice_card_ablation", RUNNER)
assert runner_spec is not None and runner_spec.loader is not None
ablation_runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(ablation_runner)


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
            self.assertFalse(dynamic["selector_invoked"])
            self.assertTrue(dynamic["oracle_selector_invoked"])
            self.assertFalse(static["selector_invoked"])
            self.assertFalse(no_cards["selector_invoked"])
            self.assertIsNone(dynamic["card_payload"])
            self.assertEqual(dynamic["validation_oracle_payload"], static["card_payload"])
            self.assertTrue(static["card_payload"])
            self.assertEqual(no_cards["card_payload"], [])
            self.assertTrue(all(set(card) == {"id", "use", "anchor"} for card in static["card_payload"]))
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
                self.assertFalse(treatment["oracle_selector_invoked"])
                self.assertIsNone(treatment["selector_command"])
                self.assertEqual(treatment["card_payload"], [])
                self.assertEqual(treatment["card_mode"], "disabled")
                self.assertIn("inapplicable", treatment["routing_instruction"])
                prompts.add(treatment["user_prompt"])
            self.assertEqual(len(prompts), 1)

    def test_execution_plan_keeps_a_oracle_out_of_a_input(self) -> None:
        rows = ablation_runner.invocation_plan()
        self.assertEqual(len(rows), 54)
        positive_a = [row for row in rows if row["case_group"] == "selector-positive" and row["arm"] == "A"]
        positive_b = [row for row in rows if row["case_group"] == "selector-positive" and row["arm"] == "B"]
        positive_c = [row for row in rows if row["case_group"] == "selector-positive" and row["arm"] == "C"]
        self.assertEqual(len(positive_a), 12)
        self.assertEqual(len(positive_b), 12)
        self.assertEqual(len(positive_c), 12)
        self.assertTrue(all(not row["card_payload_supplied"] and row["expected_selector_invocations"] == 1 for row in positive_a))
        self.assertTrue(all(row["card_payload_supplied"] and row["expected_selector_invocations"] == 0 for row in positive_b))
        self.assertTrue(all(not row["card_payload_supplied"] and row["expected_selector_invocations"] == 0 for row in positive_c))

    def test_selector_telemetry_counts_one_lifecycle_item(self) -> None:
        stream = "\n".join([
            '{"type":"item.started","item":{"id":"cmd-1","type":"command_execution","command":"py select_voice_cards.py --scene lesson"}}',
            '{"type":"item.updated","item":{"id":"cmd-1","type":"command_execution","command":"py select_voice_cards.py --scene lesson"}}',
            '{"type":"item.completed","item":{"id":"cmd-1","type":"command_execution","command":"py select_voice_cards.py --scene lesson"}}',
        ])
        self.assertEqual(ablation_runner.selector_invocations(stream), 1)

    def test_selector_trace_requires_exact_command_and_command_execution(self) -> None:
        stream = "\n".join([
            '{"type":"item.completed","item":{"id":"read-1","type":"file_read","command":"py select_voice_cards.py --scene review"}}',
            '{"type":"item.completed","item":{"id":"cmd-1","type":"command_execution","command":"python .agents/skills/sovetwave/scripts/select_voice_cards.py --scene review --domain analysis --max 2 --json"}}',
        ])
        checked = ablation_runner.validate_selector_trace(
            stream, expected=1, fixed_tags={"scene": "review", "domain": "analysis"}, oracle_payload=None,
        )
        self.assertTrue(checked["selector_invocation_match"])
        self.assertEqual(checked["recorded_selector_invocations"], 1)

    def test_selector_trace_rejects_wrong_args_duplicate_and_unexpected_control(self) -> None:
        wrong = '{"item":{"id":"cmd-1","type":"command_execution","command":"python select_voice_cards.py --scene review --domain analysis --max 3"}}'
        checked = ablation_runner.validate_selector_trace(
            wrong, expected=1, fixed_tags={"scene": "review", "domain": "analysis"}, oracle_payload=None,
        )
        self.assertFalse(checked["selector_invocation_match"])
        self.assertEqual(checked["selector_trace_status"], "wrong_selector_args")
        duplicate = "\n".join([
            '{"item":{"id":"a","type":"command_execution","command":"python select_voice_cards.py --scene review --domain analysis --max 2 --json"}}',
            '{"item":{"id":"b","type":"command_execution","command":"python select_voice_cards.py --scene review --domain analysis --max 2 --json"}}',
        ])
        self.assertEqual(ablation_runner.selector_invocations(duplicate), 2)
        control = ablation_runner.validate_selector_trace(duplicate, expected=0, fixed_tags=None, oracle_payload=None)
        self.assertFalse(control["selector_invocation_match"])

    def test_selector_trace_compares_exposed_stdout_with_oracle(self) -> None:
        payload = [{"id": "card", "use": "teach", "anchor": "anchor"}]
        stream = '{"item":{"id":"cmd","type":"command_execution","command":"python select_voice_cards.py --scene review --domain analysis --max 2 --json","aggregated_output":"[{\\"id\\":\\"card\\",\\"use\\":\\"teach\\",\\"anchor\\":\\"anchor\\"}]"}}'
        checked = ablation_runner.validate_selector_trace(
            stream, expected=1, fixed_tags={"scene": "review", "domain": "analysis"}, oracle_payload=payload,
        )
        self.assertTrue(checked["selector_invocation_match"])
        self.assertEqual(checked["selector_oracle_equivalence"], "matched")

    def test_dynamic_treatment_instruction_pins_json_command(self) -> None:
        envelope = materializer.materialize("voice-card-selector-teaching-explanation", "A")
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "SKILL.md"
            skill.write_text("kernel\n", encoding="utf-8")
            ablation_runner.append_treatment(skill, envelope)
            rendered = skill.read_text(encoding="utf-8")
        self.assertIn("select_voice_cards.py", rendered)
        self.assertIn("--max 2 --json", rendered)

    def test_timeout_is_a_persistable_first_attempt_failure(self) -> None:
        # Use the real workspace helper while making the model invocation fail
        # before a subprocess can produce a response.
        runner = ablation_runner.load_module("timeout_runner", ROOT / "scripts" / "run_model_evals.py")
        original = runner.execute_command
        runner.execute_command = lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired(args[1] if len(args) > 1 else [], 1))
        try:
            row = next(row for row in ablation_runner.invocation_plan() if row["arm"] == "A" and row["selector_eligible"])
            result = ablation_runner.execute_one(runner, row, "test-model", 1, [], "hash")
        finally:
            runner.execute_command = original
        self.assertEqual(result["process_status"], "timeout")
        self.assertFalse(result["first_attempt_completion"])
        self.assertEqual(result["treatment_status"], "not_observed")

    def test_metadata_identity_binds_provider_configuration(self) -> None:
        manifest = ablation_runner.load_manifest()
        left = ablation_runner.metadata(manifest, "model", "aaa")
        right = ablation_runner.metadata(manifest, "model", "bbb")
        self.assertNotEqual(
            ablation_runner._metadata_identity(left),
            ablation_runner._metadata_identity(right),
        )


if __name__ == "__main__":
    unittest.main()
