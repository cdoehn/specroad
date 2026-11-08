"""Synchronous durable history over execnet, separate from asynchronous reports."""
from pathlib import Path
import sqlite3
import threading

from verification_support.runtime_history import RuntimeHistory


def estimates(root, environment):
    """Latest attempt per host/test/environment; never fall back behind a failure."""
    with RuntimeHistory(root) as history:
        rows = history.db.execute('''SELECT a.test,h.host,a.invalid,a.complete,SUM(p.duration)
            FROM attempts a JOIN attempt_hosts h ON h.attempt=a.id
            LEFT JOIN phases p ON p.attempt=a.id
            WHERE h.environment=? AND a.id IN
              (SELECT MAX(a2.id) FROM attempts a2 JOIN attempt_hosts h2 ON h2.attempt=a2.id
               WHERE h2.environment=? GROUP BY a2.test,h2.host)
            GROUP BY a.id''', (environment, environment)).fetchall()
        return {test + '\n' + host: duration / 1e9
                for test, host, invalid, complete, duration in rows if not invalid and complete and duration is not None}


class HistoryClient:
    def __init__(self, channel):
        self.channel, self.sequence = channel, 0

    def request(self, kind, values):
        self.sequence += 1
        self.channel.send((self.sequence, kind, values))
        reply = self.channel.receive(timeout=60)
        if reply != (self.sequence, 'ok'):
            raise ValueError('Coordinator did not acknowledge durable runtime history')

    def start(self, run, node, identity, worker):
        self.request('start', [node, identity, worker])

    def observe(self, run, node, identity, worker, phase, duration, outcome, *, subtest=False):
        self.request('phase', [node, identity, worker, phase, duration, outcome, subtest])

    def close(self):
        pass


class HistoryServer:
    """Callback owns its SQLite connection; every ACK follows a FULL transaction."""
    def __init__(self, channel, root, run, worker, host, environment, selected):
        self.channel, self.root, self.run = channel, root, run
        self.worker, self.host, self.environment, self.selected = worker, host, environment, selected
        self.sequence, self.history, self.errors = 0, None, []
        self.closed = threading.Event()

    def receive(self, message):
        if message is None:
            if self.history is not None:
                self.history.close()
            self.closed.set()
            return
        try:
            sequence, kind, values = message
            if type(sequence) is not int or sequence != self.sequence + 1 or kind not in ('start', 'phase'):
                raise ValueError('Invalid runtime message sequence')
            if type(values) is not list or len(values) != (3 if kind == 'start' else 7):
                raise ValueError('Invalid runtime message')
            node, identity, worker = values[:3]
            if self.selected.get(node) != identity or worker != self.worker:
                raise ValueError('Foreign runtime test or worker')
            if self.history is None:
                self.history = RuntimeHistory(self.root)
            if kind == 'start':
                self.history.start(self.run, node, identity, worker, host=self.host, environment=self.environment)
            else:
                phase, duration, outcome, subtest = values[3:]
                self.history.observe(self.run, node, identity, worker, phase, duration, outcome, subtest=subtest)
            self.sequence = sequence
            self.channel.send((sequence, 'ok'))
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as error:
            self.errors.append(type(error).__name__)
            self.channel.send((self.sequence, 'rejected'))
