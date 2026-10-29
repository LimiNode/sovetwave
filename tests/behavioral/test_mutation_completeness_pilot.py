import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from mutation_completeness_pilot import (  # noqa: E402
    STATUS_INVALID,
    STATUS_KILLED,
    STATUS_NOT_EXECUTED,
    build_report,
    contract_hash,
    selftest,
)


class MutationCompletenessPilotTests(unittest.TestCase):
    def test_references_calibrate_good_and_bad_outputs(self) -> None:
        report = selftest()
        statuses = {item["candidate"]: item["status"] for item in report["reference_results"]}
        self.assertEqual(statuses["good"], "pass")
        self.assertEqual(statuses["incomplete"], "reject")
        self.assertEqual(statuses["contract_violation"], "reject")
        self.assertEqual(statuses["unsafe"], "reject")

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
        self.assertIn("isolation", results["untrusted-generated-code"]["reason"])

    def test_experiment_arms_share_contract_but_have_no_results(self) -> None:
        report = build_report()
        manifest = report["experiment_manifest"]
        self.assertEqual(manifest["task_contract_sha256"], contract_hash())
        self.assertEqual({arm["status"] for arm in manifest["arms"]}, {"planned"})
        self.assertEqual(manifest["controls"]["task_contract"], "identical across arms")


if __name__ == "__main__":
    unittest.main()
