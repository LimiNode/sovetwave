import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_experiment_readiness as readiness  # noqa: E402


class ExperimentReadinessTests(unittest.TestCase):
    def manifest(self) -> dict:
        return copy.deepcopy(readiness.load_manifest())

    def assert_not_ready(self, result: dict) -> None:
        self.assertIn(result["status"], {"BLOCKED", "INVALID"})
        self.assertFalse(result["execution_ready"])
        self.assertFalse(result["task_fixtures_verified"])
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(result["model_calls"], 0)

    def test_manifest_is_design_valid_but_execution_blocked(self) -> None:
        result = readiness.validate_manifest()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["design_valid"])
        self.assertTrue(result["provenance_verified"])
        self.assertTrue(result["allocation_plan_verified"])
        self.assert_not_ready(result)

    def test_runtime_bindings_are_explicitly_pending(self) -> None:
        manifest = readiness.load_manifest()
        runtime = manifest["shared_runtime"]
        self.assertEqual(manifest["validator_scope"], "design_only")
        self.assertIsNone(runtime["model_id"])
        self.assertIsNone(runtime["host_endpoint"])
        self.assertIsNone(runtime["tool_surface"])
        self.assertIn("required before execution", runtime["binding_status"])

    def test_missing_frozen_revision_is_fail_closed(self) -> None:
        manifest = self.manifest()
        missing_revision = "0" * 40
        manifest["harness"]["frozen_reference_revision"] = missing_revision
        manifest["arms"][1]["repository_revision"] = missing_revision
        manifest["arms"][2]["repository_revision"] = missing_revision
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["design_valid"])
        self.assertFalse(result["provenance_verified"])
        self.assertFalse(result["skill_revision_resolved"])
        self.assert_not_ready(result)

    def test_wrong_skill_hash_is_fail_closed(self) -> None:
        manifest = self.manifest()
        manifest["arms"][1]["skill_tree_sha256"] = "0" * 64
        manifest["arms"][2]["skill_tree_sha256"] = "0" * 64
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["design_valid"])
        self.assertFalse(result["provenance_verified"])
        self.assertFalse(result["skill_tree_hash_verified"])
        self.assert_not_ready(result)

    def test_wrong_overlay_hash_and_changed_path_are_fail_closed(self) -> None:
        for change in ("hash", "path"):
            with self.subTest(change=change):
                manifest = self.manifest()
                if change == "hash":
                    manifest["arms"][2]["overlay_sha256"] = "0" * 64
                else:
                    manifest["arms"][2]["overlay_path"] = "research/missing-overlay.md"
                result = readiness.validate_manifest(manifest)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertTrue(result["design_valid"])
                self.assertFalse(result["provenance_verified"])
                self.assertFalse(result["overlay_hash_verified"])
                self.assert_not_ready(result)

    def test_swapped_arm_identities_are_invalid(self) -> None:
        manifest = self.manifest()
        manifest["arms"][0]["id"], manifest["arms"][1]["id"] = manifest["arms"][1]["id"], manifest["arms"][0]["id"]
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "INVALID")
        self.assertFalse(result["design_valid"])
        self.assert_not_ready(result)

    def test_empty_bound_fixture_dictionary_is_invalid(self) -> None:
        manifest = self.manifest()
        manifest["task_fixtures_bound"] = True
        manifest["task_fixtures"] = {}
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "INVALID")
        self.assert_not_ready(result)

    def test_nonexistent_bound_fixture_is_invalid(self) -> None:
        manifest = self.manifest()
        manifest["task_fixtures_bound"] = True
        manifest["task_fixtures"] = {"status": "bound", "paths": ["research/does-not-exist.json"]}
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "INVALID")
        self.assert_not_ready(result)

    def test_fictitious_runtime_bindings_are_invalid(self) -> None:
        manifest = self.manifest()
        manifest["runtime_bound"] = True
        for field in ("model_id", "host_endpoint", "tool_surface", "permissions_profile", "environment_snapshot"):
            manifest["shared_runtime"][field] = f"fake-{field}"
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "INVALID")
        self.assert_not_ready(result)

    def test_claimed_execution_ready_without_preflight_is_invalid(self) -> None:
        manifest = self.manifest()
        manifest["execution_ready"] = True
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "INVALID")
        self.assert_not_ready(result)

    def test_top_level_status_cannot_contradict_design_only_scope(self) -> None:
        manifest = self.manifest()
        manifest["status"] = "execution_ready"
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "INVALID")
        self.assert_not_ready(result)

    def test_allocation_replay_remains_verified(self) -> None:
        manifest = self.manifest()
        self.assertEqual(manifest["allocation"]["plan"], readiness.build_allocation_plan(manifest))
        self.assertEqual(len(manifest["allocation"]["plan"]), 36)


if __name__ == "__main__":
    unittest.main()
