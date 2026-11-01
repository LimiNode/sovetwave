import copy
import subprocess
import sys
import tempfile
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
        self.assertEqual(
            report["task_contract"]["repository_revision"],
            oracle.EXPECTED_TASK_SOURCE_REVISION,
        )
        self.assertEqual(
            report["oracle_identity"]["oracle"]["revision"],
            report["current_checkout"]["revision"],
        )
        self.assertTrue(report["oracle_identity"]["oracle"]["revision_verified"])
        self.assertEqual(
            report["oracle_identity"]["trusted_implementations"]["revision"],
            report["current_checkout"]["revision"],
        )
        self.assertTrue(report["oracle_identity"]["trusted_implementations"]["revision_verified"])
        self.assertNotEqual(
            report["oracle_identity"]["oracle"]["revision"],
            report["task_contract"]["repository_revision"],
        )
        self.assertEqual(report["results"]["correct_reference"]["status"], "pass")
        for name in (
            "accepts_duplicates",
            "accepts_unknown",
            "incomplete_reference",
            "rejects_optional_none",
            "runtime_error_on_rejection",
        ):
            self.assertEqual(report["results"][name]["status"], "reject")

    def test_oracle_reports_each_required_case_group(self) -> None:
        report = oracle.run_oracle()
        expected_groups = {"optional", "normal", "boundary", "rejection"}
        result = report["results"]["correct_reference"]
        self.assertTrue(result["case_coverage_pass"])
        self.assertTrue(result["requirements_complete"])
        self.assertTrue(result["completeness_pass"])
        self.assertEqual({case["group"] for case in result["case_results"]}, expected_groups)
        self.assertEqual(result["cases_executed"], 9)
        self.assertEqual(result["required_cases_executed"], 9)

    def test_defect_is_localised_to_duplicate_invariant(self) -> None:
        report = oracle.run_oracle()
        result = report["results"]["accepts_duplicates"]
        failures = {case["case_id"] for case in result["case_results"] if not case["passed"]}
        self.assertEqual(failures, {"duplicate-axis"})

    def test_positive_completeness_defect_is_localised(self) -> None:
        report = oracle.run_oracle()
        result = report["results"]["incomplete_reference"]
        failures = {case["case_id"] for case in result["case_results"] if not case["passed"]}
        self.assertEqual(failures, {"task-completion-axis", "multi-axis"})
        self.assertTrue(result["case_coverage_pass"])
        self.assertFalse(result["requirements_complete"])

    def test_unexpected_exception_is_not_a_valid_rejection(self) -> None:
        report = oracle.run_oracle()
        result = report["results"]["runtime_error_on_rejection"]
        self.assertTrue(any(case["execution_error"] for case in result["case_results"]))
        self.assertTrue(all(not case["passed"] for case in result["case_results"] if case["execution_error"]))

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

    def test_file_provenance_matches_head_blob_and_detects_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "oracle.py").write_bytes(b"oracle = 1\n")
            (root / "trusted_implementations.py").write_bytes(b"trusted = 1\n")
            for command in (
                ["git", "init"],
                ["git", "config", "user.name", "oracle-test"],
                ["git", "config", "user.email", "oracle-test@example.invalid"],
                ["git", "add", "oracle.py", "trusted_implementations.py"],
                ["git", "commit", "-m", "fixture"],
            ):
                subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)

            checkout = oracle._current_checkout_identity(root)
            clean_oracle = oracle._tracked_file_identity("oracle.py", root=root, checkout=checkout)
            clean_trusted = oracle._tracked_file_identity(
                "trusted_implementations.py", root=root, checkout=checkout
            )
            self.assertTrue(clean_oracle["revision_verified"])
            self.assertTrue(clean_trusted["revision_verified"])
            self.assertEqual(clean_oracle["current_sha256"], clean_oracle["head_blob_sha256"])

            (root / "unrelated.txt").write_bytes(b"dirty but irrelevant\n")
            unrelated_dirty = oracle._tracked_file_identity("oracle.py", root=root, checkout=checkout)
            self.assertTrue(unrelated_dirty["revision_verified"])

            (root / "oracle.py").write_bytes(b"oracle = 2\n")
            changed_oracle = oracle._tracked_file_identity("oracle.py", root=root, checkout=checkout)
            self.assertFalse(changed_oracle["revision_verified"])
            self.assertIn("working-tree bytes differ from HEAD blob", changed_oracle["errors"])

            (root / "trusted_implementations.py").write_bytes(b"trusted = 2\n")
            changed_trusted = oracle._tracked_file_identity(
                "trusted_implementations.py", root=root, checkout=checkout
            )
            self.assertFalse(changed_trusted["revision_verified"])

            missing = oracle._tracked_file_identity("missing.py", root=root, checkout=checkout)
            self.assertFalse(missing["revision_verified"])
            self.assertIn("HEAD blob is unavailable", missing["errors"])


if __name__ == "__main__":
    unittest.main()
