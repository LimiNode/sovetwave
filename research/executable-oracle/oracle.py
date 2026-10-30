"""Execute an independent oracle against trusted reference implementations."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from trusted_implementations import (
    accepts_duplicates,
    accepts_unknown,
    correct_reference,
    incomplete_reference,
    rejects_optional_none,
    runtime_error_on_rejection,
)


ROOT = Path(__file__).resolve().parents[2]
TASK_PATH = ROOT / "research" / "executable-oracle" / "task.json"
IMPLEMENTATIONS_PATH = ROOT / "research" / "executable-oracle" / "trusted_implementations.py"
ORACLE_PATH = ROOT / "research" / "executable-oracle" / "oracle.py"
EXPECTED_TASK_SOURCE_REVISION = "a188183c16a424ef3848458dadb0df3858eb48fa"
EXPECTED_SOURCE_SHA256 = "b2932a19df5cab6419e894278139b3e03ef32e0af2288eb12383e18457193621"
EXECUTION_MODE = "trusted_reference_implementations_only"

Implementation = Callable[..., None]


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_task() -> dict[str, Any]:
    return json.loads(TASK_PATH.read_text(encoding="utf-8"))


def _pinned_source_identity(task: dict[str, Any]) -> dict[str, Any]:
    target = task.get("repository_target", {})
    revision = task.get("repository_revision")
    relative = target.get("path")
    expected_sha256 = target.get("source_sha256")
    errors: list[str] = []
    safe_relative = (
        isinstance(relative, str)
        and bool(relative)
        and not Path(relative).is_absolute()
        and ".." not in Path(relative).parts
    )
    if not isinstance(revision, str) or not revision:
        errors.append("repository revision is required")
    if not safe_relative:
        errors.append("repository target path must be a safe relative path")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        errors.append("repository target SHA-256 is malformed")
    pinned_source = b""
    if isinstance(revision, str) and safe_relative:
        try:
            pinned_source = subprocess.check_output(
                ["git", "show", f"{revision}:{relative}"],
                cwd=ROOT,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError):
            errors.append("pinned source is unavailable")
    observed_sha256 = hashlib.sha256(pinned_source).hexdigest() if pinned_source else None
    marker = target.get("required_marker")
    marker_present = isinstance(marker, str) and marker.encode("utf-8") in pinned_source
    if revision != EXPECTED_TASK_SOURCE_REVISION:
        errors.append("task revision does not match the frozen oracle revision")
    if expected_sha256 != EXPECTED_SOURCE_SHA256 or observed_sha256 != expected_sha256:
        errors.append("pinned source SHA-256 does not match the frozen contract")
    if not marker_present:
        errors.append("pinned source marker is absent")
    current_path = ROOT / relative if safe_relative else ROOT / "__missing__"
    current_sha256 = _file_hash(current_path) if current_path.is_file() else None
    return {
        "repository_revision": revision,
        "path": relative,
        "expected_sha256": expected_sha256,
        "pinned_sha256": observed_sha256,
        "pinned_marker_present": marker_present,
        "verified": not errors,
        "errors": errors,
        "current_checkout": {
            "sha256": current_sha256,
            "matches_pinned": current_sha256 == observed_sha256,
        },
    }


def _current_checkout_identity() -> dict[str, Any]:
    errors: list[str] = []
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
        errors.append("current checkout revision is unavailable")
    try:
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        dirty = None
        errors.append("current checkout status is unavailable")
    return {"revision": revision, "dirty": dirty, "verified": not errors, "errors": errors}


def _validate_task(task: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if task.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    contract = task.get("contract")
    if not isinstance(contract, dict):
        return errors + ["contract must be an object"]
    if contract.get("function") != "validate_applicable_axes":
        errors.append("contract function is not validate_applicable_axes")
    if contract.get("signature") != "(value, *, allowed)":
        errors.append("contract signature is not pinned")
    allowed = contract.get("allowed_axes")
    if not isinstance(allowed, list) or not allowed or any(not isinstance(axis, str) for axis in allowed):
        errors.append("allowed_axes must be a non-empty string list")
    cases = contract.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["contract cases must be a non-empty list"]
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(ids) != len(cases) or len(set(ids)) != len(ids):
        errors.append("case ids must be unique")
    vocabulary = set(contract.get("outcome_vocabulary", []))
    groups = set(contract.get("required_case_groups", []))
    required_case_ids = contract.get("required_case_ids")
    if not isinstance(required_case_ids, list) or not required_case_ids or any(
        not isinstance(case_id, str) for case_id in required_case_ids
    ):
        errors.append("required_case_ids must be a non-empty string list")
    elif len(set(required_case_ids)) != len(required_case_ids):
        errors.append("required_case_ids must be unique")
    case_ids = set(ids)
    if isinstance(required_case_ids, list) and not set(required_case_ids) <= case_ids:
        errors.append("required_case_ids must refer to declared cases")
    for case in cases:
        if not isinstance(case, dict):
            errors.append("case must be an object")
            continue
        if case.get("expected") not in vocabulary:
            errors.append(f"case has an unknown expected outcome: {case.get('id')}")
        if case.get("group") not in groups:
            errors.append(f"case has an unknown group: {case.get('id')}")
        if case.get("expected") == "rejected" and case.get("expected_error_type") != "ValueError":
            errors.append(f"rejected case must require ValueError: {case.get('id')}")
        if case.get("expected") == "accepted" and "expected_error_type" in case:
            errors.append(f"accepted case must not declare an error type: {case.get('id')}")
    if groups - {case.get("group") for case in cases if isinstance(case, dict)}:
        errors.append("required case groups are not covered")
    return errors


def _run_case(implementation: Implementation, case: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    expected = case["expected"]
    expected_error_type = case.get("expected_error_type")
    try:
        implementation(case.get("value"), allowed=allowed)
    except ValueError as error:
        observed = "rejected"
        error_type = type(error).__name__
        execution_error = False
    except Exception as error:
        observed = "execution_error"
        error_type = type(error).__name__
        execution_error = True
    else:
        observed = "accepted"
        error_type = None
        execution_error = False
    passed = observed == expected and (
        expected != "rejected" or error_type == expected_error_type
    )
    return {
        "case_id": case["id"],
        "group": case["group"],
        "expected": expected,
        "expected_error_type": expected_error_type,
        "observed": observed,
        "passed": passed,
        "error_type": error_type,
        "execution_error": execution_error,
    }


def grade_implementation(name: str, implementation: Implementation, task: dict[str, Any]) -> dict[str, Any]:
    contract = task["contract"]
    allowed = frozenset(contract["allowed_axes"])
    cases = contract["cases"]
    case_results = [_run_case(implementation, case, allowed) for case in cases]
    required_groups = set(contract["required_case_groups"])
    required_case_ids = set(contract["required_case_ids"])
    observed_groups = {result["group"] for result in case_results}
    case_coverage_pass = len(case_results) == len(cases) and required_groups <= observed_groups
    required_results = [result for result in case_results if result["case_id"] in required_case_ids]
    requirements_complete = (
        len(required_results) == len(required_case_ids)
        and all(result["passed"] for result in required_results)
    )
    correctness_pass = all(result["passed"] for result in case_results)
    completeness_pass = case_coverage_pass and requirements_complete
    return {
        "implementation": name,
        "status": "pass" if correctness_pass and completeness_pass else "reject",
        "correctness_pass": correctness_pass,
        "case_coverage_pass": case_coverage_pass,
        "requirements_complete": requirements_complete,
        "completeness_pass": case_coverage_pass and requirements_complete,
        "required_cases_executed": len(required_results),
        "required_cases_total": len(required_case_ids),
        "cases_executed": len(case_results),
        "case_results": case_results,
    }


IMPLEMENTATIONS: dict[str, Implementation] = {
    "correct_reference": correct_reference,
    "accepts_duplicates": accepts_duplicates,
    "accepts_unknown": accepts_unknown,
    "incomplete_reference": incomplete_reference,
    "rejects_optional_none": rejects_optional_none,
    "runtime_error_on_rejection": runtime_error_on_rejection,
}


def run_oracle() -> dict[str, Any]:
    task = load_task()
    task_errors = _validate_task(task)
    source_identity = _pinned_source_identity(task)
    if task_errors or not source_identity["verified"]:
        raise ValueError({"task_errors": task_errors, "source_identity": source_identity})
    results = {name: grade_implementation(name, implementation, task) for name, implementation in IMPLEMENTATIONS.items()}
    current_checkout = _current_checkout_identity()
    return {
        "schema_version": 1,
        "task_id": task["id"],
        "task_sha256": _canonical_hash(task),
        "execution_mode": EXECUTION_MODE,
        "model_calls": 0,
        "generated_code_executed": False,
        "agent_execution_observed": False,
        "task_contract": {
            "repository_revision": source_identity["repository_revision"],
            "task_sha256": _canonical_hash(task),
            "source_identity": source_identity,
        },
        "current_checkout": current_checkout,
        "source_identity": source_identity,
        "oracle_identity": {
            "oracle": {
                "revision": current_checkout["revision"],
                "sha256": _file_hash(ORACLE_PATH),
            },
            "trusted_implementations": {
                "revision": current_checkout["revision"],
                "sha256": _file_hash(IMPLEMENTATIONS_PATH),
            },
            "execution_boundary": "trusted checked-in callables only; no generated code or subprocess candidate execution",
        },
        "results": results,
    }


def selftest() -> dict[str, Any]:
    report = run_oracle()
    if report["results"]["correct_reference"]["status"] != "pass":
        raise ValueError("correct reference must pass every executable case")
    for name in (
        "accepts_duplicates",
        "accepts_unknown",
        "incomplete_reference",
        "rejects_optional_none",
        "runtime_error_on_rejection",
    ):
        if report["results"][name]["status"] != "reject":
            raise ValueError(f"defective reference {name} must be rejected")
    if report["model_calls"] != 0 or report["generated_code_executed"]:
        raise ValueError("oracle self-test crossed the forbidden execution boundary")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = selftest() if args.selftest else run_oracle()
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.selftest:
        print("Executable oracle self-test: PASS")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
