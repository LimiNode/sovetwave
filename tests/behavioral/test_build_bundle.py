import unittest

from scripts.build_bundle import sanitize_result, statistics_rows


class BuildBundleTests(unittest.TestCase):
    def test_legacy_missing_telemetry_is_preserved_as_unknown(self):
        row = sanitize_result("run", "rev", {
            "case_id": "case", "variant": "baseline", "process_status": "timeout",
            "stderr": "", "response": "",
        })
        self.assertIsNone(row["material_inputs_dirty"])
        self.assertIsNone(row["attempt"])
        self.assertIsNone(row["recovered"])
        self.assertIsNone(row["original_process_status"])

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


if __name__ == "__main__":
    unittest.main()
