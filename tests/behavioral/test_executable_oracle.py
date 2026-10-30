import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "executable-oracle"))

import oracle  # noqa: E402


class ExecutableOracleTests(unittest.TestCase):
    def test_trusted_reference_passes_and_defects_fail(self) -> None:
        report = oracle.selftest()
        self.assertEqual(report["execution_mode"], "trusted_reference_implementations_only")
        self.assertEqual(report["model_calls"], 0)
        self.assertFalse(report["generated_code_executed"])
        self.assertTrue(report["source_identity"]["verified"])
        self.assertEqual(report["results"]["correct_reference"]["status"], "pass")
        for name in ("accepts_duplicates", "accepts_unknown", "rejects_optional_none"):
            self.assertEqual(report["results"][name]["status"], "reject")

    def test_oracle_reports_each_required_case_group(self) -> None:
        report = oracle.run_oracle()
        expected_groups = {"optional", "normal", "boundary", "rejection"}
        result = report["results"]["correct_reference"]
        self.assertTrue(result["completeness_pass"])
        self.assertEqual({case["group"] for case in result["case_results"]}, expected_groups)
        self.assertEqual(result["cases_executed"], 7)

    def test_defect_is_localised_to_duplicate_invariant(self) -> None:
        report = oracle.run_oracle()
        result = report["results"]["accepts_duplicates"]
        failures = {case["case_id"] for case in result["case_results"] if not case["passed"]}
        self.assertEqual(failures, {"duplicate-axis"})

    def test_provenance_corruption_is_rejected(self) -> None:
        base = oracle.load_task()
        mutations = {
            "hash": lambda value: value["repository_target"].update(source_sha256="0" * 64),
            "marker": lambda value: value["repository_target"].update(required_marker="def missing_marker("),
            "revision": lambda value: value.update(repository_revision="0" * 40),
            "target": lambda value: value["repository_target"].update(path="../outside.py"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                task = copy.deepcopy(base)
                mutate(task)
                identity = oracle._pinned_source_identity(task)
                self.assertFalse(identity["verified"])
                self.assertTrue(identity["errors"])


if __name__ == "__main__":
    unittest.main()
