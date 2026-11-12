"""Model-free candidate transfer preflight.

This module does not start an agent and does not execute a candidate.  It models
the trusted controller boundary that must exist before a real host is attached:
the mock agent can write only a candidate archive, the transfer is immutable and
hash-checked, and trusted control files are rejected at admission.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
EXEC = ROOT / 'executable'
TASKS = json.loads((EXEC / 'tasks.json').read_text(encoding='utf-8'))
MAX_ARCHIVE_BYTES = 2_000_000
MAX_MEMBER_BYTES = 1_000_000
MAX_MEMBERS = 200
RESERVED_TOP_LEVEL = {
    '.git', 'fixtures', 'reference', 'grader', 'oracle', 'starter',
    'inside.py', 'tasks.json', 'content-lock.json', 'Dockerfile',
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if (not path.parts or path.is_absolute() or '..' in path.parts or '\\' in name
            or ':' in name or path.parts[0] in RESERVED_TOP_LEVEL):
        raise ValueError('unsafe candidate path')
    return path.as_posix()


def build_archive(files: dict[str, bytes]) -> bytes:
    """Create a deterministic regular-file-only tar stream for a mock agent."""
    if not files or len(files) > MAX_MEMBERS:
        raise ValueError('invalid candidate file count')
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:') as archive:
        for name in sorted(files):
            safe = _safe_name(name)
            payload = bytes(files[name])
            if len(payload) > MAX_MEMBER_BYTES:
                raise ValueError('candidate file exceeds input limit')
            member = tarfile.TarInfo(safe)
            member.size = len(payload)
            member.mode = 0o644
            member.uid = member.gid = 0
            member.uname = member.gname = ''
            member.mtime = 0
            archive.addfile(member, io.BytesIO(payload))
    blob = output.getvalue()
    if len(blob) > MAX_ARCHIVE_BYTES:
        raise ValueError('candidate archive exceeds input limit')
    return blob


def inspect_archive(blob: bytes, task: str) -> dict:
    """Validate an agent transfer without extracting or executing it."""
    if task not in TASKS:
        raise ValueError('unknown task')
    if not blob or len(blob) > MAX_ARCHIVE_BYTES:
        raise ValueError('candidate archive exceeds input limit')
    allowed = set(TASKS[task]['editable'])
    files = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode='r:') as archive:
            members = archive.getmembers()
            if not members or len(members) > MAX_MEMBERS:
                raise ValueError('invalid candidate member count')
            for member in members:
                name = _safe_name(member.name)
                if not member.isfile():
                    raise ValueError('only regular candidate files accepted')
                if allowed != {'*'} and name not in allowed:
                    raise ValueError('candidate path outside editable scope')
                if member.size > MAX_MEMBER_BYTES:
                    raise ValueError('candidate file exceeds input limit')
                if name in files:
                    raise ValueError('duplicate candidate path')
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError('candidate content unavailable')
                payload = stream.read(MAX_MEMBER_BYTES + 1)
                if len(payload) != member.size:
                    raise ValueError('incomplete candidate member')
                files[name] = _digest(payload)
    except (tarfile.TarError, EOFError) as error:
        raise ValueError('malformed candidate archive') from error
    return {'task': task, 'archive_sha256': _digest(blob), 'files': files,
            'member_count': len(files)}


def transfer_manifest(task: str, archive: bytes) -> dict:
    inspected = inspect_archive(archive, task)
    return {'schema_version': 1, 'task': task, 'archive_sha256': inspected['archive_sha256'],
            'files': inspected['files'], 'member_count': inspected['member_count'],
            'generated_code_executed': False, 'model_calls': 0}


def verify_transfer(task: str, archive: bytes, manifest: dict) -> dict:
    """Fail closed if bytes or the declared file map change in transit."""
    inspected = inspect_archive(archive, task)
    expected = transfer_manifest(task, archive)
    if manifest != expected:
        raise ValueError('candidate transfer manifest mismatch')
    return {'status': 'PASS', 'manifest': expected, 'candidate_execution': 'NOT_EXECUTED'}


def validate_completion(record: dict) -> dict:
    """Validate controller-side completion metadata before accepting results."""
    if record.get('output_bytes', 0) > MAX_ARCHIVE_BYTES:
        raise ValueError('output limit exceeded')
    if record.get('child_pids'):
        raise ValueError('background processes remain')
    if not record.get('artifact_complete', False):
        raise ValueError('incomplete artifact transfer')
    if record.get('timed_out', False):
        return {'status': 'TIMEOUT', 'candidate_execution': 'TERMINATED'}
    return {'status': 'PASS', 'candidate_execution': 'NOT_EXECUTED'}


def clean_agent_environment(workspace: Path, base: dict[str, str] | None = None) -> dict[str, str]:
    """Return an allowlisted environment; this is not proof of host cleanliness."""
    source = base or {}
    path = source.get('PATH', os.environ.get('PATH', ''))
    return {
        'PATH': path,
        'LANG': 'C',
        'LC_ALL': 'C',
        'HOME': str(workspace / 'home'),
        'USERPROFILE': str(workspace / 'home'),
        'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_CONFIG_GLOBAL': os.devnull,
        'GIT_TERMINAL_PROMPT': '0',
        'CLAUDE_CONFIG_DIR': str(workspace / 'claude-config'),
    }


def clean_workspace_status(workspace: Path) -> dict:
    """Check the local workspace boundary; host-global configuration stays unknown."""
    forbidden = [workspace / '.agents' / 'skills' / 'sovetwave',
                 workspace / '.claude' / 'skills' / 'sovetwave', workspace / 'AGENTS.md']
    return {'status': 'PASS' if not any(path.exists() for path in forbidden) else 'FAIL',
            'checked_paths': [str(path.relative_to(workspace)) for path in forbidden],
            'host_global_configuration': 'NOT_ASSESSABLE'}


def selftest() -> dict:
    """Exercise transfer integrity and clean-environment construction only."""
    checks = []
    with tempfile.TemporaryDirectory(prefix='sovetwave-bridge-') as directory:
        workspace = Path(directory)
        env = clean_agent_environment(workspace, {'PATH': '/mock/bin', 'SECRET': 'must-not-forward'})
        checks.append({'id': 'allowlisted_environment', 'status': 'PASS' if 'SECRET' not in env else 'FAIL'})
        checks.append({'id': 'workspace_config_roots', 'status': 'PASS' if all(
            str(workspace) in env[key] for key in ('HOME', 'USERPROFILE', 'CLAUDE_CONFIG_DIR')) else 'FAIL'})
        checks.append({'id': 'clean_workspace', 'status': clean_workspace_status(workspace)['status']})
        archive = build_archive({'api.hpp': b'#pragma once\n'})
        manifest = transfer_manifest('ownership', archive)
        verify_transfer('ownership', archive, manifest)
        checks.append({'id': 'valid_transfer', 'status': 'PASS'})
        checks.append({'id': 'forged_bytes_rejected', 'status': 'PASS' if _forged_rejected('ownership', archive, manifest) else 'FAIL'})
        checks.append({'id': 'missing_manifest_rejected', 'status': 'PASS' if _missing_rejected('ownership', archive, manifest) else 'FAIL'})
        checks.append({'id': 'oracle_path_rejected', 'status': 'PASS' if _path_rejected('ownership', {'inside.py': b'x'}) else 'FAIL'})
        checks.append({'id': 'incomplete_archive_rejected', 'status': 'PASS' if _incomplete_rejected('ownership', archive, manifest) else 'FAIL'})
        checks.append({'id': 'background_process_rejected', 'status': 'PASS' if _completion_rejected({'artifact_complete': True, 'child_pids': [42]}) else 'FAIL'})
        checks.append({'id': 'output_flood_rejected', 'status': 'PASS' if _completion_rejected({'artifact_complete': True, 'output_bytes': MAX_ARCHIVE_BYTES + 1}) else 'FAIL'})
        checks.append({'id': 'interrupted_transfer_rejected', 'status': 'PASS' if _completion_rejected({'artifact_complete': False}) else 'FAIL'})
        checks.append({'id': 'timeout_cleanup_contract', 'status': 'PASS' if _timeout_contract() else 'FAIL'})
    return {'status': 'PASS' if all(row['status'] == 'PASS' for row in checks) else 'FAIL',
            'checks': checks, 'model_calls': 0, 'candidate_execution': 'NOT_EXECUTED',
            'host_execution': 'NOT_IMPLEMENTED', 'grader_tamper_resistance': 'NOT_ASSESSABLE'}


def _forged_rejected(task, archive, manifest):
    try:
        verify_transfer(task, archive + b'x', manifest)
    except ValueError:
        return True
    return False


def _missing_rejected(task, archive, manifest):
    altered = dict(manifest)
    altered['files'] = {}
    try:
        verify_transfer(task, archive, altered)
    except ValueError:
        return True
    return False


def _path_rejected(task, files):
    try:
        inspect_archive(build_archive(files), task)
    except ValueError:
        return True
    return False


def _incomplete_rejected(task, archive, manifest):
    try:
        verify_transfer(task, archive[:max(1, len(archive) // 2)], manifest)
    except ValueError:
        return True
    return False


def _completion_rejected(record):
    try:
        validate_completion(record)
    except ValueError:
        return True
    return False


def _timeout_contract():
    try:
        return validate_completion({'artifact_complete': True, 'timed_out': True}) == {
            'status': 'TIMEOUT', 'candidate_execution': 'TERMINATED'}
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if not args.selftest:
        parser.error('--selftest is the only model-free operation')
    result = selftest()
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
