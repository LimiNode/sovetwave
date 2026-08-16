#!/usr/bin/env python3
"""Offline checks for the behavioral harness; no model account is used."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from run_model_evals import load_cases, redact_secrets, run_variant


RUNNER = ROOT / "scripts" / "run_model_evals.py"
COMPARE = ROOT / "scripts" / "compare_runs.py"


class BehavioralHarnessTests(unittest.TestCase):
    def test_stderr_redacts_credentials(self) -> None:
        self.assertEqual(redact_secrets("Bearer abc.def_123"), "[redacted credential]")
        self.assertEqual(redact_secrets("api_key=sk-example-secret"), "[redacted credential]")

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

    def test_codex_dry_run_copies_only_selected_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            config = directory_path / "config.toml"
            output = directory_path / "run.json"
            config.write_text(
                """model_provider = \"local-lb\"\n\n[model_providers.local-lb]\nname = \"openai\"\nbase_url = \"http://127.0.0.1:2455/backend-api/codex\"\nwire_api = \"responses\"\nrequires_openai_auth = true\n""",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--provider", "codex",
                    "--dry-run",
                    "--limit", "1",
                    "--codex-provider-config", str(config),
                    "--output", str(output),
                ],
                cwd=ROOT, text=True, capture_output=True, check=True,
            )
            command = json.loads(output.read_text(encoding="utf-8"))["results"][0]["command"]
            self.assertIn("--ignore-user-config", command)
            self.assertIn('model_provider="local-lb"', command)
            self.assertIn('model_providers.local-lb.base_url="http://127.0.0.1:2455/backend-api/codex"', command)
            self.assertIn("model_providers.local-lb.requires_openai_auth=true", command)

    def test_case_id_selects_one_named_case(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run.json"
            subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--provider", "codex",
                    "--dry-run",
                    "--case-id", "russian-pr-status-report",
                    "--output", str(output),
                ],
                cwd=ROOT, text=True, capture_output=True, check=True,
            )
            run = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(run["results"]), 2)
            self.assertEqual({item["case_id"] for item in run["results"]}, {"russian-pr-status-report"})

    def test_russian_generalization_suite_has_broad_coverage(self) -> None:
        cases = load_cases(ROOT / "evals" / "behavioral" / "cases")
        russian_cases = [case for case in cases if case["id"].startswith("russian-")]
        self.assertGreaterEqual(len(russian_cases), 16)
        self.assertTrue(all(case["assertions"] for case in russian_cases))

    def test_live_run_uses_utf8_and_handles_missing_streams(self) -> None:
        completed = subprocess.CompletedProcess(args=["codex"], returncode=1, stdout=None, stderr=None)
        case = {"id": "sample", "prompt": "Explain"}
        with patch("run_model_evals.subprocess.run", return_value=completed) as run:
            result = run_variant("codex", case, False, None, 30, False)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["response"], "")
        self.assertEqual(result["stderr"], "")
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

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
