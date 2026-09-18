import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

from scripts.build_bundle import sanitize_result, statistics_rows


class BuildBundleTests(unittest.TestCase):
    def test_legacy_missing_telemetry_is_preserved_as_unknown(self):
        row = sanitize_result("run", "rev", {
            "case_id": "case", "variant": "baseline", "process_status": "timeout",
            "capability_stage": "inquiry",
            "decision_impact": "high",
            "evidence_access": "direct",
            "stderr": "", "response": "",
        })
        self.assertEqual(row["capability_stage"], "inquiry")
        self.assertEqual(row["decision_impact"], "high")
        self.assertEqual(row["evidence_access"], "direct")
        self.assertIsNone(row["material_inputs_dirty"])
        self.assertIsNone(row["attempt"])
        self.assertIsNone(row["recovered"])
        self.assertIsNone(row["original_process_status"])

    def test_observations_csv_keeps_capability_stage_and_case_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "run.json"
            output = root / "bundle"
            source.write_text(json.dumps({"results": [{
                "case_id": "case", "variant": "baseline", "process_status": "completed",
                "execution_mode": "prompt_only", "applicable_axes": ["technical_correctness"],
                "capability_stage": "inquiry", "response": "answer",
                "decision_impact": "high", "evidence_access": "direct",
            }]}), encoding="utf-8")
            subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build_bundle.py"),
                "--output-dir", str(output), "--run", f"experiment=rev={source}",
            ], cwd=ROOT, check=True, capture_output=True, text=True)
            with (output / "observations.csv").open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["capability_stage"], "inquiry")
            self.assertEqual(row["decision_impact"], "high")
            self.assertEqual(row["evidence_access"], "direct")
            self.assertEqual(row["execution_mode"], "prompt_only")
            self.assertEqual(json.loads(row["applicable_axes"]), ["technical_correctness"])

    def test_review_bundle_retains_top_level_diagnostic_maps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "run.json"
            output = root / "bundle"
            source.write_text(json.dumps({
                "case_decision_impacts": {"case": "high"},
                "case_evidence_access": {"case": "direct"},
                "results": [{
                    "case_id": "case", "variant": "baseline", "process_status": "completed",
                    "decision_impact": "high", "evidence_access": "direct", "response": "answer",
                }],
            }), encoding="utf-8")
            subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build_bundle.py"),
                "--output-dir", str(output), "--run", f"experiment=rev={source}",
            ], cwd=ROOT, check=True, capture_output=True, text=True)
            bundle = json.loads((output / "review-bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle["runs"][0]["case_decision_impacts"], {"case": "high"})
            self.assertEqual(bundle["runs"][0]["case_evidence_access"], {"case": "direct"})
            self.assertEqual(bundle["observations"][0]["evidence_access"], "direct")

    def test_recovery_metadata_and_completed_token_scope(self):
        common = {
            "experiment": "run", "revision": "rev", "case_id": "case",
            "variant": "baseline", "elapsed_seconds": 2,
        }
        rows = [
            {**common, "process_status": "completed", "reported_tokens": 100,
             "attempt": 1, "recovered": False, "original_process_status": None},
            {**common, "process_status": "timeout", "reported_tokens": 999,
             "attempt": 2, "recovered": True, "original_process_status": "timeout"},
        ]
        stats = statistics_rows(rows)[0]
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["timeouts"], 1)
        self.assertEqual(stats["token_observations_completed"], 1)
        self.assertEqual(stats["tokens_mean_completed"], 100)

    def test_recorded_revision_is_not_invented_and_mismatch_fails(self):
        legacy = sanitize_result("run", "rev1234", {
            "case_id": "case", "variant": "baseline", "process_status": "completed",
        })
        self.assertIsNone(legacy["skill_revision"])
        current = sanitize_result("run", "rev1234", {
            "case_id": "case", "variant": "baseline", "process_status": "completed",
            "skill_revision": "rev1234abcdef",
        })
        self.assertEqual(current["skill_revision"], "rev1234abcdef")
        with self.assertRaises(ValueError):
            sanitize_result("run", "rev1234", {
                "case_id": "case", "variant": "baseline", "process_status": "completed",
                "skill_revision": "other-revision",
            })

    def test_structured_usage_and_trace_are_retained(self):
        row = sanitize_result("run", "rev", {
            "case_id": "case", "variant": "sovetwave", "process_status": "completed",
            "codex_usage": {"input_tokens": 12, "output_tokens": 3},
            "codex_usage_events": 1, "codex_duplicate_usage_events": 0,
            "codex_item_counts_by_type": {"command_execution": 1},
            "codex_tool_calls": 1, "reference_trace_status": "not_available",
        })
        self.assertEqual(row["codex_usage"]["input_tokens"], 12)
        self.assertEqual(row["codex_input_tokens"], 12)
        self.assertEqual(row["codex_output_tokens"], 3)
        self.assertEqual(row["codex_item_counts_by_type"]["command_execution"], 1)
        self.assertEqual(row["reference_trace_status"], "not_available")

    def test_ambiguous_usage_is_not_flattened_or_counted(self):
        row = sanitize_result("run", "rev", {
            "case_id": "case", "variant": "sovetwave", "process_status": "completed",
            "codex_usage": {"input_tokens": 99},
            "codex_usage_events": 2, "codex_duplicate_usage_events": 1,
        })
        self.assertIsNone(row["codex_input_tokens"])
        stats = statistics_rows([row])[0]
        self.assertEqual(stats["codex_input_tokens_observations_completed"], 0)
        self.assertIsNone(stats["codex_input_tokens_mean_completed"])

    def test_usage_component_statistics_use_valid_completed_observations(self):
        common = {
            "experiment": "run", "revision": "rev", "case_id": "case",
            "variant": "baseline", "process_status": "completed",
            "codex_usage_events": 1, "codex_duplicate_usage_events": 0,
            "reported_tokens": None,
            "elapsed_seconds": None,
        }
        rows = [
            {**common, "codex_usage": {"input_tokens": 10, "output_tokens": 2}},
            {**common, "codex_usage": {"input_tokens": 20, "output_tokens": 4}},
            {**common, "codex_usage": {"input_tokens": 999},
             "codex_usage_events": 2, "codex_duplicate_usage_events": 1},
        ]
        stats = statistics_rows(rows)[0]
        self.assertEqual(stats["codex_input_tokens_observations_completed"], 2)
        self.assertEqual(stats["codex_input_tokens_mean_completed"], 15)
        self.assertEqual(stats["codex_input_tokens_median_completed"], 15)
        self.assertEqual(stats["codex_output_tokens_observations_completed"], 2)


if __name__ == "__main__":
    unittest.main()
