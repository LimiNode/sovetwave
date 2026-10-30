import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from mutation_completeness_pilot import (  # noqa: E402
    STATUS_INVALID,
    STATUS_KILLED,
    STATUS_NOT_EXECUTED,
    STATUS_SURVIVED,
    STATUS_TOLERATED,
    build_report,
    contract_hash,
    evaluate_candidate,
    reference_candidates,
    selftest,
)


class MutationCompletenessPilotTests(unittest.TestCase):
    def test_references_calibrate_good_and_bad_outputs(self) -> None:
        report = selftest()
        statuses = {item["candidate"]: item["status"] for item in report["reference_results"]}
        self.assertEqual(statuses["good"], "pass")
        self.assertEqual(statuses["incomplete"], "reject")
        self.assertEqual(statuses["contract_violation"], "reject")
        self.assertEqual(statuses["success_error_code"], "reject")
        self.assertEqual(statuses["unsafe"], "reject")

    def test_completeness_dimensions_follow_the_failed_property(self) -> None:
        report = build_report()
        evaluations = {
            item["mutation_id"]: item["evaluation"]
            for item in report["mutation_results"]
            if "evaluation" in item
        }
        expected = {
            "missing-boundary-check": {
                "requirements_complete": False,
                "public_contract_preserved": True,
                "negative_scenarios": True,
            },
            "incorrect-identifier-mapping": {
                "requirements_complete": False,
                "public_contract_preserved": True,
                "negative_scenarios": True,
            },
            "incorrect-error-handling": {
                "requirements_complete": True,
                "public_contract_preserved": True,
                "negative_scenarios": False,
            },
            "missing-required-output": {
                "requirements_complete": False,
                "public_contract_preserved": True,
                "negative_scenarios": False,
            },
            "removed-security-check": {
                "requirements_complete": True,
                "public_contract_preserved": True,
                "negative_scenarios": False,
                "security_checks_preserved": False,
            },
        }
        for mutation_id, dimensions in expected.items():
            with self.subTest(mutation_id=mutation_id):
                self.assertEqual(
                    {key: evaluations[mutation_id]["completeness"][key] for key in dimensions},
                    dimensions,
                )

        success_error = evaluate_candidate(reference_candidates()["success_error_code"])
        self.assertEqual(success_error["status"], "reject")
        self.assertFalse(success_error["completeness"]["public_contract_preserved"])
        self.assertTrue(any("error_code=None" in finding["message"] for finding in success_error["findings"]))

    def test_mutation_statuses_are_distinct_and_explainable(self) -> None:
        report = build_report()
        results = {item["mutation_id"]: item for item in report["mutation_results"]}
        for mutation_id in (
            "missing-boundary-check",
            "incorrect-error-handling",
            "incorrect-identifier-mapping",
            "missing-required-output",
            "removed-security-check",
        ):
            self.assertEqual(results[mutation_id]["status"], STATUS_KILLED)
        self.assertEqual(results["equivalent-no-op"]["status"], STATUS_INVALID)
        self.assertEqual(results["untrusted-generated-code"]["status"], STATUS_NOT_EXECUTED)
        self.assertEqual(results["unobserved-extra-output"]["status"], STATUS_TOLERATED)
        self.assertEqual(results["unobserved-wrong-rejection-path"]["status"], STATUS_SURVIVED)
        self.assertEqual(results["unrelated-rejection"]["status"], STATUS_SURVIVED)
        self.assertIn("not for the targeted property", results["unrelated-rejection"]["reason"])
        self.assertEqual(results["malformed-fixture"]["status"], STATUS_INVALID)
        self.assertIn("isolation", results["untrusted-generated-code"]["reason"])

    def test_experiment_arms_share_contract_but_have_no_results(self) -> None:
        report = build_report()
        manifest = report["experiment_manifest"]
        self.assertEqual(manifest["task_contract_sha256"], contract_hash())
        self.assertEqual({arm["status"] for arm in manifest["arms"]}, {"planned"})
        self.assertEqual(manifest["controls"]["task_contract"], "identical across arms")


if __name__ == "__main__":
    unittest.main()
