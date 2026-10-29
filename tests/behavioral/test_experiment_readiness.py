import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_experiment_readiness as readiness  # noqa: E402


class ExperimentReadinessTests(unittest.TestCase):
    def test_manifest_is_design_valid_but_execution_blocked(self) -> None:
        result = readiness.validate_manifest()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["design_valid"])
        self.assertFalse(result["task_fixtures_bound"])
        self.assertFalse(result["runtime_bound"])
        self.assertFalse(result["execution_ready"])
        self.assertEqual(result["model_calls"], 0)
        self.assertTrue(result["allocation_plan_verified"])

    def test_runtime_bindings_are_explicitly_pending(self) -> None:
        runtime = readiness.load_manifest()["shared_runtime"]
        self.assertIsNone(runtime["model_id"])
        self.assertIsNone(runtime["host_endpoint"])
        self.assertIsNone(runtime["tool_surface"])
        self.assertIn("required before execution", runtime["binding_status"])

    def test_missing_frozen_revision_is_fail_closed(self) -> None:
        manifest = copy.deepcopy(readiness.load_manifest())
        manifest["harness"]["frozen_reference_revision"] = "0" * 40
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["skill_revision_resolved"])
        self.assertFalse(result["execution_ready"])
        self.assertTrue(any("revision is unavailable" in error for error in result["errors"]))

    def test_wrong_skill_hash_is_not_pass(self) -> None:
        manifest = copy.deepcopy(readiness.load_manifest())
        manifest["arms"][1]["skill_tree_sha256"] = "0" * 64
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["skill_revision_resolved"])
        self.assertFalse(result["skill_tree_hash_verified"])

    def test_wrong_overlay_hash_and_changed_path_are_not_pass(self) -> None:
        manifest = copy.deepcopy(readiness.load_manifest())
        manifest["arms"][2]["overlay_sha256"] = "0" * 64
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["overlay_hash_verified"])

        manifest = copy.deepcopy(readiness.load_manifest())
        manifest["arms"][2]["overlay_path"] = "research/missing-overlay.md"
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["overlay_hash_verified"])

    def test_swapped_arm_identities_are_rejected(self) -> None:
        manifest = copy.deepcopy(readiness.load_manifest())
        manifest["arms"][0]["id"], manifest["arms"][1]["id"] = manifest["arms"][1]["id"], manifest["arms"][0]["id"]
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "INVALID")
        self.assertFalse(result["design_valid"])

    def test_missing_runtime_binding_cannot_claim_readiness(self) -> None:
        manifest = copy.deepcopy(readiness.load_manifest())
        manifest["runtime_bound"] = True
        result = readiness.validate_manifest(manifest)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["runtime_bound"])
        self.assertFalse(result["execution_ready"])
        self.assertTrue(any("runtime_bound=true" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
