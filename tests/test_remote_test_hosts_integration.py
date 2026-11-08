"""Real execnet/xdist workers over isolated synthetic project snapshots."""
import json
import os
from pathlib import Path
import subprocess
import sys

from support.catalog_project import make_catalog_project, execute
from verification_support.host_execution import POLICY, POLICY_VALUE
from verification_support.identity import source_identity
from verification_support.runtime_history import RuntimeHistory
from dev.test_hosts.environment import environment, digest
from dev.test_hosts.pool import public_proof, verify_pool
from dev.test_hosts.snapshot import copy_snapshot, fingerprint
from verification_support.cpu_capacity import available_cpus


def run_isolated_pool(tmp_path, *, source=None, crash=False):
    ids = [f'tests/test_subject.py::test_{i}' for i in range(6)]
    source = source or '\n'.join(f'def test_{i}():\n    assert {i} >= 0\n' for i in range(6))
    if crash:
        source = source.replace('def test_0():', 'def test_0():\n    import os; os._exit(7)')
    root = make_catalog_project(tmp_path / 'controller', ids=ids, source=source)
    (root / POLICY).write_text(json.dumps(POLICY_VALUE))
    target = tmp_path / 'remote-source'
    manifest = copy_snapshot(root, target)
    # A proxy popen gateway exercises the same execnet via transport as SSH.
    # No credentials, external hosts or prepared live installations are needed.
    expected = environment()
    resources = dict(format_version=1, available_cpus=available_cpus(), workers=1,
                     worker_limit=1, nested=False, nice_minimum=10)
    base = dict(host='synthetic-host', hostname='synthetic-host', root=str(target),
                environment_sha256=digest(expected), resources=resources, speed=1.0,
                spec='popen//via=srproxy0//python=' + sys.executable,
                budget=1, remote=True)
    profile = dict(format_version=1, source_sha256=source_identity(root), snapshot_sha256=fingerprint(manifest),
                   environment=expected, workers={'gw0': base},
                   proxies=['id=srproxy0//popen//python=' + sys.executable + '//chdir=' + str(target)],
                   selected={n: n for n in ids}, estimates={}, baseline={n: 1.0 for n in ids})
    path = root / 'build/host-run.json'; path.write_text(json.dumps(profile))
    result = execute(root, 'pytest_entry.py', ['-o', 'addopts=', '--disable-plugin-autoload', '-p', 'xdist.plugin',
        '-p', 'no:cacheprovider', '-p', 'no:doctest', '-n', '1', '--dist', 'worksteal', '--max-worker-restart=0',
        '--worker-limit', '1', '--sr-host-run', str(path), '--sr-expected-tests', '6',
        '--sr-observations', str(root / 'build/observations.json'), *ids],
        environment={'SPECROAD_NESTED_TEST_RUN': '0', 'XDG_STATE_HOME': str(tmp_path / 'private-state')})
    return root, target, profile, result


def test_real_proxy_workers_use_snapshot_and_ack_every_phase_to_coordinator(tmp_path):
    root, remote, profile, result = run_isolated_pool(tmp_path)
    assert result.returncode == 0, (result.stdout + result.stderr).decode()
    observation = json.loads((root / 'build/observations.json').read_bytes())
    verify_pool(observation, public_proof(profile))
    assert observation['suite_passed'] and observation['tests_run'] == 6
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
    assert apply_gate.verify_commit_gate(root, gate, source=source, head=head, test_plan=plan)['tests'] == 3
    assert git('rev-parse', 'HEAD') == head
    profile_path = gate / 'host-run.json'; profile = json.loads(profile_path.read_bytes())
    profile['workers']['gw0']['host'] = 'invented-host'
    profile_path.write_text(json.dumps(profile))
    import pytest
    with pytest.raises(ValueError, match='Host run'):
        apply_gate.verify_commit_gate(root, gate, source=source, head=head, test_plan=plan)
