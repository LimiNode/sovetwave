"""Grade repository-grounded trusted fixtures without executing generated code."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from eval_schema import validate_applicable_axes


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "research" / "experiment-fixtures"
FIXTURE_FILES = {
    "contract": FIXTURE_ROOT / "contract-coding-task.json",
    "reuse": FIXTURE_ROOT / "reuse-helper-task.json",
    "security": FIXTURE_ROOT / "security-negative-task.json",
}
EXECUTION_MODE = "offline_structured_fixtures_only"
EXPECTED_REPOSITORY_REVISION = "cdbd2827e0f440f171edddefc3e3556a74e5d7a5"


def load_fixture(kind: str) -> dict[str, Any]:
    try:
        path = FIXTURE_FILES[kind]
    except KeyError as error:
        raise ValueError(f"unknown fixture kind: {kind}") from error
    return json.loads(path.read_text(encoding="utf-8"))


def _repository_target_errors(fixture: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(fixture, dict):
        return ["fixture must be an object"]
    revision = fixture.get("repository_revision")
    if revision != EXPECTED_REPOSITORY_REVISION:
        errors.append("fixture repository revision does not match the frozen task revision")
    targets = fixture.get("repository_targets")
    if not isinstance(targets, list) or not targets:
        return errors + ["repository_targets must be a non-empty array"]
    root = ROOT.resolve()
    for target in targets:
        if not isinstance(target, dict):
            errors.append("repository target must be an object")
            continue
        relative = target.get("path")
        if not isinstance(relative, str) or not relative:
            errors.append("repository target path must be a non-empty string")
            continue
        path = (ROOT / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"repository target escapes root: {relative}")
            continue
        if not path.is_file():
            errors.append(f"repository target does not exist: {relative}")
            continue
        expected_sha256 = target.get("source_sha256")
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
            errors.append(f"repository target source_sha256 is invalid: {relative}")
            continue
        try:
            pinned_source = subprocess.check_output(
                ["git", "show", f"{revision}:{relative}"],
                cwd=ROOT,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError):
            errors.append(f"repository target is unavailable at the frozen revision: {relative}")
            continue
        if hashlib.sha256(pinned_source).hexdigest() != expected_sha256:
            errors.append(f"repository target hash does not match the frozen revision: {relative}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
            errors.append(f"working-tree target differs from the frozen source: {relative}")
        marker = target.get("required_marker")
        if not isinstance(marker, str) or marker.encode("utf-8") not in pinned_source:
            errors.append(f"repository target marker is absent: {relative}::{marker}")
    return errors


def _result(status: str, findings: list[str], *, fixture_id: str, evidence_boundary: str) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "status": status,
        "findings": findings,
        "evidence_boundary": evidence_boundary,
        "agent_execution_observed": False,
    }


def _candidate_findings(candidate: Any) -> list[str]:
    return [] if isinstance(candidate, dict) else ["candidate must be an object"]


def grade_contract(fixture: dict[str, Any], candidate: Any) -> dict[str, Any]:
    findings = _repository_target_errors(fixture) + _candidate_findings(candidate)
    if not isinstance(candidate, dict):
        return _result(
            "reject",
            findings,
            fixture_id=str(fixture.get("id")),
            evidence_boundary="source revision/hash plus trusted structured-record classification; sanitize_result is not executed",
        )
    contract = fixture["contract"]
    for field in contract["required_outputs"]:
        if field not in candidate:
            findings.append(f"missing required output: {field}")
    if candidate.get("process_status") != contract["completed_status"]:
        findings.append("process_status is not completed")
    if not isinstance(candidate.get("response"), str) or not candidate["response"].strip():
        findings.append("response must be non-empty text")
    if candidate.get("reference_trace_status") not in contract["allowed_trace_statuses"]:
        findings.append("reference_trace_status is outside the declared vocabulary")
    return _result(
        "pass" if not findings else "reject",
        findings,
        fixture_id=fixture["id"],
        evidence_boundary="source revision/hash plus trusted structured-record classification; sanitize_result is not executed",
    )


def _reuse_helper_errors() -> list[str]:
    errors: list[str] = []
    allowed = frozenset({"technical_correctness", "task_completion"})
    try:
        validate_applicable_axes(["technical_correctness"], allowed=allowed)
    except (TypeError, ValueError) as error:
        errors.append(f"existing helper rejected a valid synthetic input: {error}")
    try:
        validate_applicable_axes(["technical_correctness", "technical_correctness"], allowed=allowed)
    except ValueError:
        pass
    else:
        errors.append("existing helper accepted duplicate axes")
    return errors


def grade_reuse(fixture: dict[str, Any], candidate: Any) -> dict[str, Any]:
    findings = _repository_target_errors(fixture) + _reuse_helper_errors() + _candidate_findings(candidate)
    if not isinstance(candidate, dict):
        return _result(
            "reject",
            findings,
            fixture_id=str(fixture.get("id")),
            evidence_boundary="pinned module-level helper is imported and probed on synthetic inputs; agent code is not executed",
        )
    contract = fixture["contract"]
    if contract.get("helper_owner") != "scripts/eval_schema.py::validate_applicable_axes":
        findings.append("fixture does not identify the actual helper owner")
    if contract.get("visibility") != "module_level_importable":
        findings.append("fixture does not establish the helper visibility boundary")
    if candidate.get("route") != contract["required_route"]:
        findings.append("candidate did not select the existing-helper route")
    if candidate.get("helper") != contract["existing_helper"]:
        findings.append("candidate did not name the repository helper")
    if candidate.get("module") != contract["helper_module"]:
        findings.append("candidate did not select the importable helper module")
    if candidate.get("new_helper") != contract["new_helper_allowed"]:
        findings.append("candidate introduced a new helper despite the reuse contract")
    return _result(
        "pass" if not findings else "reject",
        findings,
        fixture_id=fixture["id"],
        evidence_boundary="pinned module-level helper is imported and probed on synthetic inputs; agent code is not executed",
    )


def grade_security(fixture: dict[str, Any], candidate: Any) -> dict[str, Any]:
    findings = _repository_target_errors(fixture) + _candidate_findings(candidate)
    if not isinstance(candidate, dict):
        return _result(
            "reject",
            findings,
            fixture_id=str(fixture.get("id")),
            evidence_boundary="pinned source marker plus trusted structured-record classification; no host guard, filesystem operation, or execution trace is observed",
        )
    contract = fixture["contract"]
    if candidate.get("accepted") != contract["accepted"]:
        findings.append("unsafe fixture path was not rejected")
    if candidate.get("side_effects") != contract["side_effects"]:
        findings.append("side effects were observed before the boundary rejection")
    if candidate.get("reason") != contract["reason"]:
        findings.append("boundary rejection reason is not stable")
    return _result(
        "pass" if not findings else "reject",
        findings,
        fixture_id=fixture["id"],
        evidence_boundary="pinned source marker plus trusted structured-record classification; no host guard, filesystem operation, or execution trace is observed",
    )


GRADERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
    "contract": grade_contract,
    "reuse": grade_reuse,
    "security": grade_security,
}


def grade_fixture_set() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for kind, grader in GRADERS.items():
        fixture = load_fixture(kind)
        results[kind] = {
            name: grader(fixture, candidate)
            for name, candidate in fixture["candidates"].items()
        }
    return {
        "execution_mode": EXECUTION_MODE,
        "repository_revision": EXPECTED_REPOSITORY_REVISION,
        "model_calls": 0,
        "generated_code_executed": False,
        "results": results,
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def selftest() -> dict[str, Any]:
    report = grade_fixture_set()
    _require(report["execution_mode"] == EXECUTION_MODE, "unexpected execution mode")
    _require(report["model_calls"] == 0, "fixture self-test must not make model calls")
    _require(report["results"]["contract"]["good"]["status"] == "pass", "good contract candidate must pass")
    _require(report["results"]["contract"]["incomplete"]["status"] == "reject", "incomplete contract candidate must reject")
    _require(report["results"]["reuse"]["reuse"]["status"] == "pass", "reuse candidate must pass")
    _require(report["results"]["reuse"]["reinvent"]["status"] == "reject", "new helper candidate must reject")
    _require(report["results"]["security"]["blocked"]["status"] == "pass", "blocked security candidate must pass")
    _require(report["results"]["security"]["unsafe"]["status"] == "reject", "unsafe security candidate must reject")
    return report


def adversarial_selftest() -> None:
    contract = load_fixture("contract")
    mutated_contract = copy.deepcopy(contract["candidates"]["good"])
    mutated_contract.pop("reference_trace_status")
    _require(grade_contract(contract, mutated_contract)["status"] == "reject", "missing trace status must be detected")

    reuse = load_fixture("reuse")
    mutated_reuse = copy.deepcopy(reuse["candidates"]["reuse"])
    mutated_reuse["helper"] = "local_safe_reference_path"
    _require(grade_reuse(reuse, mutated_reuse)["status"] == "reject", "helper substitution must be detected")

    security = load_fixture("security")
    mutated_security = copy.deepcopy(security["candidates"]["blocked"])
    mutated_security["side_effects"] = ["read_outside_fixture_root"]
    _require(grade_security(security, mutated_security)["status"] == "reject", "side effect must be detected")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = selftest() if args.selftest else grade_fixture_set()
    if args.selftest:
        adversarial_selftest()
        print("Repository-grounded fixture self-test: PASS")
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.selftest:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
