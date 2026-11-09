"""Pool callbacks share a pre-opened writer without weakening durable ACKs."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading
from types import SimpleNamespace

import pytest

from dev.test_hosts import history_writer, pytest_pool
from dev.test_hosts.history import HistoryServer
from verification_support import pytest_backend
from verification_support.runtime_history import RuntimeHistory
from test_remote_test_hosts import Reply


@pytest.mark.parametrize('workers', [1, 14])
def test_pool_initializes_one_thread_owned_writer_before_concurrent_worker_rpcs(tmp_path, monkeypatch, workers):
    with RuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, workers)
        path = store.path
    opened, closed = [], []

    class ObservedHistory(RuntimeHistory):
        def __init__(self, root):
            opened.append(threading.get_ident())
            super().__init__(root)

        def close(self):
            closed.append(threading.get_ident())
            super().close()

    monkeypatch.setattr(history_writer, 'RuntimeHistory', ObservedHistory)
    selected = {f'node{i}': f'case{i}' for i in range(workers)}
    profile = dict(selected=selected, source_sha256='a' * 64, snapshot_sha256='c' * 64,
        workers={f'gw{i}': dict(resources={}, host=f'host{i}', environment_sha256='b' * 64)
                 for i in range(workers)})
    config = SimpleNamespace(_sr_host_profile=profile, _sr_pool_servers=[])
    state = SimpleNamespace(history_root=tmp_path, history_run=run)

    class Channel(Reply):
        def setcallback(self, callback, endmarker):
            self.callback = callback

        def send(self, value):
            # Read the native database independently while ACK is emitted.
            assert value[1] == 'ok'
            with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
                count = db.execute('SELECT COUNT(*) FROM attempts WHERE node=?', (self.node,)).fetchone()[0]
                phases = db.execute('SELECT COUNT(*) FROM phases p JOIN attempts a ON a.id=p.attempt WHERE a.node=?',
                                    (self.node,)).fetchone()[0]
            assert count == 1 and phases == value[0] - 1
            super().send(value)

    channels = []
    try:
        for i in range(workers):
            channel = Channel(); channel.node = f'node{i}'; channels.append(channel)
            node = SimpleNamespace(config=config, workerinput={},
                gateway=SimpleNamespace(id=f'gw{i}', newchannel=lambda: channel))
            pytest_pool.setup_node(node, state)
            assert node.workerinput['sr_history_channel'] is channel
        assert len(opened) == 1 and opened[0] != threading.get_ident()

        def execute(i):
            channel = channels[i]
            channel.callback((1, 'start', [f'node{i}', f'case{i}', f'gw{i}']))
            for sequence, phase in enumerate(('setup', 'call', 'teardown'), 2):
                channel.callback((sequence, 'phase', [f'node{i}', f'case{i}', f'gw{i}', phase, 0.1, 'passed', False]))
            channel.callback(None)

        with ThreadPoolExecutor(max_workers=workers) as callers:
            list(callers.map(execute, range(workers)))
        # Per-worker disconnection must not close the pool's shared connection.
        assert not closed and len(opened) == 1
        assert all(not server.errors and server.closed.is_set() for server in config._sr_pool_servers)
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
            assert db.execute('SELECT COUNT(*) FROM attempts WHERE complete=1 AND invalid=0').fetchone() == (workers,)
            assert db.execute('SELECT COUNT(DISTINCT host) FROM attempt_hosts').fetchone() == (workers,)
        # Unconfigure must release a controller writer even without a worker lease.
        pytest_backend.pytest_unconfigure(config)
        assert closed == opened
        with pytest.raises(ValueError, match='closed'):
            config._sr_pool_history.start(run, 'late', 'late', 'gw0')
    finally:
        pytest_pool.close(config)
    assert closed == opened


def test_pool_integrity_failure_stops_setup_before_any_history_channel(tmp_path, monkeypatch):
    def corrupt(root):
        raise ValueError('Runtime history integrity check failed')
    monkeypatch.setattr(history_writer, 'RuntimeHistory', corrupt)
    config = SimpleNamespace(_sr_host_profile={'workers': {}}, _sr_pool_servers=[])
    state = SimpleNamespace(history_root=tmp_path)
    node = SimpleNamespace(config=config, gateway=SimpleNamespace(id='gw0'))
    with pytest.raises(ValueError, match='integrity'):
        pytest_pool.setup_node(node, state)
    assert not config._sr_pool_servers and not hasattr(config, '_sr_pool_history')
    pytest_pool.close(config)


@pytest.mark.parametrize('failed', [False, True])
def test_ack_waits_for_durable_transaction_and_rejects_storage_failure(tmp_path, monkeypatch, failed):
    with RuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 1)
        path = store.path
    entered, release = threading.Event(), threading.Event()

    class ControlledHistory(RuntimeHistory):
        def observe(self, *args, **kwargs):
            entered.set()
            if not release.wait(10):
                raise RuntimeError('Test did not release transaction')
            if failed:
                raise sqlite3.OperationalError('Synthetic failed storage')
            super().observe(*args, **kwargs)

    monkeypatch.setattr(history_writer, 'RuntimeHistory', ControlledHistory)
    writer = history_writer.HistoryWriter(tmp_path)
    channel = Reply()
    server = HistoryServer(channel, tmp_path, run, 'gw0', 'host', 'b' * 64, {'node': 'case'}, writer=writer)
    try:
        server.receive((1, 'start', ['node', 'case', 'gw0']))
        with ThreadPoolExecutor(max_workers=1) as callbacks:
            pending = callbacks.submit(server.receive, (2, 'phase', ['node', 'case', 'gw0', 'setup', 1, 'passed', False]))
            try:
                assert entered.wait(10)
                assert channel.replies == [(1, 'ok')]
            finally:
                release.set()
            pending.result(timeout=10)
        assert channel.replies[-1] == ((1, 'rejected') if failed else (2, 'ok'))
        assert bool(server.errors) is failed
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
            assert db.execute('SELECT COUNT(*) FROM phases').fetchone() == (0 if failed else 1,)
    finally:
        release.set()
        server.receive(None)
        writer.close()


def test_disconnected_history_peer_remains_an_error_without_a_second_send_exception(tmp_path):
    class Disconnected:
        def send(self, value):
            raise OSError('Synthetic disconnected channel')
    with RuntimeHistory(tmp_path) as store:
        run = store.begin('a' * 64, 1)
    writer = history_writer.HistoryWriter(tmp_path)
    server = HistoryServer(Disconnected(), tmp_path, run, 'gw0', 'host', 'b' * 64, {'node': 'case'}, writer=writer)
    try:
        server.receive((1, 'start', ['node', 'case', 'gw0']))
        assert server.errors == ['OSError']
        with RuntimeHistory(tmp_path) as independent:
            assert independent.snapshot(['case'])['tests'][0]['duration_ns'] is None
    finally:
        server.receive(None)
        writer.close()
