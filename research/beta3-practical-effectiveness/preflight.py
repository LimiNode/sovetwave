"""Offline fixture/oracle preparation. Never launches a model or agent CLI.

Only Docker may execute C++ here; there is deliberately no local-shell fallback.
Use --offline for digest checks, --build-image for toolchain provisioning, then
--selftest --image sha256:... for the trusted-control suite. No candidate CLI is
exposed until the model-host execution bridge has been reviewed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXEC = ROOT / 'executable'
TASKS = json.loads((EXEC / 'tasks.json').read_text(encoding='utf-8'))


def git_bytes(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)


def skill_identity(revision, separator=b'\0'):
    """Exact Git blob bytes, never text-mode shell output or checkout newlines."""
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('full commit identity required')
    paths = git_bytes('ls-tree', '-r', '--name-only', revision, 'skills/sovetwave/').decode().splitlines()
    if not paths:
        raise ValueError('missing skill tree')
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.encode('utf-8') + separator + git_bytes('show', revision + ':' + path) + separator)
    return {'commit': revision, 'file_count': len(paths), 'sha256': digest.hexdigest(),
            'separator_hex': separator.hex(), 'path_scope': 'repository_relative'}


def file_inventory():
    return {p.relative_to(EXEC).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(EXEC.rglob('*')) if p.is_file() and p.relative_to(EXEC).parts[0] != '.temp'
            and '__pycache__' not in p.parts and p.name != 'content-lock.json'}


def prepare(task, destination):
    """Materialize a new synthetic Git repository; never resets an existing one."""
    destination = destination.resolve()
    base = (EXEC / '.temp').resolve()
    if not destination.is_relative_to(base) or destination == base or destination.exists():
        raise ValueError('prepare requires a new task directory below executable/.temp')
    source = EXEC / 'fixtures' / task / 'starter'
    shutil.copytree(source, destination)
    (destination / 'TASK.md').write_text(TASKS[task]['prompt'] + '\n', encoding='utf-8', newline='\n')
    env = {**{key: value for key, value in os.environ.items() if not key.startswith('GIT_')},
           'GIT_AUTHOR_DATE': '2026-11-11T00:00:00Z', 'GIT_COMMITTER_DATE': '2026-11-11T00:00:00Z',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}
    for args in (['init', '-b', 'task'], ['add', '.'],
                 ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                  '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=' + os.devnull, 'commit', '-m', 'Initial fixture']):
        subprocess.run(['git', *args], cwd=destination, env=env, check=True, capture_output=True)
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=destination, env=env).decode().strip()


def allocation(seed=20261111):
    """Three complete repetitions; invert arm order by task/repetition."""
    rng = random.Random(seed)
    rows = []
    subsets = {'primary': list(TASKS), 'natural': ['brownfield', 'greenfield'],
               'grounded': ['ownership', 'boundary']}
    for subset, tasks in subsets.items():
        shuffled = list(tasks); rng.shuffle(shuffled)
        for index, task in enumerate(shuffled):
            for repetition in range(1, 4):
                arms = ['baseline', 'combined'] if (index + repetition) % 2 else ['combined', 'baseline']
                for position, arm in enumerate(arms, 1):
                    rows.append({'sequence': len(rows) + 1, 'experiment': subset,
                                 'task': task, 'repetition': repetition, 'arm': arm,
                                 'position': position})
    return rows


def validate_pairs(rows):
    seen, pairs = set(), {}
    for row in rows:
        key = (row['experiment'], row['task'], row['repetition'], row['arm'])
        if key in seen:
            raise ValueError('duplicate observation identity')
        seen.add(key)
        pairs.setdefault(key[:-1], set()).add(key[-1])
    if any(arms != {'baseline', 'combined'} for arms in pairs.values()):
        raise ValueError('missing paired arm')
    return len(pairs)


def offline():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    identities = {key: skill_identity(manifest[key]['commit']) for key in ('historical_release', 'combined_candidate')}
    errors = []
    for key, identity in identities.items():
        if manifest[key]['skill_tree_sha256'] != identity['sha256']:
            errors.append(key + ': SHA mismatch')
    lock = json.loads((EXEC / 'content-lock.json').read_text())
    if lock['files'] != file_inventory():
        errors.append('fixture/oracle content-lock mismatch')
    task_ids = {task['id'] for task in TASKS.values()}
    if task_ids != {task['id'] for task in manifest['task_inventory']}:
        errors.append('task inventory mismatch')
    for name, task in TASKS.items():
        contract = json.loads((ROOT / 'fixtures' / (task['id'] + '.json')).read_text())
        if contract.get('executable_fixture') != 'executable/fixtures/' + name:
            errors.append(name + ': fixture binding mismatch')
    rows = allocation()
    if rows != manifest['allocation'].get('plan') or len(rows) != manifest['allocation']['maximum_calls']:
        errors.append('allocation replay mismatch')
    validate_pairs(rows)
    return {'status': 'PASS' if not errors else 'FAIL', 'errors': errors,
            'skill_identities': identities, 'fixture_files': len(lock['files']),
            'paired_observations': len(rows), 'pairs': len(rows) // 2,
            'model_calls': 0, 'execution_ready': False}


def container_options(image, name):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('immutable local image ID required; tags are not execution identities')
    return ['docker', 'create', '--name', name, '--pull', 'never', '--network', 'none',
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--user', '65534:65534', '--memory', '512m', '--memory-swap', '512m',
            '--cpus', '1', '--pids-limit', '64', '--ulimit', 'fsize=67108864:67108864',
            '--ulimit', 'core=0:0', '--tmpfs', '/work:rw,exec,nosuid,nodev,size=256m,mode=1777',
            '--init', image]


def docker_case(image, args, timeout=90):
    """No host filesystem mounts, environment forwarding, or privileged modes."""
    name = 'sovetwave-preflight-' + uuid.uuid4().hex
    created = False
    outcome = {'args': args, 'status': 'NOT_EXECUTED'}
    try:
        subprocess.run(container_options(image, name) + args, check=True, capture_output=True, timeout=20)
        created = True
        inspect = json.loads(subprocess.check_output(['docker', 'inspect', name], timeout=15))[0]
        config = inspect['HostConfig']
        outcome['isolation_config'] = {key: config.get(key) for key in (
            'NetworkMode', 'ReadonlyRootfs', 'CapDrop', 'SecurityOpt', 'Memory',
            'MemorySwap', 'NanoCpus', 'PidsLimit', 'Binds', 'Tmpfs', 'Privileged')}
        proc = subprocess.Popen(['docker', 'start', '-a', name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        chunks = bytearray()
        overflow = threading.Event()

        def reader():
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                if len(chunks) + len(chunk) > 2_000_000:
                    overflow.set()
                    subprocess.run(['docker', 'kill', name], capture_output=True, timeout=15)
                    break
                chunks.extend(chunk)

        thread = threading.Thread(target=reader, daemon=True); thread.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            outcome['status'] = 'TIMEOUT'
            subprocess.run(['docker', 'kill', name], capture_output=True, timeout=15, check=True)
            proc.wait(timeout=15)
        finally:
            thread.join(timeout=15)
            proc.stdout.close()
        state = json.loads(subprocess.check_output(['docker', 'inspect', name], timeout=15))[0]['State']
        outcome['container_state'] = state
        if overflow.is_set():
            outcome['status'] = 'INVALID'
            outcome['reason'] = 'output limit exceeded'
        elif outcome['status'] != 'TIMEOUT':
            try:
                outcome['result'] = json.loads(chunks.decode('utf-8'))
                outcome['status'] = outcome['result']['status'] if state['ExitCode'] == 0 else 'FAIL'
            except (ValueError, KeyError):
                outcome['status'] = 'FAIL'
                outcome['diagnostic'] = chunks.decode('utf-8', errors='replace')[-8000:]
    finally:
        if created:
            # Delete only the UUID-named container created by this invocation.
            subprocess.run(['docker', 'rm', '-f', name], check=True, capture_output=True, timeout=20)
            outcome['container_removed'] = True
    return outcome


def selftest(image):
    report = {'offline': offline(), 'image': image, 'cases': [], 'model_calls': 0,
              'generated_code_executed': False}
    if report['offline']['status'] != 'PASS':
        report['status'] = 'FAIL'; return report
    probe = docker_case(image, ['--probe'])
    report['isolation_probe'] = probe
    expected_lock = hashlib.sha256((EXEC / 'content-lock.json').read_bytes()).hexdigest()
    if probe['status'] != 'PASS' or probe.get('result', {}).get('fixture_lock_sha256') != expected_lock:
        report['status'] = 'FAIL'; return report
    for task, spec in TASKS.items():
        good = docker_case(image, ['--task', task, '--variant', 'reference'])
        bad = docker_case(image, ['--task', task, '--variant', 'mutant'])
        stub = docker_case(image, ['--task', task, '--variant', 'starter'])
        failure = {row['id']: row['status'] for row in bad.get('result', {}).get('checks', [])}
        ok = (good['status'] == 'PASS' and bad['status'] == 'FAIL' and
              failure.get(spec['expected_failure']) == 'FAIL' and stub['status'] == 'FAIL')
        report['cases'].append({'task': task, 'reference': good, 'mutant': bad,
                                'starter': stub, 'oracle_control': 'PASS' if ok else 'FAIL'})
    hung = docker_case(image, ['--hang-child'], timeout=2)
    report['termination_probe'] = hung
    reset = docker_case(image, ['--probe'])
    report['reset_probe'] = reset
    memory = docker_case(image, ['--memory-probe'])
    report['memory_probe'] = memory
    report['status'] = 'PASS' if (all(row['oracle_control'] == 'PASS' for row in report['cases'])
                                 and hung['status'] == 'TIMEOUT' and hung['container_removed']
                                 and not hung['container_state']['Running'] and reset['status'] == 'PASS'
                                 and memory['container_state']['OOMKilled']) else 'FAIL'
    report['live_pilot_verdict'] = 'HOLD'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--build-image', action='store_true')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--image')
    parser.add_argument('--prepare', choices=TASKS)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.prepare:
        if not args.output:
            parser.error('--prepare needs a new --output directory under executable/.temp')
        print(json.dumps({'fixture_commit': prepare(args.prepare, args.output), 'model_calls': 0}))
        return 0
    if args.build_image:
        subprocess.run(['docker', 'build', '-t', 'sovetwave-preflight:local', str(EXEC)], check=True)
        print(subprocess.check_output(['docker', 'image', 'inspect', 'sovetwave-preflight:local', '--format', '{{.Id}}']).decode().strip())
        return 0
    if args.selftest and not args.image:
        parser.error('--selftest requires an immutable --image sha256:...')
    result = selftest(args.image) if args.selftest else offline()
    payload = json.dumps(result, sort_keys=True, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8', newline='\n')
    print(json.dumps({'status': result['status'], 'report': str(args.output), 'model_calls': 0})
          if args.output else payload)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
