"""Offline regression tests; C++ execution occurs only in the Docker selftest."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[2] / 'research/beta3-practical-effectiveness'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = load('cpp_preflight', BASE / 'preflight.py')
inside = load('cpp_inside', BASE / 'executable/inside.py')


class PreflightTests(unittest.TestCase):
    def test_offline_inventory_hashes_and_allocation(self):
        result = preflight.offline()
        self.assertEqual(result['status'], 'PASS', result['errors'])
        self.assertFalse(result['execution_ready'])
        self.assertEqual(result['pairs'], 30)

    def test_skill_hash_uses_real_nul_and_raw_bytes(self):
        def git(*args):
            return b'skills/sovetwave/a\n' if args[0] == 'ls-tree' else b'raw\r\n\xff'
        with patch.object(preflight, 'git_bytes', side_effect=git):
            actual = preflight.skill_identity('a' * 40)
        self.assertEqual(actual['sha256'], hashlib.sha256(b'skills/sovetwave/a\0raw\r\n\xff\0').hexdigest())
        self.assertEqual(actual['separator_hex'], '00')

    def test_pairing_rejects_duplicate_and_missing_arm(self):
        rows = preflight.allocation()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            preflight.validate_pairs(rows + [rows[0]])
        with self.assertRaisesRegex(ValueError, 'missing'):
            preflight.validate_pairs(rows[1:])
        self.assertEqual(rows, preflight.allocation())
        self.assertNotEqual(rows, preflight.allocation(1))

    def test_counterbalance_and_subset_counts(self):
        rows = preflight.allocation()
        for name, count in [('primary', 36), ('natural', 12), ('grounded', 12)]:
            subset = [r for r in rows if r['experiment'] == name]
            self.assertEqual(len(subset), count)
            for position in (1, 2):
                self.assertEqual(sum(r['position'] == position and r['arm'] == 'baseline' for r in subset), count // 4)

    def test_docker_has_no_host_bind_or_environment_forwarding(self):
        command = preflight.container_options('sha256:' + 'a' * 64, 'sovetwave-preflight-unit')
        for option in ('--network', '--read-only', '--cap-drop', '--memory', '--cpus', '--pids-limit', '--tmpfs'):
            self.assertIn(option, command)
        for option in ('--volume', '-v', '--mount', '--privileged', '--env-file', '--env'):
            self.assertNotIn(option, command)
        self.assertIn('/work:rw,exec,nosuid,nodev,size=256m,mode=1777', command)
        with self.assertRaises(ValueError):
            preflight.container_options('gcc:latest', 'bad')

    def test_missing_or_duplicate_checks_never_pass(self):
        self.assertEqual(inside.summarize([], {'compile'})[0], 'NOT_ASSESSABLE')
        self.assertEqual(inside.summarize([{'id': 'compile', 'status': 'PASS'}], {'compile', 'run'})[0], 'NOT_ASSESSABLE')
        row = {'id': 'compile', 'status': 'PASS'}
        self.assertEqual(inside.summarize([row, row], {'compile'})[0], 'INVALID')

    def test_statuses_remain_distinct(self):
        for status in ('PASS', 'FAIL', 'INVALID', 'NOT_EXECUTED', 'NOT_ASSESSABLE'):
            self.assertEqual(inside.summarize([{'id': 'check', 'status': status}], {'check'})[0], status)

    def test_machine_gates_require_evidence_and_do_not_grade_economy(self):
        gates = inside.grade_gates('state', [], {'compile', 'runtime_contract', 'unrelated_diff'})
        self.assertTrue(all(gate['status'] == 'NOT_ASSESSABLE' for gate in gates.values()))
        self.assertFalse(gates['economy']['review_eligible'])
        checks = [{'id': key, 'status': 'PASS'} for key in ('compile', 'runtime_contract', 'unrelated_diff')]
        gates = inside.grade_gates('state', checks, {c['id'] for c in checks})
        self.assertTrue(gates['economy']['review_eligible'])
        self.assertEqual(gates['economy']['status'], 'NOT_ASSESSABLE')
        checks[1]['status'] = 'FAIL'
        gates = inside.grade_gates('state', checks, {c['id'] for c in checks})
        self.assertEqual(gates['safety']['status'], 'FAIL')
        self.assertFalse(gates['economy']['review_eligible'])

    def test_archive_rejects_traversal_links_duplicate_and_oversize(self):
        for names, kind in [(['../escape'], 'file'), (['a', 'a'], 'file'), (['/absolute'], 'file'),
                            (['a\\escape'], 'file'), (['C:escape'], 'file'), (['link'], 'link')]:
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode='w:') as archive:
                for name in names:
                    item = tarfile.TarInfo(name)
                    if kind == 'link':
                        item.type = tarfile.SYMTYPE; item.linkname = '/etc/passwd'
                        archive.addfile(item)
                    else:
                        item.size = 1; archive.addfile(item, io.BytesIO(b'x'))
            with tempfile.TemporaryDirectory() as directory:
                with patch.object(inside.sys, 'stdin', type('Stdin', (), {'buffer': io.BytesIO(data.getvalue())})()):
                    with self.assertRaises(ValueError):
                        inside.candidate_from_stdin(Path(directory))

    def test_content_lock_drift_fails_closed(self):
        real = preflight.file_inventory()
        with patch.object(preflight, 'file_inventory', return_value={**real, 'extra': 'bad'}):
            result = preflight.offline()
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('fixture/oracle content-lock mismatch', result['errors'])

    def test_prepare_is_repeatable_and_never_resets_existing_directory(self):
        base = preflight.EXEC / '.temp'
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as directory:
            root = Path(directory)
            first = preflight.prepare('state', root / 'first')
            second = preflight.prepare('state', root / 'second')
            self.assertEqual(first, second)
            self.assertNotIn(b'\r', (root / 'first/TASK.md').read_bytes())
            with self.assertRaises(ValueError):
                preflight.prepare('state', root / 'first')
            with self.assertRaises(ValueError):
                preflight.prepare('state', preflight.ROOT / 'outside-temp')

    def test_recorded_control_evidence_and_checksums(self):
        runtime = json.loads((BASE / 'runtime-preflight.json').read_text())
        report_path = BASE / runtime['control_report']
        report = json.loads(report_path.read_text())
        self.assertEqual(hashlib.sha256(report_path.read_bytes()).hexdigest(), runtime['control_report_sha256'])
        lock_hash = hashlib.sha256((BASE / runtime['fixture_lock']).read_bytes()).hexdigest()
        self.assertEqual(lock_hash, runtime['fixture_lock_sha256'])
        self.assertEqual(lock_hash, report['isolation_probe']['result']['fixture_lock_sha256'])
        self.assertEqual(report['image'], runtime['executor']['image_id'])
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['model_calls'], 0)
        self.assertEqual(len(report['cases']), len(preflight.TASKS))
        self.assertEqual({row['task'] for row in report['cases']}, set(preflight.TASKS))
        for row in report['cases']:
            self.assertEqual(row['oracle_control'], 'PASS')
            self.assertEqual(row['reference']['status'], 'PASS')
            gates = row['reference']['result']['machine_gates']
            self.assertTrue(all(gates[name]['status'] == 'PASS' for name in
                                ('functionality', 'completeness', 'compatibility', 'safety')))
            self.assertEqual(gates['economy']['status'], 'NOT_ASSESSABLE')
            self.assertEqual(row['mutant']['status'], 'FAIL')
            self.assertEqual(row['starter']['status'], 'FAIL')
            self.assertTrue(all(row[variant]['container_removed'] for variant in ('reference', 'mutant', 'starter')))
        self.assertTrue(report['memory_probe']['container_state']['OOMKilled'])
        self.assertEqual(report['termination_probe']['status'], 'TIMEOUT')
        self.assertEqual(report['reset_probe']['status'], 'PASS')
        paths = set()
        for line in (BASE / 'SHA256SUMS.txt').read_text().splitlines():
            digest, path = line.split('  ', 1)
            self.assertNotIn(path, paths)
            paths.add(path)
            self.assertEqual(hashlib.sha256((BASE / path).read_bytes()).hexdigest(), digest, path)


if __name__ == '__main__':
    unittest.main()
