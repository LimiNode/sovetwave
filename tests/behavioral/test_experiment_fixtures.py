import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_experiment_fixtures as fixtures  # noqa: E402


class ExperimentFixtureTests(unittest.TestCase):
    def test_trusted_candidates_have_independent_grades(self) -> None:
        report = fixtures.selftest()
        self.assertEqual(report["execution_mode"], fixtures.EXECUTION_MODE)
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(report["results"]["contract"]["good"]["status"], "pass")
        self.assertEqual(report["results"]["contract"]["incomplete"]["status"], "reject")
        self.assertEqual(report["results"]["reuse"]["reuse"]["status"], "pass")
        self.assertEqual(report["results"]["reuse"]["reinvent"]["status"], "reject")
        self.assertEqual(report["results"]["security"]["blocked"]["status"], "pass")
        self.assertEqual(report["results"]["security"]["unsafe"]["status"], "reject")

    def test_contract_grader_rejects_missing_required_output(self) -> None:
        fixture = fixtures.load_fixture("contract")
        candidate = copy.deepcopy(fixture["candidates"]["good"])
        candidate.pop("reference_trace_status")
        result = fixtures.grade_contract(fixture, candidate)
        self.assertEqual(result["status"], "reject")
        self.assertIn("reference_trace_status", " ".join(result["findings"]))

    def test_reuse_grader_rejects_new_local_helper(self) -> None:
        fixture = fixtures.load_fixture("reuse")
        candidate = copy.deepcopy(fixture["candidates"]["reuse"])
        candidate.update({"route": "new_local_validator", "module": None, "helper": "validate_axes_locally", "new_helper": True})
        result = fixtures.grade_reuse(fixture, candidate)
        self.assertEqual(result["status"], "reject")

    def test_reuse_helper_is_module_level_and_callable(self) -> None:
        fixture = fixtures.load_fixture("reuse")
        result = fixtures.grade_reuse(fixture, fixture["candidates"]["reuse"])
        self.assertEqual(result["status"], "pass")
        self.assertEqual(fixture["contract"]["helper_owner"], "scripts/eval_schema.py::validate_applicable_axes")
        self.assertEqual(fixture["contract"]["visibility"], "module_level_importable")
        self.assertIn("imported and probed", result["evidence_boundary"])
        self.assertFalse(result["agent_execution_observed"])

    def test_security_grader_rejects_any_side_effect(self) -> None:
        fixture = fixtures.load_fixture("security")
        candidate = copy.deepcopy(fixture["candidates"]["blocked"])
        candidate["side_effects"] = ["read_outside_fixture_root"]
        result = fixtures.grade_security(fixture, candidate)
        self.assertEqual(result["status"], "reject")
        self.assertIn("side effects", " ".join(result["findings"]))

    def test_generated_code_is_not_an_execution_input(self) -> None:
        self.assertEqual(fixtures.EXECUTION_MODE, "offline_structured_fixtures_only")
        self.assertFalse(any("generated" in str(path).lower() for path in fixtures.FIXTURE_FILES.values()))

    def test_source_marker_hash_revision_and_target_are_fail_closed(self) -> None:
        base = fixtures.load_fixture("contract")
        mutations = {
            "marker": lambda value: value["repository_targets"][0].update(required_marker="def missing_marker("),
            "hash": lambda value: value["repository_targets"][0].update(source_sha256="0" * 64),
            "revision": lambda value: value.update(repository_revision="0" * 40),
            "target": lambda value: value["repository_targets"][0].update(path="scripts/missing_target.py"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                fixture = copy.deepcopy(base)
                mutate(fixture)
                result = fixtures.grade_contract(fixture, fixture["candidates"]["good"])
                self.assertEqual(result["status"], "reject")
                self.assertTrue(result["findings"])

    def test_malformed_candidate_is_controlled_rejection(self) -> None:
        graders = {
            "contract": fixtures.grade_contract,
            "reuse": fixtures.grade_reuse,
            "security": fixtures.grade_security,
        }
        for kind, grader in graders.items():
            with self.subTest(kind=kind):
                result = grader(fixtures.load_fixture(kind), ["not", "an", "object"])
                self.assertEqual(result["status"], "reject")
                self.assertIn("candidate must be an object", result["findings"])

    def test_security_pass_is_structured_fixture_evidence_only(self) -> None:
        fixture = fixtures.load_fixture("security")
        result = fixtures.grade_security(fixture, fixture["candidates"]["blocked"])
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["agent_execution_observed"])
        self.assertIn("no host guard", result["evidence_boundary"])


if __name__ == "__main__":
    unittest.main()
