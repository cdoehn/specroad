"""Host setup/transport, durable phases and heterogeneous dispatch contracts."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dev.test_hosts.config import host, load
from dev.test_hosts.environment import environment, digest
from dev.test_hosts.history import HistoryClient, HistoryServer, estimates
from dev.test_hosts.lease import Lease
from dev.test_hosts.provision import check, prepare, python_path
from dev.test_hosts.snapshot import inventory, copy_snapshot, remote_verify
from dev.test_hosts.ssh import Transport
from dev.status.monitor_data import history as monitor_history
from verification_support.runtime_history import RuntimeHistory


def configured(**values):
    return host({'name': 'fast', 'ssh': 'test-server', 'directory': '/tmp/specroad-host-fixture', **values})


def test_local_config_preserves_alias_limits_and_has_no_credentials(tmp_path):
    path = tmp_path / 'hosts.json'
    path.write_text(json.dumps({'format_version': 1, 'hosts': [configured().value(), configured(name='local', ssh=None).value()]}))
    assert [h.ssh for h in load(path)] == ['test-server', None]
    with pytest.raises(ValueError):
        configured(password='not-a-real-password')


def test_ssh_commands_reuse_private_master_and_do_not_prompt_during_tests(tmp_path):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout='true')
    transport = Transport(configured(persist=3600), runner=run, state=tmp_path)
    assert transport.python('print(True)') is True
    command, options = calls[0]
    assert 'BatchMode=yes' in command and 'ControlPersist=3600' in command
    assert 'ForwardAgent=no' in command and 'StrictHostKeyChecking=yes' in command
    transport.control('connect')
    assert 'BatchMode=no' in calls[1][0] and '-tt' in calls[1][0]
    assert calls[1][1]['capture_output'] is False
    assert not list(tmp_path.iterdir())


def test_setup_installs_exact_separate_environment_then_checks_it(tmp_path):
    expected = environment()
    host = configured()
    binary = tmp_path / 'uv'; binary.write_bytes(b'synthetic installer input')
    calls = []
    checked = []
    class Remote:
        def python(self, script, **kwargs):
            # The environment script also hashes the host account. Its explicit
            # managed interpreter distinguishes it from the installer checksum.
            if kwargs.get('executable') == python_path(host, expected):
                assert 'sync' in calls[-1]
                checked.append(kwargs['executable'])
                return {'environment': expected, 'tools': dict.fromkeys(('rsync', 'git', 'ionice'), True)}
            if 'linked host directory' in script:
                return True
            if 'hashlib.sha256' in script:
                from hashlib import sha256
                return sha256(binary.read_bytes()).hexdigest()
            pytest.fail('unexpected preparation probe')
        def run(self, command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=1 if command[0] == 'test' else 0,
                stdout='ID=ubuntu\n' if command[0] == 'cat' else expected['machine'] if command[0] == 'uname' else '')
        def copy(self, source, target):
            assert (Path(source) / 'requirements.txt').read_text().splitlines() == [f'{n}=={v}' for n, v in expected['packages'].items()]
    result = prepare(host, transport=Remote(), uv=binary, non_interactive=True)
    assert result['ready']
    assert result['environment'] == expected and result['environment_sha256'] == digest(expected)
    assert checked == [python_path(host, expected)]
    assert any(c[:4] == ['sudo', '-n', 'apt-get', 'update'] for c in calls)
    assert any('--managed-python' in c and expected['python'] in c for c in calls)
    assert any('sync' in c and '--only-binary' in c for c in calls)
    assert python_path(configured(), expected).endswith(digest(expected) + '/venv/bin/python')


def test_check_mismatch_cannot_install_or_start_tests():
    class Remote:
        def python(self, *a, **kw):
            return {'environment': {}, 'tools': {}}
        def run(self, *a, **kw):
            pytest.fail('check must not install')
    with pytest.raises(ValueError, match='environment mismatch'):
        check(configured(), transport=Remote())


def test_snapshot_contains_current_dirty_bytes_but_no_local_work_or_credentials(tmp_path):
    root = tmp_path / 'repo'; root.mkdir()
    for name in ('src/specroad/a.py', 'tests/test_a.py', 'tools/a.py', 'verification/a.json', 'docs/a.md', 'pyproject.toml'):
        target = root / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(b'current uncommitted bytes')
    for name in ('CURRENT_WORK.txt', '.env', '.git/config', '.venv/key', 'build/session.json'):
        target = root / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(b'private fixture')
    manifest = copy_snapshot(root, tmp_path / 'snapshot')
    assert len(manifest) == 6 and inventory(tmp_path / 'snapshot') == manifest
    assert (tmp_path / 'snapshot/src/specroad/a.py').read_bytes() == b'current uncommitted bytes'
    # Execute the actual standalone verifier against synthetic source bytes.
    exec(compile(remote_verify(tmp_path / 'snapshot', manifest), '<snapshot-verifier>', 'exec'), {})


class Reply:
    def __init__(self):
        self.replies = []
    def send(self, value):
        self.replies.append(value)


def test_rpc_start_is_committed_before_ack_and_phases_reach_host_monitor(tmp_path):
    channel = Reply()
    with RuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 1)
    server = HistoryServer(channel, tmp_path, run, 'gw0', 'fast', 'b' * 64, {'node': 'identity'})
    try:
        server.receive((1, 'start', ['node', 'identity', 'gw0']))
        assert channel.replies == [(1, 'ok')]
        with RuntimeHistory(tmp_path) as independent:
            assert independent.snapshot(['identity'])['tests'][0]['duration_ns'] is None
            assert independent.db.execute('SELECT host FROM attempt_hosts').fetchall() == [('fast',)]
        for sequence, phase in enumerate(('setup', 'call', 'teardown'), 2):
            server.receive((sequence, 'phase', ['node', 'identity', 'gw0', phase, 2.0, 'passed', False]))
        rows = monitor_history(tmp_path / 'build/test-runtime-history.sqlite3')
        assert rows[0]['host'] == 'fast' and rows[0]['total_seconds'] == 6.0
        assert estimates(tmp_path, 'b' * 64) == {'identity\nfast': 6.0}
    finally:
        server.receive(None)


def test_new_incomplete_host_attempt_suppresses_old_estimate(tmp_path):
    with RuntimeHistory(tmp_path) as store:
        for turn in range(2):
            run = store.begin('a' * 64, 1)
            store.start(run, 'node', 'identity', 'gw0', host='fast', environment='b' * 64)
            if turn == 0:
                for phase in ('setup', 'call', 'teardown'):
                    store.observe(run, 'node', 'identity', 'gw0', phase, 1, 'passed')
    assert estimates(tmp_path, 'b' * 64) == {}


def test_two_apply_lines_cannot_exceed_shared_host_slots(tmp_path):
    directory = tmp_path / 'slots'
    first, second = Lease(2, directory=directory), Lease(2, directory=directory)
    try:
        assert first.slot != second.slot
        with pytest.raises(ValueError, match='occupied'):
            Lease(2, directory=directory)
        with pytest.raises(ValueError, match='budget change'):
            Lease(3, directory=directory)
    finally:
        first.close(); second.close()
    replacement = Lease(3, directory=directory)
    replacement.close()


class Node:
    def __init__(self, name):
        self.gateway = SimpleNamespace(id=name)
        self.shutting_down = False
        self.sent = []
    def send_runtest_some(self, indices):
        self.sent.extend(indices)
    def shutdown(self):
        self.shutting_down = True


def scheduler(durations, speeds):
    from dev.test_hosts.scheduler import HostScheduling
    # The actual dispatch methods run with tiny fake xdist transports; no sleeps.
    item = object.__new__(HostScheduling)
    item.collection = ['node' + str(i) for i in range(len(durations))]
    item.pending = list(range(len(durations)))
    item.node2pending = {Node('gw' + str(i)): [] for i in range(len(speeds))}
    item.profile = {'selected': {n: n for n in item.collection},
        'workers': {'gw' + str(i): {'host': str(i), 'speed': speed} for i, speed in enumerate(speeds)},
        'baseline': {n: value for n, value in zip(item.collection, durations) if value is not None}, 'estimates': {}}
    item.started, item.scale, item.ready = {}, {}, False
    return item


def test_unknown_is_explored_on_fast_host_while_known_long_jobs_start_early():
    item = scheduler([None, 200, 100, 5, 2, 1], [4, 4, 0.25])
    item.check_schedule()
    nodes = list(item.node2pending)
    assert 0 in nodes[0].sent and 1 in nodes[1].sent
    assert 0 not in nodes[2].sent and 1 not in nodes[2].sent
    assert all(len(p) <= 2 for p in item.node2pending.values())


def test_dispatch_preserves_every_test_once_until_the_last_short_tail():
    item = scheduler([100, 80, 50, 40, 30, 2, 1, 0.5, None], [2, 1, 0.3])
    item.check_schedule()
    done = []
    for _ in range(50):
        active = [(n, p[0]) for n, p in item.node2pending.items() if p]
        if not active:
            break
        node, index = min(active, key=lambda pair: item.duration(*pair))
        done.append(index)
        item.mark_test_complete(node, index, item.duration(node, index))
    assert sorted(done) == list(range(9)) and not item.pending
