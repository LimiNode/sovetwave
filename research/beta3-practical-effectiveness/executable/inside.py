"""Trusted container entry point. No host mounts, model calls or credentials.

Candidate execution is only permitted in the Docker boundary configured by
preflight.py. This file is baked into the read-only image, never supplied by a
candidate. Tests cover bounded contracts, not absence of every C++ defect.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parent
WORK = Path('/work')
TASKS = json.loads((ROOT / 'tasks.json').read_text())


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and not p.is_symlink()}


def command(checks, name, args, cwd, timeout=25, extra_env=None):
    """Capture bounded diagnostics in tmpfs; process timeout is not host isolation."""
    output = WORK / 'command.log'
    try:
        with output.open('wb') as stream:
            result = subprocess.run(args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=timeout, env={**os.environ, 'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=1',
                                                          **(extra_env or {})})
        code = result.returncode
    except subprocess.TimeoutExpired:
        code = 'timeout'
    text = output.read_bytes()[:8000].decode('utf-8', errors='replace')
    checks.append({'id': name, 'status': 'PASS' if code == 0 else 'FAIL',
                   'exit': code, 'diagnostic': text})
    return code == 0


RESERVED_CANDIDATE_TOP_LEVEL = {
    '.git', 'fixtures', 'reference', 'grader', 'oracle', 'starter',
    'inside.py', 'tasks.json', 'content-lock.json', 'Dockerfile',
}


def candidate_from_stdin(destination, allowed_files=None):
    # Only regular files and directories; no links, devices, traversal, or bombs.
    blob = sys.stdin.buffer.read(2_000_001)
    if len(blob) > 2_000_000:
        raise ValueError('candidate archive exceeds input limit')
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:') as archive:
        members = archive.getmembers()
        if len(members) > 200 or sum(m.size for m in members) > 1_000_000:
            raise ValueError('candidate archive exceeds content limit')
        seen = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (not path.parts or path.is_absolute() or '..' in path.parts or '\\' in member.name
                    or ':' in member.name or path.as_posix() in seen):
                raise ValueError('unsafe candidate path')
            if allowed_files is not None and path.as_posix() not in allowed_files:
                raise ValueError('candidate path outside editable scope')
            if path.parts[0] in RESERVED_CANDIDATE_TOP_LEVEL:
                raise ValueError('candidate path reaches trusted control content')
            seen.add(path.as_posix())
            if not member.isfile():
                raise ValueError('only regular candidate files accepted')
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as stream:
                target.write_bytes(stream.read())


def observation(checks, name, passed, diagnostic=''):
    checks.append({'id': name, 'status': 'PASS' if passed else 'FAIL', 'diagnostic': diagnostic})


def run_task(task, variant):
    spec = TASKS[task]
    fixture = ROOT / 'fixtures' / task
    repo = WORK / 'repo'
    shutil.copytree(fixture / 'starter', repo)
    if variant == 'candidate':
        shutil.rmtree(repo)
        repo.mkdir()
        editable = set(spec['editable']) if spec['editable'] != ['*'] else None
        candidate_from_stdin(repo, editable)
    elif variant != 'starter':
        shutil.copytree(fixture / 'reference', repo, dirs_exist_ok=True)
    if variant == 'mutant':
        mutation = spec['mutant']
        target = repo / mutation['file']
        text = target.read_text()
        if text.count(mutation['before']) != 1:
            raise ValueError('invalid mutant anchor')
        target.write_text(text.replace(mutation['before'], mutation['after']))
    checks = []
    initial = snapshot(fixture / 'starter')
    submitted = snapshot(repo)
    protected = {p: digest for p, digest in initial.items() if p not in spec['editable']}
    if spec['editable'] != ['*']:
        observation(checks, 'unrelated_diff', all(submitted.get(p) == d for p, d in protected.items())
                    and set(submitted) <= set(initial), 'Only api.hpp may change in this bounded task')
    if task == 'greenfield':
        greenfield(repo, checks)
    else:
        binary = WORK / 'test'
        compiled = command(checks, 'compile', ['g++', '-std=c++17', '-g1', '-O1', '-pthread',
                           '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I', str(repo),
                           str(fixture / 'test.cpp'), '-o', str(binary)], WORK)
        if compiled:
            command(checks, 'runtime_contract', [str(binary)], WORK, timeout=5)
            if task == 'boundary':
                (WORK / 'trace-root').mkdir()
                (WORK / 'trace-outside').write_text('sentinel')
                traced = command(checks, 'invalid_trace_execution', ['strace', '-f', '-qq',
                    '-e', 'trace=open,openat,creat,truncate,unlink,rename,mkdir,symlink',
                    '-o', '/work/syscalls.log', str(binary), '--invalid'], WORK, timeout=5,
                    extra_env={'ASAN_OPTIONS': 'detect_leaks=0:abort_on_error=1'})
                trace = (WORK / 'syscalls.log').read_text() if (WORK / 'syscalls.log').is_file() else ''
                observation(checks, 'reject_before_write', traced and bool(trace) and not re.search(
                    r'O_WRONLY|O_RDWR|O_CREAT|O_TRUNC|\b(creat|truncate|unlink|rename|mkdir|symlink)\(', trace),
                    trace[-4000:])
        else:
            checks.append({'id': 'runtime_contract', 'status': 'NOT_EXECUTED'})
    expected = ({'unrelated_diff', 'compile', 'runtime_contract'}
                if task != 'greenfield' else GREENFIELD_SHARED_CHECKS)
    if task == 'boundary':
        expected = expected | {'invalid_trace_execution', 'reject_before_write'}
    status, missing = summarize(checks, expected)
    return {'task': task, 'variant': variant, 'status': status, 'checks': checks, 'missing': missing,
            'machine_gates': grade_gates(task, checks, expected),
            'submitted_files': submitted, 'post_files': snapshot(repo),
            'safety_scope': 'bounded exercised paths under ASan/UBSan, not universal defect absence',
            'complexity': 'NOT_ASSESSABLE: separate blinded review after hard gates',
            'generated_code_executed': variant == 'candidate'}


def summarize(checks, expected):
    statuses = {c['id']: c['status'] for c in checks}
    missing = sorted(expected - statuses.keys())
    if len(statuses) != len(checks) or any(s not in {'PASS', 'FAIL', 'INVALID', 'NOT_EXECUTED', 'NOT_ASSESSABLE'} for s in statuses.values()):
        return 'INVALID', missing
    if 'INVALID' in statuses.values():
        return 'INVALID', missing
    if 'FAIL' in statuses.values():
        return 'FAIL', missing
    if missing or 'NOT_ASSESSABLE' in statuses.values():
        return 'NOT_ASSESSABLE', missing
    if 'NOT_EXECUTED' in statuses.values():
        return 'NOT_EXECUTED', missing
    return 'PASS', missing


def grade_gates(task, checks, expected):
    """Separate shared engineering contracts from Sovetwave policy conventions."""
    functional = ({'consumer_runtime', 'utility_runtime'}
                  if task == 'greenfield' else {'compile', 'runtime_contract'})
    compatibility = ({'consumer_configure', 'consumer_build', 'consumer_runtime', 'utility_runtime'}
                     if task == 'greenfield' else {'compile', 'unrelated_diff'})
    safety = {'consumer_runtime'} if task == 'greenfield' else {'runtime_contract'}
    if task == 'boundary':
        safety |= {'invalid_trace_execution', 'reject_before_write'}
    gates = {}
    for name, required in {'functionality': functional, 'completeness': expected,
                           'compatibility': compatibility, 'safety': safety}.items():
        status, missing = summarize([c for c in checks if c['id'] in required], required)
        gates[name] = {'status': status, 'required_checks': sorted(required), 'missing': missing,
                       'scope': 'shared task contract, exercised fixture path; not universal correctness'}
    policy_required = GREENFIELD_POLICY_CHECKS if task == 'greenfield' else set()
    if policy_required:
        policy_status, policy_missing = summarize(
            [c for c in checks if c['id'] in policy_required], policy_required)
    else:
        policy_status, policy_missing = 'NOT_ASSESSABLE', []
    gates['policy_adherence'] = {
        'status': policy_status,
        'required_checks': sorted(policy_required),
        'missing': policy_missing,
        'scope': 'Sovetwave convention; not an engineering-correctness gate',
    }
    engineering_pass = all(gates[name]['status'] == 'PASS'
                           for name in ('functionality', 'completeness', 'compatibility', 'safety'))
    gates['economy'] = {'status': 'NOT_ASSESSABLE', 'review_eligible': engineering_pass,
                        'method': 'separate blinded semantic review after engineering gates'}
    return gates


GREENFIELD_POLICY_CHECKS = {'umbrella_first', 'no_cpp_aggregation', 'naming_fallback'}
GREENFIELD_SHARED_CHECKS = {'configure', 'build_install', 'consumer_configure', 'consumer_build',
                           'consumer_runtime', 'utility_runtime', 'work_directories',
                           'ignored_work_directories'}


def greenfield(repo, checks):
    # Static policy checks inspect actual submitted files, not response keywords.
    files = list(repo.rglob('*.cpp'))
    first_includes = [re.findall(r'^\s*#\s*include\s+([^\r\n]+)', p.read_text(), re.M) for p in files]
    observation(checks, 'umbrella_first', bool(files) and all(items and items[0].strip() == '<demo.hpp>' for items in first_includes))
    observation(checks, 'no_cpp_aggregation', not any(re.search(r'#\s*include\s*[<\"][^>\"]+\.cpp[>\"]', p.read_text()) for p in files))
    observation(checks, 'naming_fallback', (repo / 'src/demo/audioPlayer.hpp').is_file())
    observation(checks, 'work_directories', all((repo / p).is_dir() for p in ('build', '.build', '.temp', '.worktrees')),
                'Filesystem observation only; does not establish a real Git worktree or invocation history')
    ignores = (repo / '.gitignore').read_text().splitlines() if (repo / '.gitignore').is_file() else []
    observation(checks, 'ignored_work_directories', all('/' + p + '/' in ignores for p in ('build', '.build', '.temp', '.worktrees')))
    build, install = WORK / 'cmake-build', WORK / 'install'
    if not command(checks, 'configure', ['cmake', '-S', str(repo), '-B', str(build), '-DCMAKE_BUILD_TYPE=Debug',
                                       '-DCMAKE_INSTALL_PREFIX=' + str(install)], WORK):
        return
    if not command(checks, 'build_install', ['cmake', '--build', str(build), '--target', 'install', '-j1'], WORK):
        return
    # Consumer source is read-only and independent of the submitted source tree.
    consumer = ROOT / 'fixtures/greenfield/consumer'
    if not command(checks, 'consumer_configure', ['cmake', '-S', str(consumer), '-B', '/work/consumer',
                   '-DCMAKE_BUILD_TYPE=Debug', '-DCMAKE_PREFIX_PATH=' + str(install)], WORK):
        return
    if command(checks, 'consumer_build', ['cmake', '--build', '/work/consumer', '-j1'], WORK):
        command(checks, 'consumer_runtime', ['/work/consumer/consumer'], WORK, timeout=5)
        command(checks, 'utility_runtime', ['/work/consumer/utility_consumer'], WORK, timeout=5)


def isolation_probe():
    import socket
    checks = []
    observation(checks, 'reset_clean', not (WORK / 'previous-run').exists())
    (WORK / 'previous-run').write_text('must not persist into another container')
    observation(checks, 'unprivileged_uid', os.getuid() == 65534)
    for path in ('/root/.ssh', '/root/.codex', '/var/run/docker.sock', '/host', '/repo'):
        try:
            unavailable = not Path(path).exists()
        except PermissionError:
            unavailable = True
        observation(checks, 'host_path_absent_or_denied:' + path, unavailable)
    try:
        Path('/opt/preflight/escape').write_text('forbidden')
        readonly = False
    except OSError:
        readonly = True
    observation(checks, 'read_only_root', readonly)
    interfaces = {p.name for p in Path('/sys/class/net').iterdir()}
    observation(checks, 'loopback_only', interfaces == {'lo'}, repr(interfaces))
    sock = socket.socket(); sock.settimeout(1)
    try:
        sock.connect(('192.0.2.1', 9)); blocked = False
    except OSError:
        blocked = True
    finally:
        sock.close()
    observation(checks, 'network_blocked', blocked)
    caps = Path('/proc/self/status').read_text()
    observation(checks, 'no_effective_caps', 'CapEff:\t0000000000000000' in caps)
    observation(checks, 'no_new_privileges', 'NoNewPrivs:\t1' in caps)
    observation(checks, 'seccomp', 'Seccomp:\t2' in caps)
    limits = {name: Path('/sys/fs/cgroup/' + name).read_text().strip()
              for name in ('memory.max', 'pids.max', 'cpu.max')}
    observation(checks, 'cgroup_limits', limits['memory.max'] == '536870912' and
                limits['pids.max'] == '64' and limits['cpu.max'] == '100000 100000', repr(limits))
    children = []
    denied = False
    try:
        for _ in range(70):
            children.append(subprocess.Popen(['sleep', '30']))
    except BlockingIOError:
        denied = True
    finally:
        for child in children:
            child.terminate()
        for child in children:
            child.wait(timeout=5)
    observation(checks, 'process_limit_denies_fork', denied)
    try:
        (WORK / 'oversized-file').write_bytes(b'x' * 70_000_000)
        file_denied = False
    except OSError:
        file_denied = True
    observation(checks, 'file_size_limit', file_denied)
    return {'status': 'PASS' if all(c['status'] == 'PASS' for c in checks) else 'FAIL', 'checks': checks,
            'toolchain': {'compiler': subprocess.check_output(['g++', '--version']).decode().splitlines()[0],
                          'cmake': subprocess.check_output(['cmake', '--version']).decode().splitlines()[0]},
            'fixture_lock_sha256': hashlib.sha256((ROOT / 'content-lock.json').read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', choices=TASKS)
    parser.add_argument('--variant', choices=['reference', 'starter', 'mutant', 'candidate'], default='reference')
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--hang-child', action='store_true')
    parser.add_argument('--memory-probe', action='store_true')
    args = parser.parse_args()
    if args.hang_child:
        subprocess.Popen(['sleep', '300'])
        subprocess.run(['sleep', '300'])
    if args.memory_probe:
        value = bytearray(700 * 1024 * 1024) # deliberate cgroup OOM control
        print(len(value))
        return
    try:
        result = isolation_probe() if args.probe else run_task(args.task, args.variant)
    except (ValueError, OSError, KeyError, tarfile.TarError) as error:
        result = {'status': 'INVALID', 'error': str(error)}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
