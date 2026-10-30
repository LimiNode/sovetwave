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
    rejects_optional_none,
)


ROOT = Path(__file__).resolve().parents[2]
TASK_PATH = ROOT / "research" / "executable-oracle" / "task.json"
IMPLEMENTATIONS_PATH = ROOT / "research" / "executable-oracle" / "trusted_implementations.py"
ORACLE_PATH = ROOT / "research" / "executable-oracle" / "oracle.py"
EXPECTED_REVISION = "a188183c16a424ef3848458dadb0df3858eb48fa"
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
    if revision != EXPECTED_REVISION:
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
    for case in cases:
        if not isinstance(case, dict):
            errors.append("case must be an object")
            continue
        if case.get("expected") not in vocabulary:
            errors.append(f"case has an unknown expected outcome: {case.get('id')}")
        if case.get("group") not in groups:
            errors.append(f"case has an unknown group: {case.get('id')}")
    if groups - {case.get("group") for case in cases if isinstance(case, dict)}:
        errors.append("required case groups are not covered")
    return errors


def _run_case(implementation: Implementation, case: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    try:
        implementation(case.get("value"), allowed=allowed)
    except Exception as error:  # trusted implementations are expected to reject through exceptions
        observed = "rejected"
        error_type = type(error).__name__
    else:
        observed = "accepted"
        error_type = None
    expected = case["expected"]
    return {
        "case_id": case["id"],
        "group": case["group"],
        "expected": expected,
        "observed": observed,
        "passed": observed == expected,
        "error_type": error_type,
    }


def grade_implementation(name: str, implementation: Implementation, task: dict[str, Any]) -> dict[str, Any]:
    contract = task["contract"]
    allowed = frozenset(contract["allowed_axes"])
    cases = contract["cases"]
    case_results = [_run_case(implementation, case, allowed) for case in cases]
    required_groups = set(contract["required_case_groups"])
    observed_groups = {result["group"] for result in case_results}
    completeness_pass = len(case_results) == len(cases) and required_groups <= observed_groups
    correctness_pass = all(result["passed"] for result in case_results)
    return {
        "implementation": name,
        "status": "pass" if correctness_pass and completeness_pass else "reject",
        "correctness_pass": correctness_pass,
        "completeness_pass": completeness_pass,
        "cases_executed": len(case_results),
        "case_results": case_results,
    }


IMPLEMENTATIONS: dict[str, Implementation] = {
    "correct_reference": correct_reference,
    "accepts_duplicates": accepts_duplicates,
    "accepts_unknown": accepts_unknown,
    "rejects_optional_none": rejects_optional_none,
}


def run_oracle() -> dict[str, Any]:
    task = load_task()
    task_errors = _validate_task(task)
    source_identity = _pinned_source_identity(task)
    if task_errors or not source_identity["verified"]:
        raise ValueError({"task_errors": task_errors, "source_identity": source_identity})
    results = {name: grade_implementation(name, implementation, task) for name, implementation in IMPLEMENTATIONS.items()}
    return {
        "schema_version": 1,
        "task_id": task["id"],
        "task_sha256": _canonical_hash(task),
        "execution_mode": EXECUTION_MODE,
        "model_calls": 0,
        "generated_code_executed": False,
        "agent_execution_observed": False,
        "source_identity": source_identity,
        "oracle_identity": {
            "repository_revision": EXPECTED_REVISION,
            "oracle_sha256": _file_hash(ORACLE_PATH),
            "implementations_sha256": _file_hash(IMPLEMENTATIONS_PATH),
            "execution_boundary": "trusted checked-in callables only; no generated code or subprocess candidate execution",
        },
        "results": results,
    }


def selftest() -> dict[str, Any]:
    report = run_oracle()
    if report["results"]["correct_reference"]["status"] != "pass":
        raise ValueError("correct reference must pass every executable case")
    for name in ("accepts_duplicates", "accepts_unknown", "rejects_optional_none"):
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
