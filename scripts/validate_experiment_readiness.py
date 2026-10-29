"""Validate the offline Experiment Readiness manifest without model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "research" / "experiment-readiness-manifest.json"
OVERLAY = ROOT / "research" / "experiment-readiness-minimal-ladder.md"
EXPECTED_ARMS = {"baseline", "sovetwave-frozen", "sovetwave-explicit-ladder"}


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def validate_manifest(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest or load_manifest()
    assert manifest["schema_version"] == 1
    assert manifest["status"] == "dry_run_ready_not_executed"
    assert _canonical_hash(manifest["task_contract"]) == manifest["harness"]["task_contract_sha256"]
    assert _file_hash(OVERLAY) == manifest["arms"][2]["overlay_sha256"]

    arms = manifest["arms"]
    assert {arm["id"] for arm in arms} == EXPECTED_ARMS
    assert len(arms) == len(EXPECTED_ARMS)
    assert arms[0]["skill_tree_sha256"] is None
    assert arms[1]["skill_tree_sha256"] == arms[2]["skill_tree_sha256"]
    assert manifest["shared_runtime"]["binding_status"].startswith("required before execution")

    expected_calls = len(manifest["task_contract"]) * len(arms) * manifest["allocation"]["repetitions_per_arm"]
    assert expected_calls == manifest["allocation"]["maximum_model_calls"]
    assert EXPECTED_ARMS.issubset(manifest["activation_evidence"])
    assert manifest["unavailable_policy"]["missing_model_or_host_binding"] == "not_executed"

    recorded_revision = manifest["harness"]["frozen_reference_revision"]
    observed_skill_hash = _git_skill_tree_hash(recorded_revision)
    if observed_skill_hash is not None:
        assert observed_skill_hash == arms[1]["skill_tree_sha256"]
    return {
        "task_contract_sha256": manifest["harness"]["task_contract_sha256"],
        "overlay_sha256": manifest["arms"][2]["overlay_sha256"],
        "skill_tree_hash_verified": observed_skill_hash is not None,
        "model_calls": 0,
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="validate the checked-in dry-run manifest")
    args = parser.parse_args()
    result = validate_manifest()
    if args.selftest:
        print("Experiment readiness manifest self-test: PASS")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
