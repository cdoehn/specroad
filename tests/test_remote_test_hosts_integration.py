"""Real execnet/xdist workers over isolated synthetic project snapshots."""
import json
import os
import platform
from pathlib import Path
import subprocess
import sys

from support.catalog_project import make_catalog_project, execute
from verification_support.host_execution import POLICY, POLICY_VALUE
from verification_support.identity import source_identity
from verification_support.runtime_history import RuntimeHistory
from dev.test_hosts.environment import environment, digest, account
from dev.test_hosts.pool import public_proof, verify_pool, proxy_gateway
from dev.test_hosts.snapshot import copy_snapshot, fingerprint
from verification_support.cpu_capacity import available_cpus
from verification_support.process_environment import test_environment as isolated_environment


def run_isolated_pool(tmp_path, *, source=None, crash=False, workers=1, durations=None,
                      heterogeneous=False):
    count = 6 if durations is None else len(durations)
    ids = [f'tests/test_subject.py::test_{i}' for i in range(count)]
    source = source or 'import threading\n' + '\n'.join(
        f'def test_{i}():\n    assert {i} >= 0\n'
        '    assert threading.current_thread() is threading.main_thread()\n' for i in range(count))
    if crash:
        source = source.replace('def test_0():', 'def test_0():\n    import os; os._exit(7)')
    root = make_catalog_project(tmp_path / 'controller', ids=ids, source=source)
    (root / POLICY).write_text(json.dumps(POLICY_VALUE))
    target = tmp_path / 'remote-source'
    manifest = copy_snapshot(root, target)
    # A proxy popen gateway exercises the same execnet via transport as SSH.
    # No credentials, external hosts or prepared live installations are needed.
    expected = environment()
    workers = min(workers, available_cpus())
    resources = dict(format_version=1, available_cpus=available_cpus(), workers=workers,
                     worker_limit=workers, nested=False, nice_minimum=10)
    base = dict(host='synthetic-host', hostname=platform.node(), account=account(), root=str(target),
                environment_sha256=digest(expected), resources=resources, speed=1.0,
                spec='popen//via=srproxy0//python=' + sys.executable,
                budget=workers, remote=True)
    worker_profiles = {f'gw{i}': base.copy() for i in range(workers)}
    if heterogeneous:
        # Distinct synthetic forecast groups share real processes and leases
        # on this machine. No remote credentials or real host speed are faked.
        for i, row in enumerate(worker_profiles.values()):
            row.update(host=f'synthetic-{i}', speed=1.0 if i == 0 else 0.5,
                       resources={**resources, 'workers': 1, 'worker_limit': 1})
    profile = dict(format_version=1, source_sha256=source_identity(root), snapshot_sha256=fingerprint(manifest),
                   environment=expected, workers=worker_profiles,
                   proxies=[proxy_gateway('srproxy0', 'popen', sys.executable, str(target))],
                   selected={n: n for n in ids}, estimates={},
                   baseline=dict(zip(ids, [1.0] * count if durations is None else durations)))
    path = root / 'build/host-run.json'; path.write_text(json.dumps(profile))
    args = ['-o', 'addopts=', '--disable-plugin-autoload', '-p', 'xdist.plugin',
        '-p', 'no:cacheprovider', '-p', 'no:doctest', '-n', str(workers), '--dist', 'worksteal', '--max-worker-restart=0',
        '--worker-limit', str(workers), '--sr-host-run', str(path), '--sr-expected-tests', str(count),
        '--sr-observations', str(root / 'build/observations.json'), *ids]
    env = isolated_environment(os.environ)
    env.update(SPECROAD_NESTED_TEST_RUN='0', XDG_STATE_HOME=str(tmp_path / 'private-state'))
    result = subprocess.run([sys.executable, '-I', '-B', str(root / 'tools/pytest_entry.py'), *args],
        cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=90)
    return root, target, profile, result


def test_real_slower_proxy_keeps_processing_successors_with_complete_native_phases(tmp_path):
    durations = [100, 100, 80] + [1] * 80
    source = '''import os
from pathlib import Path
import threading
import time

def exercise():
    assert threading.current_thread() is threading.main_thread()
    worker = os.environ['PYTEST_XDIST_WORKER']
    marker = Path('build') / ('seen-' + worker)
    marker.parent.mkdir(exist_ok=True)
    count = int(marker.read_text()) + 1 if marker.exists() else 1
    marker.write_text(str(count))
    continued = marker.parent / 'slow-continued'
    if worker == 'gw1' and count == 2:
        continued.write_text('two native test bodies')
    if worker == 'gw0' and count == 1 and int(os.environ['PYTEST_XDIST_WORKER_COUNT']) > 1:
        deadline = time.monotonic() + 15
        while not continued.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert continued.exists(), 'slower worker retired before its second test'
'''
    source += '\n'.join(f'def test_{i}():\n    exercise()\n' for i in range(len(durations)))
    root, remote, profile, result = run_isolated_pool(tmp_path, source=source, workers=2,
        durations=durations, heterogeneous=True)
    assert result.returncode == 0, (result.stdout + result.stderr).decode()
    observation = json.loads((root / 'build/observations.json').read_bytes())
    verify_pool(observation, public_proof(profile))
    assert observation['suite_passed'] and observation['tests_run'] == len(durations)
    assert not (remote / 'build/test-runtime-history.sqlite3').exists()
    with RuntimeHistory(root) as history:
        attempts = history.db.execute('SELECT test,worker,complete,invalid FROM attempts').fetchall()
        assert len(attempts) == len(durations)
        assert {test for test, _, _, _ in attempts} == set(profile['selected'])
        assert all(complete and not invalid for _, _, complete, invalid in attempts)
        assert history.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (3 * len(durations),)
        assert {row[0] for row in history.db.execute('SELECT DISTINCT host FROM attempt_hosts')} == {
            row['host'] for row in profile['workers'].values()}
        if len(profile['workers']) > 1:
            assert sum(worker == 'gw1' for _, worker, _, _ in attempts) >= 2
            assert (remote / 'build/slow-continued').is_file()


