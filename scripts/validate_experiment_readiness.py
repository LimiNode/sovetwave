"""Validate the offline Experiment Readiness design manifest without model calls."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "research" / "experiment-readiness-manifest.json"
EXPECTED_ARMS = {"baseline", "sovetwave-frozen", "sovetwave-explicit-ladder"}


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_revision_available(revision: str) -> bool:
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _git_skill_tree_hash(revision: str) -> str | None:
    try:
        raw_paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", revision, "skills/sovetwave"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    paths = sorted(path for path in raw_paths.splitlines() if path)
    if not paths:
        return None
    digest = hashlib.sha256()
    try:
        for path in paths:
            digest.update(path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT))
            digest.update(b"\0")
    except (OSError, subprocess.CalledProcessError):
        return None
    return digest.hexdigest()


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def build_allocation_plan(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = [task["id"] for task in manifest["task_contract"]]
    arms = [arm["id"] for arm in manifest["arms"]]
    repetitions = manifest["allocation"]["repetitions_per_arm"]
    permutations = list(itertools.permutations(arms))
    block_count = len(tasks) * repetitions
    if block_count % len(permutations) != 0:
        raise ValueError("balanced allocation requires a whole number of permutation sets")
    blocks = permutations * (block_count // len(permutations))
    random.Random(manifest["allocation"]["seed"]).shuffle(blocks)
    plan: list[dict[str, Any]] = []
    sequence = 0
    block_index = 0
    for task_id in tasks:
        for repetition in range(1, repetitions + 1):
            for block_position, arm_id in enumerate(blocks[block_index], start=1):
                sequence += 1
                plan.append(
                    {
                        "sequence": sequence,
                        "task_id": task_id,
                        "repetition": repetition,
                        "arm_id": arm_id,
                        "block_position": block_position,
                    }
                )
            block_index += 1
    return plan


def _resolve_repository_path(relative_path: Any) -> tuple[Path | None, str | None]:
    if not isinstance(relative_path, str) or not relative_path:
        return None, "overlay_path must be a non-empty repository-relative string"
    candidate = (ROOT / relative_path).resolve()
    root = ROOT.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, "overlay_path escapes the repository root"
    return candidate, None


def validate_manifest(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = load_manifest() if manifest is None else manifest
    errors: list[str] = []
    design_errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)
            design_errors.append(message)

    check(isinstance(manifest, dict), "manifest must be an object")
    if not isinstance(manifest, dict):
        return {
            "status": "INVALID",
            "design_valid": False,
            "provenance_verified": False,
            "allocation_plan_verified": False,
            "task_fixtures_verified": False,
            "runtime_verified": False,
            "execution_ready": False,
            "model_calls": 0,
            "errors": errors,
        }

    check(manifest.get("schema_version") == 1, "schema_version must be 1")
    check(manifest.get("status") == "design_valid_execution_blocked", "manifest status must declare design-only execution blocking")
    check(manifest.get("validator_scope") == "design_only", "validator_scope must be design_only")
    check(manifest.get("design_valid") is True, "design_valid must be true for this design manifest")
    check(manifest.get("task_fixtures_bound") is False, "design-only manifest must not claim bound task fixtures")
    check(manifest.get("runtime_bound") is False, "design-only manifest must not claim runtime bindings")
    check(manifest.get("execution_ready") is False, "design-only manifest must declare execution_ready=false")

    harness = manifest.get("harness")
    arms = manifest.get("arms")
    task_contract = manifest.get("task_contract")
    allocation = manifest.get("allocation")
    runtime = manifest.get("shared_runtime")
    check(isinstance(harness, dict), "harness must be an object")
    check(isinstance(arms, list), "arms must be a list")
    check(isinstance(task_contract, list) and bool(task_contract), "task_contract must be a non-empty list")
    check(isinstance(allocation, dict), "allocation must be an object")
    check(isinstance(runtime, dict), "shared_runtime must be an object")
    if not all(isinstance(value, (dict, list)) for value in (harness, arms, task_contract, allocation, runtime)):
        return {
            "status": "INVALID",
            "design_valid": False,
            "provenance_verified": False,
            "allocation_plan_verified": False,
            "task_fixtures_verified": False,
            "runtime_verified": False,
            "execution_ready": False,
            "model_calls": 0,
            "errors": errors,
        }

    task_ids = [task.get("id") for task in task_contract if isinstance(task, dict)]
    check(len(task_ids) == len(task_contract) and len(set(task_ids)) == len(task_ids), "task contract ids must be unique")
    arms_by_id = {arm.get("id"): arm for arm in arms if isinstance(arm, dict)}
    check(set(arms_by_id) == EXPECTED_ARMS, "arm identities must match the declared three-arm design")
    check(len(arms_by_id) == len(arms) == len(EXPECTED_ARMS), "arm ids must be unique")

    recorded_revision = harness.get("frozen_reference_revision")
    repository_revision = harness.get("repository_revision")
    evaluator_revision = harness.get("evaluator_revision")
    check(isinstance(recorded_revision, str) and bool(recorded_revision), "frozen_reference_revision is required")
    check(isinstance(repository_revision, str) and bool(repository_revision), "repository_revision is required")
    check(isinstance(evaluator_revision, str) and bool(evaluator_revision), "evaluator_revision is required")
    check(harness.get("task_contract_sha256") == _canonical_hash(task_contract), "task contract hash does not match manifest contents")

    if set(arms_by_id) == EXPECTED_ARMS:
        baseline = arms_by_id["baseline"]
        frozen = arms_by_id["sovetwave-frozen"]
        overlay_arm = arms_by_id["sovetwave-explicit-ladder"]
        check(baseline.get("skill_mode") == "none", "baseline arm must have skill_mode=none")
        check(baseline.get("repository_revision") == repository_revision, "baseline arm must use repository_revision")
        check(baseline.get("skill_tree_sha256") is None and baseline.get("overlay_sha256") is None, "baseline must not carry skill or overlay identity")
        check(frozen.get("skill_mode") == "production_frozen", "frozen arm identity is inconsistent")
        check(overlay_arm.get("skill_mode") == "production_frozen_plus_research_overlay", "overlay arm identity is inconsistent")

    if set(arms_by_id) == EXPECTED_ARMS:
        frozen = arms_by_id["sovetwave-frozen"]
        overlay_arm = arms_by_id["sovetwave-explicit-ladder"]
        check(frozen.get("repository_revision") == recorded_revision, "frozen arm must use frozen_reference_revision")
        check(overlay_arm.get("repository_revision") == recorded_revision, "overlay arm must use frozen_reference_revision")
        check(frozen.get("skill_tree_sha256") == overlay_arm.get("skill_tree_sha256"), "research overlay must preserve frozen skill identity")

    overlay_path, overlay_path_error = _resolve_repository_path(
        arms_by_id.get("sovetwave-explicit-ladder", {}).get("overlay_path")
    )
    if overlay_path_error:
        errors.append(overlay_path_error)
    overlay_hash_verified = False
    if overlay_path is not None:
        try:
            observed_overlay_hash = _file_hash(overlay_path)
        except OSError as error:
            errors.append(f"overlay cannot be read: {error}")
        else:
            overlay_hash_verified = observed_overlay_hash == arms_by_id.get("sovetwave-explicit-ladder", {}).get("overlay_sha256")
            if not overlay_hash_verified:
                errors.append("overlay hash does not match the manifest at overlay_path")

    revision_resolved = isinstance(recorded_revision, str) and _git_revision_available(recorded_revision)
    skill_hash_verified = False
    if not revision_resolved:
        errors.append("frozen reference revision is unavailable; skill identity cannot be verified")
    else:
        observed_skill_hash = _git_skill_tree_hash(recorded_revision)
        expected_skill_hash = arms_by_id.get("sovetwave-frozen", {}).get("skill_tree_sha256")
        skill_hash_verified = observed_skill_hash is not None and observed_skill_hash == expected_skill_hash
        if observed_skill_hash is None:
            errors.append("frozen reference revision has no readable skills/sovetwave tree")
        elif not skill_hash_verified:
            errors.append("frozen skill tree hash does not match the manifest")

    runtime_values = (
        runtime.get("model_id"),
        runtime.get("host_endpoint"),
        runtime.get("tool_surface"),
        runtime.get("permissions_profile"),
        runtime.get("environment_snapshot"),
    )
    check(not any(value is not None for value in runtime_values), "design-only runtime bindings must remain null")
    runtime_verified = False

    fixture_info = manifest.get("task_fixtures")
    check(isinstance(fixture_info, dict), "task_fixtures must be an object")
    if isinstance(fixture_info, dict):
        check(fixture_info.get("status") == "not_bound", "design-only task fixtures must declare status=not_bound")
        check(fixture_info.get("paths") == [], "design-only task fixture paths must remain empty")
    task_fixtures_verified = False

    allocation_plan_verified = False
    try:
        expected_plan = build_allocation_plan(manifest)
    except (KeyError, TypeError, ValueError) as error:
        errors.append(f"allocation plan cannot be generated: {error}")
    else:
        recorded_plan = allocation.get("plan")
        allocation_plan_verified = recorded_plan == expected_plan
        check(allocation_plan_verified, "recorded allocation plan does not match deterministic replay")
        expected_calls = len(task_contract) * len(arms) * allocation.get("repetitions_per_arm", 0)
        check(expected_calls == allocation.get("maximum_model_calls"), "maximum_model_calls does not match the allocation")
        check(expected_calls == len(expected_plan), "allocation plan length does not match the design")
        plan_keys = {(row.get("task_id"), row.get("arm_id"), row.get("repetition")) for row in expected_plan}
        check(len(plan_keys) == len(expected_plan), "allocation plan contains duplicate task/arm/repetition identities")
        position_counts = {arm_id: [0, 0, 0] for arm_id in arms_by_id}
        for row in expected_plan:
            position_counts[row["arm_id"]][row["block_position"] - 1] += 1
        check(len({tuple(counts) for counts in position_counts.values()}) == 1, "arm order is not balanced across block positions")

    design_valid = not design_errors
    provenance_verified = revision_resolved and skill_hash_verified and overlay_hash_verified
    blockers: list[str] = []
    if not revision_resolved:
        blockers.append("frozen reference revision is unavailable")
    if not skill_hash_verified:
        blockers.append("frozen skill tree hash is not verified")
    if not overlay_hash_verified:
        blockers.append("research overlay hash is not verified")
    blockers.append("repository task fixtures require a separate execution preflight")
    blockers.append("runtime bindings require a separate execution preflight")
    if not allocation_plan_verified:
        blockers.append("allocation plan is not verified")
    execution_ready = False
    status = "BLOCKED" if design_valid else "INVALID"
    return {
        "status": status,
        "design_valid": design_valid,
        "provenance_verified": provenance_verified,
        "task_fixtures_verified": task_fixtures_verified,
        "runtime_verified": runtime_verified,
        "execution_ready": execution_ready,
        "skill_revision_resolved": revision_resolved,
        "skill_tree_hash_verified": skill_hash_verified,
        "overlay_hash_verified": overlay_hash_verified,
        "allocation_plan_verified": allocation_plan_verified,
        "model_calls": 0,
        "errors": errors,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="validate the checked-in design-only manifest")
    args = parser.parse_args()
    result = validate_manifest()
    if args.selftest:
        if result["status"] == "INVALID":
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        print("Experiment readiness manifest self-test: PASS (design valid; execution blocked)")
        return 0
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
