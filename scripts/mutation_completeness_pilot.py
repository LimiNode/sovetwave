"""Deterministic, offline mutation and completeness pilot.

The pilot evaluates trusted structured reference outputs rather than executing
generated source code.  This keeps the self-test useful on an ordinary
developer machine while making the isolation boundary explicit: a future
grader must classify untrusted-code mutations as ``not_executed`` until a
separate sandbox contract exists.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable


STATUS_KILLED = "killed"
STATUS_SURVIVED = "survived"
STATUS_INVALID = "invalid_mutant"
STATUS_NOT_EXECUTED = "not_executed"


TASK_CONTRACT: dict[str, Any] = {
    "id_map_contract": {
        "success_ids": ["a", "b", "c"],
        "expected_values": {"a": 10, "b": 20, "c": 30},
        "success": {"status": "ok", "error_code": None},
        "rejection": {"status": "error", "items": [], "error_code": "unknown_id"},
    },
    "safe_path_contract": {
        "safe_path": "workspace/notes.txt",
        "unsafe_path": "../secrets.txt",
        "success": {"status": "written", "side_effect": True},
        "rejection": {"status": "blocked", "side_effect": False, "reason": "outside_root"},
    },
}


@dataclass(frozen=True)
class Candidate:
    """A trusted fixture result and the metrics reported for that fixture."""

    name: str
    outputs: dict[str, dict[str, dict[str, Any]]]
    loc: int
    independent_invariants: int


@dataclass(frozen=True)
class Finding:
    task_id: str
    axis: str
    message: str


@dataclass(frozen=True)
class MutationSpec:
    mutation_id: str
    description: str
    apply: Callable[[Candidate], Candidate | None] | None
    execution_allowed: bool = True


def contract_hash() -> str:
    payload = json.dumps(TASK_CONTRACT, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _candidate_outputs() -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "id_map_contract": {
            "success": {
                "status": "ok",
                "items": [
                    {"id": "a", "value": 10},
                    {"id": "b", "value": 20},
                    {"id": "c", "value": 30},
                ],
                "error_code": None,
            },
            "rejection": {"status": "error", "items": [], "error_code": "unknown_id"},
        },
        "safe_path_contract": {
            "success": {
                "status": "written",
                "path": "workspace/notes.txt",
                "side_effect": True,
            },
            "rejection": {
                "status": "blocked",
                "path": "../secrets.txt",
                "side_effect": False,
                "reason": "outside_root",
            },
        },
    }


def reference_candidates() -> dict[str, Candidate]:
    good_outputs = _candidate_outputs()
    incomplete_outputs = copy.deepcopy(good_outputs)
    incomplete_outputs["id_map_contract"]["success"]["items"].pop()

    contract_violation_outputs = copy.deepcopy(good_outputs)
    contract_violation_outputs["id_map_contract"]["rejection"].pop("error_code")

    success_error_outputs = copy.deepcopy(good_outputs)
    success_error_outputs["id_map_contract"]["success"]["error_code"] = "unexpected"

    unsafe_outputs = copy.deepcopy(good_outputs)
    unsafe_outputs["safe_path_contract"]["rejection"].update(
        {"status": "written", "side_effect": True, "reason": "outside_root"}
    )

    return {
        "good": Candidate("good", good_outputs, loc=42, independent_invariants=4),
        "incomplete": Candidate("incomplete", incomplete_outputs, loc=18, independent_invariants=1),
        "contract_violation": Candidate("contract_violation", contract_violation_outputs, loc=39, independent_invariants=3),
        "success_error_code": Candidate("success_error_code", success_error_outputs, loc=41, independent_invariants=3),
        "unsafe": Candidate("unsafe", unsafe_outputs, loc=36, independent_invariants=3),
    }


def _check_id_map(outputs: dict[str, dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    success = outputs["success"]
    required = {"status", "items", "error_code"}
    if not required.issubset(success):
        findings.append(Finding("id_map_contract", "required_output", "success output is missing a required field"))
    if success.get("status") != "ok":
        findings.append(Finding("id_map_contract", "contract", "success result does not preserve status=ok"))
    if success.get("error_code") is not None:
        findings.append(Finding("id_map_contract", "contract", "successful result must carry error_code=None"))
    items = success.get("items")
    if not isinstance(items, list):
        findings.append(Finding("id_map_contract", "required_output", "success items must be a list"))
        items = []
    expected_ids = TASK_CONTRACT["id_map_contract"]["success_ids"]
    actual_ids = [item.get("id") for item in items if isinstance(item, dict)]
    if actual_ids != expected_ids:
        findings.append(Finding("id_map_contract", "boundary", "success result must contain every required id exactly once"))
    expected_values = TASK_CONTRACT["id_map_contract"]["expected_values"]
    for item in items:
        if isinstance(item, dict) and expected_values.get(item.get("id")) != item.get("value"):
            findings.append(Finding("id_map_contract", "identifier_mapping", "id-to-value mapping is incorrect"))
    rejection = outputs["rejection"]
    if not required.issubset(rejection):
        findings.append(Finding("id_map_contract", "required_output", "rejection output is missing a required field"))
    if rejection != TASK_CONTRACT["id_map_contract"]["rejection"]:
        findings.append(Finding("id_map_contract", "error_handling", "unknown id must be rejected with the stable error contract"))
    return findings


def _check_safe_path(outputs: dict[str, dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    success = outputs["success"]
    expected_success = TASK_CONTRACT["safe_path_contract"]["success"]
    if any(success.get(key) != value for key, value in expected_success.items()):
        findings.append(Finding("safe_path_contract", "contract", "safe path result does not preserve the write contract"))
    if success.get("path") != TASK_CONTRACT["safe_path_contract"]["safe_path"]:
        findings.append(Finding("safe_path_contract", "boundary", "safe result escaped the repository root"))
    rejection = outputs["rejection"]
    expected_rejection = TASK_CONTRACT["safe_path_contract"]["rejection"]
    if any(rejection.get(key) != value for key, value in expected_rejection.items()):
        findings.append(Finding("safe_path_contract", "security", "outside-root path must be blocked before side effect"))
    return findings


def evaluate_candidate(candidate: Candidate) -> dict[str, Any]:
    findings = _check_id_map(candidate.outputs["id_map_contract"])
    findings.extend(_check_safe_path(candidate.outputs["safe_path_contract"]))
    axes = {"required_output": True, "contract": True, "boundary": True, "identifier_mapping": True, "error_handling": True, "security": True}
    for finding in findings:
        axes[finding.axis] = False
    return {
        "candidate": candidate.name,
        "status": "pass" if not findings else "reject",
        "findings": [finding.__dict__ for finding in findings],
        "completeness": {
            "requirements_complete": axes["required_output"] and axes["boundary"] and axes["identifier_mapping"],
            "public_contract_preserved": axes["contract"],
            "negative_scenarios": axes["error_handling"] and axes["security"],
            "error_handling_preserved": axes["error_handling"],
            "security_checks_preserved": axes["security"],
        },
        "metrics": {
            "loc": candidate.loc,
            "independent_invariants": candidate.independent_invariants,
        },
    }


def _drop_boundary(candidate: Candidate) -> Candidate:
    outputs = copy.deepcopy(candidate.outputs)
    outputs["id_map_contract"]["success"]["items"].pop()
    return replace(candidate, name=f"{candidate.name}:drop-boundary", outputs=outputs)


def _wrong_error(candidate: Candidate) -> Candidate:
    outputs = copy.deepcopy(candidate.outputs)
    outputs["id_map_contract"]["rejection"]["status"] = "ok"
    return replace(candidate, name=f"{candidate.name}:wrong-error", outputs=outputs)


def _swap_mapping(candidate: Candidate) -> Candidate:
    outputs = copy.deepcopy(candidate.outputs)
    items = outputs["id_map_contract"]["success"]["items"]
    items[0]["value"], items[1]["value"] = items[1]["value"], items[0]["value"]
    return replace(candidate, name=f"{candidate.name}:swap-identifiers", outputs=outputs)


def _remove_required_output(candidate: Candidate) -> Candidate:
    outputs = copy.deepcopy(candidate.outputs)
    outputs["id_map_contract"]["rejection"].pop("error_code")
    return replace(candidate, name=f"{candidate.name}:drop-output", outputs=outputs)


def _remove_security_check(candidate: Candidate) -> Candidate:
    outputs = copy.deepcopy(candidate.outputs)
    outputs["safe_path_contract"]["rejection"].update({"status": "written", "side_effect": True})
    return replace(candidate, name=f"{candidate.name}:drop-security-check", outputs=outputs)


def _add_unobserved_output(candidate: Candidate) -> Candidate:
    outputs = copy.deepcopy(candidate.outputs)
    outputs["id_map_contract"]["success"]["diagnostic"] = "extra-but-allowed"
    return replace(candidate, name=f"{candidate.name}:extra-output", outputs=outputs)


def _malformed_structure(candidate: Candidate) -> Candidate:
    outputs = copy.deepcopy(candidate.outputs)
    outputs["id_map_contract"]["success"] = ["not", "an", "output-object"]
    return replace(candidate, name=f"{candidate.name}:malformed", outputs=outputs)


def mutation_specs() -> list[MutationSpec]:
    return [
        MutationSpec("missing-boundary-check", "omit the last required item", _drop_boundary),
        MutationSpec("incorrect-error-handling", "turn a rejected input into success", _wrong_error),
        MutationSpec("incorrect-identifier-mapping", "swap two identifier values", _swap_mapping),
        MutationSpec("missing-required-output", "remove a required error field", _remove_required_output),
        MutationSpec("removed-security-check", "allow an outside-root side effect", _remove_security_check),
        MutationSpec("unobserved-extra-output", "add an output field outside this contract", _add_unobserved_output),
        MutationSpec("equivalent-no-op", "attempt a mutation that changes no trusted fixture", lambda candidate: candidate),
        MutationSpec("malformed-fixture", "replace an output object with an invalid structure", _malformed_structure),
        MutationSpec(
            "untrusted-generated-code",
            "execute a generated-code mutation only inside a future isolated grader",
            None,
            execution_allowed=False,
        ),
    ]


def run_mutation(spec: MutationSpec, candidate: Candidate) -> dict[str, Any]:
    if not spec.execution_allowed:
        return {"mutation_id": spec.mutation_id, "description": spec.description, "status": STATUS_NOT_EXECUTED, "reason": "isolation boundary is not established"}
    if spec.apply is None:
        return {"mutation_id": spec.mutation_id, "description": spec.description, "status": STATUS_INVALID, "reason": "no mutation operator"}
    try:
        mutated = spec.apply(candidate)
    except (AttributeError, KeyError, IndexError, TypeError, ValueError) as error:
        return {
            "mutation_id": spec.mutation_id,
            "description": spec.description,
            "status": STATUS_INVALID,
            "reason": f"mutation operator failed: {type(error).__name__}",
        }
    if mutated is None or mutated.outputs == candidate.outputs:
        return {"mutation_id": spec.mutation_id, "description": spec.description, "status": STATUS_INVALID, "reason": "operator did not produce a distinct fixture"}
    if not isinstance(mutated, Candidate):
        return {"mutation_id": spec.mutation_id, "description": spec.description, "status": STATUS_INVALID, "reason": "operator did not return a Candidate"}
    try:
        evaluation = evaluate_candidate(mutated)
    except (AttributeError, KeyError, IndexError, TypeError, ValueError) as error:
        return {
            "mutation_id": spec.mutation_id,
            "description": spec.description,
            "status": STATUS_INVALID,
            "reason": f"mutated fixture is structurally invalid: {type(error).__name__}",
        }
    return {
        "mutation_id": spec.mutation_id,
        "description": spec.description,
        "status": STATUS_KILLED if evaluation["status"] == "reject" else STATUS_SURVIVED,
        "evaluation": evaluation,
    }


def experiment_manifest() -> dict[str, Any]:
    return {
        "status": "planned",
        "task_contract_sha256": contract_hash(),
        "arms": [
            {"id": "baseline", "skill_variant": "none", "status": "planned"},
            {"id": "sovetwave-frozen", "skill_variant": "frozen reference", "status": "planned"},
            {"id": "sovetwave-explicit-ladder", "skill_variant": "experimental explicit minimal-solution ladder", "status": "planned"},
        ],
        "controls": {
            "task_contract": "identical across arms",
            "tool_permissions": "must be fixed identically before any model run",
            "environment": "must be fixed identically before any model run",
            "model": "must be fixed identically before any model run",
        },
        "decision_rule": "Do not claim an efficiency or completeness benefit until correctness, mutation-kill, and completeness results are available for all compared arms.",
    }


def build_report() -> dict[str, Any]:
    candidates = reference_candidates()
    return {
        "schema_version": 1,
        "execution_mode": "offline_trusted_fixtures_only",
        "task_contract_sha256": contract_hash(),
        "reference_results": [evaluate_candidate(candidate) for candidate in candidates.values()],
        "mutation_results": [run_mutation(spec, candidates["good"]) for spec in mutation_specs()],
        "experiment_manifest": experiment_manifest(),
    }


def selftest() -> dict[str, Any]:
    report = build_report()
    references = {item["candidate"]: item for item in report["reference_results"]}
    assert references["good"]["status"] == "pass"
    for name in ("incomplete", "contract_violation", "success_error_code", "unsafe"):
        assert references[name]["status"] == "reject", name
    assert any(
        finding["axis"] == "contract" and "error_code=None" in finding["message"]
        for finding in references["success_error_code"]["findings"]
    )
    statuses = {item["mutation_id"]: item["status"] for item in report["mutation_results"]}
    for mutation_id in (
        "missing-boundary-check",
        "incorrect-error-handling",
        "incorrect-identifier-mapping",
        "missing-required-output",
        "removed-security-check",
    ):
        assert statuses[mutation_id] == STATUS_KILLED, mutation_id
    assert statuses["equivalent-no-op"] == STATUS_INVALID
    assert statuses["malformed-fixture"] == STATUS_INVALID
    assert statuses["unobserved-extra-output"] == STATUS_SURVIVED
    assert statuses["untrusted-generated-code"] == STATUS_NOT_EXECUTED
    assert report["experiment_manifest"]["status"] == "planned"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run deterministic checks")
    parser.add_argument("--report", type=Path, help="write the deterministic report as JSON")
    args = parser.parse_args()
    report = selftest() if args.selftest else build_report()
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.selftest:
        print("Mutation/completeness pilot self-test: PASS")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
