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
from run_model_evals import THEMATIC_REFERENCES, load_cases, make_workspace, redact_secrets, run_variant, summarize_ablation, variant_plan


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

    def test_codex_ablation_dry_run_creates_repeated_third_variant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run.json"
            subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--provider", "codex",
                    "--dry-run",
                    "--case-id", "cpp-vector-invalidation",
                    "--ablate-reference", "cpp-engineering.md",
                    "--repetitions", "2",
                    "--output", str(output),
                ],
                cwd=ROOT, text=True, capture_output=True, check=True,
            )
            run = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(run["ablation"]["status"], "planned")
            self.assertEqual(len(run["results"]), 6)
            self.assertEqual(
                [item["variant"] for item in run["results"]],
                [
                    "baseline", "sovetwave", "sovetwave_without_reference",
                    "baseline", "sovetwave_without_reference", "sovetwave",
                ],
            )
            self.assertEqual(
                run["variant_orders"],
                [
                    {"repetition": 1, "variants": ["baseline", "sovetwave", "sovetwave_without_reference"]},
                    {"repetition": 2, "variants": ["baseline", "sovetwave_without_reference", "sovetwave"]},
                ],
            )
            self.assertEqual([item["sequence"] for item in run["results"]], [1, 2, 3, 1, 2, 3])
            self.assertEqual({item["repetition"] for item in run["results"]}, {1, 2})
            self.assertEqual(
                run["results"][2]["ablated_reference"],
                "cpp-engineering.md",
            )

    def test_ablation_removes_only_the_selected_conditional_reference(self) -> None:
        with make_workspace(ROOT, True, "cpp-engineering.md") as directory:
            skill = Path(directory) / ".agents" / "skills" / "sovetwave"
            self.assertFalse((skill / "references" / "cpp-engineering.md").exists())
            self.assertNotIn(
                "[cpp-engineering.md](references/cpp-engineering.md)",
                (skill / "SKILL.md").read_text(encoding="utf-8"),
            )
            self.assertTrue((skill / "references" / "voice-core.md").exists())

    def test_code_economy_ablation_preserves_the_core_invariant(self) -> None:
        with make_workspace(ROOT, True, "code-economy.md") as directory:
            skill = Path(directory) / ".agents" / "skills" / "sovetwave"
            skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertFalse((skill / "references" / "code-economy.md").exists())
            self.assertNotIn(
                "[code-economy.md](references/code-economy.md)",
                skill_text,
            )
            self.assertIn("minimise semantic surface", skill_text)

    def test_c_engineering_ablation_preserves_the_core_invariant(self) -> None:
        with make_workspace(ROOT, True, "c-engineering.md") as directory:
            skill = Path(directory) / ".agents" / "skills" / "sovetwave"
            skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertFalse((skill / "references" / "c-engineering.md").exists())
            self.assertNotIn(
                "[c-engineering.md](references/c-engineering.md)",
                skill_text,
            )
            self.assertIn("establish storage duration", skill_text)
            self.assertTrue((skill / "references" / "cpp-engineering.md").exists())

    def test_python_engineering_ablation_preserves_the_core_invariant(self) -> None:
        with make_workspace(ROOT, True, "python-engineering.md") as directory:
            skill = Path(directory) / ".agents" / "skills" / "sovetwave"
            skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertFalse((skill / "references" / "python-engineering.md").exists())
            self.assertNotIn(
                "[python-engineering.md](references/python-engineering.md)",
                skill_text,
            )
            self.assertIn("Treat type annotations as interface evidence", skill_text)
            self.assertTrue((skill / "references" / "code-economy.md").exists())

    def test_agent_instruction_ablation_preserves_the_core_invariant(self) -> None:
        with make_workspace(ROOT, True, "agent-instructions.md") as directory:
            skill = Path(directory) / ".agents" / "skills" / "sovetwave"
            skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertFalse((skill / "references" / "agent-instructions.md").exists())
            self.assertNotIn(
                "[agent-instructions.md](references/agent-instructions.md)",
                skill_text,
            )
            self.assertIn("scoped operational contracts", skill_text)
            self.assertIn("target agent's documented or observed", skill_text)

    def test_house_conventions_ablation_preserves_precedence_and_cpp_layers(self) -> None:
        with make_workspace(ROOT, True, "house-conventions.md") as directory:
            skill = Path(directory) / ".agents" / "skills" / "sovetwave"
            skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertFalse((skill / "references" / "house-conventions.md").exists())
            self.assertNotIn(
                "[house-conventions.md](references/house-conventions.md)",
                skill_text,
            )
            self.assertIn("Repository instructions and established local style override", skill_text)
            self.assertTrue((skill / "references" / "cpp-engineering.md").exists())
            self.assertTrue((skill / "references" / "c-engineering.md").exists())

    def test_cpp_review_ablation_preserves_the_core_invariant(self) -> None:
        with make_workspace(ROOT, True, "cpp-review-workflow.md") as directory:
            skill = Path(directory) / ".agents" / "skills" / "sovetwave"
            skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertFalse((skill / "references" / "cpp-review-workflow.md").exists())
            self.assertNotIn(
                "[cpp-review-workflow.md](references/cpp-review-workflow.md)",
                skill_text,
            )
            self.assertIn("Use deterministic checks as evidence", skill_text)

    def test_qt_cpp_ablation_keeps_the_generic_cpp_review_layer(self) -> None:
        with make_workspace(ROOT, True, "qt-cpp-engineering.md") as directory:
            skill = Path(directory) / ".agents" / "skills" / "sovetwave"
            skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertFalse((skill / "references" / "qt-cpp-engineering.md").exists())
            self.assertNotIn(
                "[qt-cpp-engineering.md](references/qt-cpp-engineering.md)",
                skill_text,
            )
            self.assertTrue((skill / "references" / "cpp-review-workflow.md").exists())
            self.assertIn("whether the target is an application", skill_text)

    def test_ablation_rejects_a_non_thematic_reference(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--provider", "codex",
                "--dry-run",
                "--ablate-reference", "voice-core.md",
                "--repetitions", "2",
            ],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("must name a conditional skill reference", completed.stderr)

    def test_ablation_is_partial_when_some_repetitions_never_reach_it(self) -> None:
        results = [{"variant": "sovetwave_without_reference", "status": "completed", "repetition": 1}]
        self.assertEqual(summarize_ablation(results, expected_ablations=3, dry_run=False), "partial")
        self.assertEqual(summarize_ablation([], expected_ablations=3, dry_run=False), "not_tested")
        self.assertEqual(summarize_ablation(results, expected_ablations=1, dry_run=False), "completed")

    def test_russian_generalization_suite_has_broad_coverage(self) -> None:
        cases = load_cases(ROOT / "evals" / "behavioral" / "cases")
        russian_cases = {case["id"]: case for case in cases if case["id"].startswith("russian-")}
        required_ids = {
            "russian-pr-status-report",
            "russian-ci-result-summary",
            "russian-cmake-failure",
            "russian-api-documentation",
            "russian-sql-analysis",
            "russian-network-timeout",
            "russian-threading-review",
            "russian-python-dependency",
            "russian-benchmark-report",
            "russian-release-notes",
            "russian-refactoring-plan",
            "russian-review-follow-up",
            "russian-deployment-rollback",
            "russian-logging-diagnosis",
            "russian-git-working-tree",
            "russian-documentation-change",
            "russian-clean-build-status",
            "russian-clean-review-status",
            "russian-clean-deployment-note",
            "russian-clean-performance-report",
        }
        self.assertTrue(required_ids.issubset(russian_cases))
        self.assertTrue(all(case["assertions"] for case in russian_cases.values()))

    def test_cpp_engineering_suite_has_thematic_coverage(self) -> None:
        cases = load_cases(ROOT / "evals" / "behavioral" / "cases")
        cpp_cases = {case["id"]: case for case in cases if case["id"].startswith("cpp-")}
        required_ids = {
            "cpp-vector-invalidation",
            "cpp-exception-ownership",
            "cpp-moved-from-state",
            "cpp-behaviour-classification",
            "cpp-optimization-clue",
            "cpp-data-race-read",
            "cpp-condition-variable-predicate",
            "cpp-sanitizer-scope",
            "cpp-odr-abi-boundary",
            "cpp-uninitialized-state",
            "cpp-function-static-callback-slot-isolation",
        }
        self.assertTrue(required_ids.issubset(cpp_cases))
        self.assertTrue(all(case["assertions"] for case in cpp_cases.values()))

    def test_c_engineering_suite_has_thematic_coverage(self) -> None:
        cases = load_cases(ROOT / "evals" / "behavioral" / "cases")
        required_ids = {
            "c-small-fixed-temporary-buffer",
            "c-static-buffer-reentrancy",
            "c-untrusted-vla-stack-bound",
            "c-allocation-size-overflow",
            "c-partial-initialization-cleanup",
        }
        indexed = {case["id"]: case for case in cases}
        self.assertTrue(required_ids.issubset(indexed))
        self.assertTrue(all(indexed[case_id]["assertions"] for case_id in required_ids))
        self.assertIn("c-engineering.md", THEMATIC_REFERENCES)

    def test_python_engineering_suite_has_thematic_coverage(self) -> None:
        cases = load_cases(ROOT / "evals" / "behavioral" / "cases")
        required_ids = {
            "python-mutable-default-state-leak",
            "python-context-manager-resource-ownership",
            "python-exception-boundary-contract",
            "python-task-cancellation-ownership",
            "python-typing-runtime-boundary",
            "python-declared-dependency-boundary",
            "python-concurrency-from-workload",
            "python-free-threaded-cpu-parallelism",
        }
        indexed = {case["id"]: case for case in cases}
        self.assertTrue(required_ids.issubset(indexed))
        self.assertTrue(all(indexed[case_id]["assertions"] for case_id in required_ids))
        self.assertIn("python-engineering.md", THEMATIC_REFERENCES)

    def test_cpp_review_and_qt_suites_have_thematic_coverage(self) -> None:
        cases = load_cases(ROOT / "evals" / "behavioral" / "cases")
        required_ids = {
            "cpp-review-bounded-diff-scope",
            "cpp-review-remains-read-only",
            "cpp-review-linter-is-evidence",
            "cpp-review-abi-profile",
            "qt-cpp-qobject-profile",
            "qt-cpp-direct-connection-thread",
            "qt-cpp-cmake-version-boundary",
        }
        indexed = {case["id"]: case for case in cases}
        self.assertTrue(required_ids.issubset(indexed))
        self.assertTrue(all(indexed[case_id]["assertions"] for case_id in required_ids))
        self.assertIn("cpp-review-workflow.md", THEMATIC_REFERENCES)
        self.assertIn("qt-cpp-engineering.md", THEMATIC_REFERENCES)

    def test_house_conventions_suite_has_thematic_coverage(self) -> None:
        cases = load_cases(ROOT / "evals" / "behavioral" / "cases")
        required_ids = {
            "house-default-capture-selected-profile",
            "house-default-capture-no-profile",
            "house-repository-overrides-method-style",
            "house-semantic-scope-prefixes",
            "house-convention-not-correctness-defect",
        }
        indexed = {case["id"]: case for case in cases}
        self.assertTrue(required_ids.issubset(indexed))
        self.assertTrue(all(indexed[case_id]["assertions"] for case_id in required_ids))
        self.assertIn("house-conventions.md", THEMATIC_REFERENCES)

    def test_code_economy_suite_has_thematic_coverage(self) -> None:
        cases = load_cases(ROOT / "evals" / "behavioral" / "cases")
        economy_cases = {case["id"]: case for case in cases if case["id"].startswith("code-economy-")}
        required_ids = {
            "code-economy-reuse-existing-path",
            "code-economy-impossible-branch",
            "code-economy-no-speculative-framework",
            "code-economy-noexcept-is-contract",
            "code-economy-review-dead-residue",
            "code-economy-exact-reserve-growth",
            "code-economy-review-before-new-state",
            "code-economy-residue-survives-severity",
        }
        self.assertTrue(required_ids.issubset(economy_cases))
        self.assertTrue(all(case["assertions"] for case in economy_cases.values()))
        self.assertIn("code-economy.md", THEMATIC_REFERENCES)
        self.assertIn(
            "[code-economy.md](references/code-economy.md)",
            (ROOT / "skills" / "sovetwave" / "SKILL.md").read_text(encoding="utf-8"),
        )

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
            self.assertIn("Ablation: **не проверялось**", content)
            self.assertIn("Техническая правильность", content)

    def test_comparison_sheet_marks_missing_ablation_variants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "incomplete.json"
            sheet = Path(directory) / "comparison.md"
            run.write_text(json.dumps({
                "repetitions": 3,
                "case_ids": ["sample"],
                "ablation": {
                    "reference": "cpp-engineering.md",
                    "status": "partial",
                    "method": "test",
                },
                "results": [
                    {"case_id": "sample", "repetition": 1, "variant": "baseline", "prompt": "Explain", "status": "completed", "response": "Plain", "assertions": ["a"]},
                    {"case_id": "sample", "repetition": 1, "variant": "sovetwave", "prompt": "Explain", "status": "completed", "response": "Full", "assertions": ["a"]},
                    {"case_id": "sample", "repetition": 1, "variant": "sovetwave_without_reference", "ablated_reference": "cpp-engineering.md", "prompt": "Explain", "status": "completed", "response": "Ablated", "assertions": ["a"]},
                    {"case_id": "sample", "repetition": 2, "variant": "baseline", "prompt": "Explain", "status": "failed", "response": "", "assertions": ["a"]},
                ],
                "variant_orders": [
                    {"repetition": 1, "variants": ["baseline", "sovetwave", "sovetwave_without_reference"]},
                    {"repetition": 2, "variants": ["baseline", "sovetwave_without_reference", "sovetwave"]},
                    {"repetition": 3, "variants": ["baseline", "sovetwave", "sovetwave_without_reference"]},
                ],
            }), encoding="utf-8")
            subprocess.run([sys.executable, str(COMPARE), str(run), "--output", str(sheet)], cwd=ROOT, check=True)
            content = sheet.read_text(encoding="utf-8")
            self.assertIn("Ablation: `cpp-engineering.md` — **partial**", content)
            self.assertEqual(content.count("#### Sovetwave without `cpp-engineering.md`"), 3)
            self.assertIn("Не проверялось: вариант отсутствует в файле прогона", content)
            self.assertIn("Planned execution order: Baseline → Sovetwave without `cpp-engineering.md` → Sovetwave", content)

    def test_ablation_variant_plan_alternates_only_the_thematic_variants(self) -> None:
        self.assertEqual(variant_plan("cpp-engineering.md", 1), [(False, None), (True, None), (True, "cpp-engineering.md")])
        self.assertEqual(variant_plan("cpp-engineering.md", 2), [(False, None), (True, "cpp-engineering.md"), (True, None)])
        self.assertEqual(variant_plan(None, 3), [(False, None), (True, None)])


if __name__ == "__main__":
    unittest.main()
