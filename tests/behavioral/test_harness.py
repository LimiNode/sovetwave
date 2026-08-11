#!/usr/bin/env python3
"""Offline checks for the behavioral harness; no model account is used."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_model_evals.py"
COMPARE = ROOT / "scripts" / "compare_runs.py"


class BehavioralHarnessTests(unittest.TestCase):
    def test_codex_dry_run_creates_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run.json"
            completed = subprocess.run(
                [sys.executable, str(RUNNER), "--provider", "codex", "--dry-run", "--limit", "2", "--output", str(output)],
                cwd=ROOT, text=True, capture_output=True, check=True,
            )
            self.assertIn("4 planned", completed.stdout)
            run = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual([item["variant"] for item in run["results"]], ["baseline", "sovetwave", "baseline", "sovetwave"])
            self.assertTrue(run["results"][1]["command"][-1].startswith("$sovetwave\n"))

    def test_comparison_sheet_contains_both_variants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run.json"
            sheet = Path(directory) / "comparison.md"
            run.write_text(json.dumps({"results": [
                {"case_id": "sample", "variant": "baseline", "prompt": "Explain", "response": "Plain", "assertions": ["a"]},
                {"case_id": "sample", "variant": "sovetwave", "prompt": "Explain", "response": "Styled", "assertions": ["a"]},
            ]}), encoding="utf-8")
            subprocess.run([sys.executable, str(COMPARE), str(run), "--output", str(sheet)], cwd=ROOT, check=True)
            content = sheet.read_text(encoding="utf-8")
            self.assertIn("Plain", content)
            self.assertIn("Styled", content)
            self.assertIn("Техническая правильность", content)


if __name__ == "__main__":
    unittest.main()
