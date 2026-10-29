import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_experiment_readiness import load_manifest, validate_manifest  # noqa: E402


class ExperimentReadinessTests(unittest.TestCase):
    def test_manifest_is_deterministic_and_unexecuted(self) -> None:
        result = validate_manifest()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(len(load_manifest()["arms"]), 3)

    def test_runtime_bindings_are_explicitly_pending(self) -> None:
        runtime = load_manifest()["shared_runtime"]
        self.assertIsNone(runtime["model_id"])
        self.assertIsNone(runtime["host_endpoint"])
        self.assertIsNone(runtime["tool_surface"])
        self.assertIn("required before execution", runtime["binding_status"])


if __name__ == "__main__":
    unittest.main()
