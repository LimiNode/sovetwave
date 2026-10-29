"""Grade repository-grounded trusted fixtures without executing generated code."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "research" / "experiment-fixtures"
FIXTURE_FILES = {
    "contract": FIXTURE_ROOT / "contract-coding-task.json",
    "reuse": FIXTURE_ROOT / "reuse-helper-task.json",
    "security": FIXTURE_ROOT / "security-negative-task.json",
}
EXECUTION_MODE = "offline_structured_fixtures_only"


def load_fixture(kind: str) -> dict[str, Any]:
    try:
        path = FIXTURE_FILES[kind]
    except KeyError as error:
        raise ValueError(f"unknown fixture kind: {kind}") from error
    return json.loads(path.read_text(encoding="utf-8"))


def _repository_target_errors(fixture: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root = ROOT.resolve()
    for target in fixture.get("repository_targets", []):
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
        marker = target.get("required_marker")
        if not isinstance(marker, str) or marker not in path.read_text(encoding="utf-8"):
            errors.append(f"repository target marker is absent: {relative}::{marker}")
    return errors


def _result(status: str, findings: list[str], *, fixture_id: str) -> dict[str, Any]:
    return {"fixture_id": fixture_id, "status": status, "findings": findings}


def grade_contract(fixture: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    findings = _repository_target_errors(fixture)
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
    return _result("pass" if not findings else "reject", findings, fixture_id=fixture["id"])


def grade_reuse(fixture: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    findings = _repository_target_errors(fixture)
    contract = fixture["contract"]
    if candidate.get("route") != contract["required_route"]:
        findings.append("candidate did not select the existing-helper route")
    if candidate.get("helper") != contract["existing_helper"]:
        findings.append("candidate did not name the repository helper")
    if candidate.get("new_helper") != contract["new_helper_allowed"]:
        findings.append("candidate introduced a new helper despite the reuse contract")
    return _result("pass" if not findings else "reject", findings, fixture_id=fixture["id"])


def grade_security(fixture: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    findings = _repository_target_errors(fixture)
    contract = fixture["contract"]
    if candidate.get("accepted") != contract["accepted"]:
        findings.append("unsafe fixture path was not rejected")
    if candidate.get("side_effects") != contract["side_effects"]:
        findings.append("side effects were observed before the boundary rejection")
    if candidate.get("reason") != contract["reason"]:
        findings.append("boundary rejection reason is not stable")
    return _result("pass" if not findings else "reject", findings, fixture_id=fixture["id"])


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
    return {"execution_mode": EXECUTION_MODE, "model_calls": 0, "results": results}


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
