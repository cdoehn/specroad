"""Versioned SQLite profiles; short concurrent transactions, no runtime-history writes."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

from .common import MARKER, VERSION, digest, encoded, now, output_path


def validate(db):
    if db.execute('SELECT id,marker,version FROM metadata').fetchall() != [(1, MARKER, VERSION)]:
        raise ValueError('Not a supported SpecRoad profiling database')


@contextmanager
def reader(path):
    path = Path(path).resolve()
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=30)
    try:
        validate(db)
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        db.row_factory = sqlite3.Row
        yield db
    finally:
        db.close()


class Store:
    def __init__(self, path, root, *, create=False):
        self.path = output_path(root, path)
        created = False
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(fd)
                created = True
        self.db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=60)
        try:
            if created:
                self.db.executescript((Path(__file__).with_name('schema.sql')).read_text())
            # Reject unrelated databases before changing their journal mode.
            validate(self.db)
            self.db.execute('PRAGMA foreign_keys=ON')
            if created:
                self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
        except BaseException:
            self.db.close()
            raise

    def create_run(self, identifier, repository, directory, settings):
        with self.db:
            self.db.execute('INSERT INTO runs(id,repository,directory,created,status,settings_json) '
                            'VALUES(?,?,?,?,?,?)',
                            (identifier, str(repository), str(directory), now(), 'preparing', encoded(settings)))

    def select(self, run, pairs, historical, source, selection_hash, workers):
        if (not pairs or len(set(pairs.values())) != len(pairs)
                or selection_hash != digest(pairs) or type(workers) is not int or workers < 1):
            raise ValueError('Profiling selection must be nonempty, unique and hash-bound')
        with self.db:
            self.db.executemany('INSERT INTO tests(run_id,nodeid,test_id,ordinal,historical_json) VALUES(?,?,?,?,?)',
                                ((run, node, identity, i, encoded(historical.get(identity)))
                                 for i, (node, identity) in enumerate(pairs.items())))
            self.db.execute('UPDATE runs SET source_sha256=?,selection_sha256=?,workers=? WHERE id=?',
                            (source, selection_hash, workers, run))

    def running(self, run, command):
        with self.db:
            self.db.execute('UPDATE runs SET status=?,command_json=? WHERE id=?', ('running', encoded(command), run))

    def begin_test(self, run, node, worker, pid, tid, cpu, stamp):
        with self.db:
            changed = self.db.execute('UPDATE tests SET status=?,worker=?,pid=?,tid=?,cpu=?,started_ns=? '
                                      'WHERE run_id=? AND nodeid=? AND status=?',
                                      ('running', worker, pid, tid, cpu, stamp, run, node, 'selected')).rowcount
            if changed != 1:
                raise ValueError('Unselected or repeated profiling attempt')

    def end_test(self, run, node, stamp):
        with self.db:
            self.db.execute('UPDATE tests SET status=?,finished_ns=? WHERE run_id=? AND nodeid=? AND status=?',
                            ('finished', stamp, run, node, 'running'))

    def phase(self, run, node, name, before, after, stats, root):
        def label(key):
            filename, line, function = key
            prefix = str(root) + '/'
            return (filename[len(prefix):] if filename.startswith(prefix) else filename, line, function)
        with self.db:
            phase = self.db.execute('INSERT INTO phases(run_id,nodeid,phase,pid,tid,start_ns,end_ns,elapsed_ns,resources_json) '
                                   'VALUES(?,?,?,?,?,?,?,?,?)',
                                   (run, node, name, before['pid'], before['tid'], before['time_ns'], after['time_ns'],
                                    after['monotonic_ns'] - before['monotonic_ns'], encoded(dict(before=before, after=after)))).lastrowid
            for index, (key, values) in enumerate(sorted(stats.items())):
                primitive, calls, own, cumulative, callers = values
                self.db.execute('INSERT INTO python_functions VALUES(?,?,?,?,?,?,?,?,?)',
                                (phase, index, *label(key), primitive, calls, own, cumulative))
                self.db.executemany('INSERT INTO python_callers VALUES(?,?,?,?,?,?,?,?,?)',
                                    ((phase, index, *label(caller), *metrics) for caller, metrics in callers.items()))

    def phase_outcome(self, run, node, phase, outcome):
        with self.db:
            self.db.execute('UPDATE phases SET outcome=? WHERE run_id=? AND nodeid=? AND phase=?',
                            (outcome, run, node, phase))

    def finish(self, run, status, code, *, outcomes=None, error=None):
        if status == 'passed' and (type(code) is not int or code != 0):
            status, error = 'failed', 'A successful profiling run requires process exit code zero'
        with self.db:
            selected = self.db.execute('SELECT nodeid,test_id,started_ns,finished_ns FROM tests WHERE run_id=?', (run,)).fetchall()
            for node, identity, started, finished in selected:
                outcome = (outcomes or {}).get(identity, 'not_run')
                phases = dict(self.db.execute('SELECT phase,outcome FROM phases WHERE run_id=? AND nodeid=?', (run, node)))
                complete = (started is not None and finished is not None and
                            phases == dict.fromkeys(('setup', 'call', 'teardown'), 'passed'))
                state = ('passed' if outcome == 'passed' and complete else 'skipped' if outcome in ('skipped', 'expected_failure')
                         else 'failed' if outcome in ('failed', 'error', 'unexpected_success') else 'incomplete')
                self.db.execute('UPDATE tests SET status=?,outcome=? WHERE run_id=? AND nodeid=?', (state, outcome, run, node))
            if status == 'passed' and (not selected or self.db.execute('SELECT COUNT(*) FROM tests WHERE run_id=? AND status!=?', (run, 'passed')).fetchone()[0]):
                status, error = 'incomplete', 'Missing complete profiling phases'
            self.db.execute('UPDATE runs SET status=?,exit_code=?,finished=?,error=? WHERE id=?', (status, code, now(), error, run))
        return status

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