def test_real_proxy_workers_use_snapshot_and_ack_every_phase_to_coordinator(tmp_path):
    root, remote, profile, result = run_isolated_pool(tmp_path, workers=2)
    assert result.returncode == 0, (result.stdout + result.stderr).decode()
    observation = json.loads((root / 'build/observations.json').read_bytes())
    verify_pool(observation, public_proof(profile))
    assert observation['suite_passed'] and observation['tests_run'] == 6
    assert set(observation['workers']) == set(profile['workers'])
    assert not (remote / 'build/test-runtime-history.sqlite3').exists()
    with RuntimeHistory(root) as history:
        assert history.db.execute('SELECT COUNT(*) FROM attempts').fetchone() == (6,)
        assert history.db.execute('SELECT COUNT(*) FROM phases').fetchone() == (18,)
        assert history.db.execute('SELECT DISTINCT host FROM attempt_hosts').fetchall() == [('synthetic-host',)]
        assert all(row['duration_ns'] is not None for row in history.snapshot(profile['selected'].values())['tests'])


def test_real_remote_worker_loss_fails_without_retry_and_keeps_started_attempt(tmp_path):
    root, remote, profile, result = run_isolated_pool(tmp_path, crash=True)
    assert result.returncode != 0
    with RuntimeHistory(root) as history:
        attempts = history.db.execute('SELECT test,complete FROM attempts').fetchall()
        assert ('tests/test_subject.py::test_0', 0) in attempts
        assert len(attempts) == len(set(test for test, complete in attempts))
        assert history.snapshot(['tests/test_subject.py::test_0'])['tests'][0]['duration_ns'] is None


def test_real_apply_pool_gate_preserves_rotation_union_and_rechecks_host_binding(tmp_path):
    from verification_support import apply_gate, apply_rotation
    from verification_support.commit_tests import POLICY as REQUIRED, POLICY_VALUE as REQUIRED_VALUE
    from verification_support.runtime_history import LOCAL
    ids = [f'tests/test_subject.py::test_{i}' for i in range(6)]
    root = make_catalog_project(tmp_path / 'repo', ids=ids,
        source='\n'.join(f'def test_{i}():\n    assert {i} >= 0\n' for i in range(6)))
    (root / POLICY).write_text(json.dumps(POLICY_VALUE))
    (root / REQUIRED).write_text(json.dumps(REQUIRED_VALUE))
    (root / 'verification/test_runtime_policy.json').write_text(json.dumps(
        dict(format_version=1, selection='latest_valid_fifth', database=LOCAL)))
    (root / '.gitignore').write_text('build/\n__pycache__/\n*.pyc\n')
    def git(*args):
        return subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'core.hooksPath=/dev/null', *args], cwd=root, stdin=subprocess.DEVNULL,
            capture_output=True, check=True).stdout.decode().strip()
    git('init'); git('add', '.'); git('commit', '-m', 'synthetic base')
    head = git('rev-parse', 'HEAD')
    (root / apply_rotation.REGISTRY).write_text(json.dumps(dict(format_version=2, anchor_commit=head,
        rotation_anchor_commit=head, partition_count=3, test_ids=ids)))
    plan = dict(format_version=1, commit_id='host.W', test_ids=[ids[1]], test_files=[], reason='Synthetic required union')
    plan_path = root / 'build/plan.json'; plan_path.write_text(json.dumps(plan))
    host_path = root / 'build/hosts.json'
    host_path.write_text(json.dumps(dict(format_version=1, hosts=[dict(name='local', ssh=None,
        directory=str(tmp_path / 'host'), workers=2)])))
    source = source_identity(root)
    gate = root / 'build/gate'
    result = execute(root, 'run_apply_tests.py', ['--test-plan', str(plan_path), '--commit-id', 'host.W',
        '--outdir', str(gate), '--hosts', str(host_path), '--worker-limit', '2'],
        environment={'SPECROAD_NESTED_TEST_RUN': '0', 'XDG_STATE_HOME': str(tmp_path / 'private-state')})
    assert result.returncode == 0, (result.stdout + result.stderr).decode()
    report = json.loads((gate / 'selection.json').read_bytes())
    assert report['format_version'] == 5 and report['selection_binding']['format_version'] == 6
    assert set(report['nodeid_to_test_id']) == {ids[i] for i in (0, 1, 3)}
    receipt = apply_gate.verify_commit_gate(root, gate, source=source, head=head, test_plan=plan)
    assert receipt['tests'] == 3
    assert git('rev-parse', 'HEAD') == head
    profile_path = gate / 'host-run.json'; original = profile_path.read_bytes()
    workers = tuple(json.loads(original)['workers'])
    import pytest
    try:
        for changed in (('gw0',), workers):
            profile = json.loads(original)
            for worker in changed:
                profile['workers'][worker]['host'] = 'invented-host'
            if changed == workers:
                # Even an internally consistent replacement must not match the
                # frozen host proof; the other case can fail profile validation.
                assert public_proof(profile) != report['host_pool']
            profile_path.write_text(json.dumps(profile))
            with pytest.raises(ValueError):
                apply_gate.verify_commit_gate(root, gate, source=source, head=head, test_plan=plan)
    finally:
        profile_path.write_bytes(original)
    assert apply_gate.verify_commit_gate(root, gate, source=source, head=head, test_plan=plan) == receipt
    assert git('rev-parse', 'HEAD') == head
