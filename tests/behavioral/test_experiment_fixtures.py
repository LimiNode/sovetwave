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
        candidate["helper"] = "local_safe_reference_path"
        result = fixtures.grade_reuse(fixture, candidate)
        self.assertEqual(result["status"], "reject")

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


if __name__ == "__main__":
    unittest.main()
