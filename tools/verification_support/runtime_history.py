"""Current test durations backed by append-only attempts and durable native phases."""
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import time

from .common import json_bytes
from .identity import platform_identity
from .runtime_baseline import load_baseline
from .runtime_store import PHASES, journal_path

POLICY = 'verification/test_runtime_policy.json'
SHARED = '../exchange/specroad-test-runtime-history.sqlite3'
LOCAL = 'build/test-runtime-history.sqlite3'


def policy(root):
    path = Path(root) / POLICY
    if not os.path.lexists(path):
        return None
    if path.is_symlink() or not path.is_file():
        raise ValueError('Unsafe runtime policy')
    value = json.loads(path.read_bytes())
    if (set(value) != {'format_version', 'selection', 'database'}
            or type(value['format_version']) is not int or value['format_version'] != 1
            or value['selection'] != 'latest_valid_fifth'
            or value['database'] not in (LOCAL, SHARED)):
        raise ValueError('Unknown runtime history policy')
    return value


def now():
    return datetime.now(timezone.utc).isoformat()


SCHEMA = '''
CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL);
INSERT INTO metadata VALUES(1,1);
CREATE TABLE origins (hash TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE seeds (id INTEGER PRIMARY KEY, test TEXT NOT NULL, duration INTEGER NOT NULL,
    origin TEXT NOT NULL, UNIQUE(test,origin), FOREIGN KEY(origin) REFERENCES origins(hash));
CREATE TABLE runs (id INTEGER PRIMARY KEY, source TEXT, workers INTEGER NOT NULL,
    platform TEXT NOT NULL, started TEXT NOT NULL, finished TEXT, exit_code INTEGER);
CREATE TABLE attempts (id INTEGER PRIMARY KEY, run INTEGER NOT NULL, node TEXT NOT NULL,
    test TEXT NOT NULL, worker TEXT NOT NULL, started TEXT NOT NULL,
    invalid INTEGER NOT NULL DEFAULT 0, complete INTEGER NOT NULL DEFAULT 0,
    UNIQUE(run,node), FOREIGN KEY(run) REFERENCES runs(id));
CREATE INDEX attempts_test ON attempts(test,id);
CREATE TABLE phases (attempt INTEGER NOT NULL, phase TEXT NOT NULL, duration INTEGER NOT NULL,
    outcome TEXT NOT NULL, recorded TEXT NOT NULL, PRIMARY KEY(attempt,phase),
    FOREIGN KEY(attempt) REFERENCES attempts(id));
'''


class RuntimeHistory:
    """Multiple controllers/workers serialize short FULL-sync transactions, not runs."""

    def __init__(self, root, *, path=None):
        root = Path(root).resolve()
        config = policy(root)
        self.path = journal_path(path or root / (config['database'] if config else LOCAL), root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        journal_path(self.path, root)
        self.db = None
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            # Serialize creation only; every writer uses SQLite transactions afterwards.
            deadline = time.monotonic() + 30
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise ValueError('Runtime history initialization is busy') from None
                    time.sleep(0.01)
            opened = os.fstat(fd)
            current = self.path.lstat()
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)):
                raise ValueError('Runtime history file changed while opening')
            size = os.fstat(fd).st_size
            if size and os.read(fd, 16) != b'SQLite format 3\0':
                raise ValueError('Invalid runtime history file')
            self.db = sqlite3.connect(self.path, timeout=30)
            self.db.execute('PRAGMA journal_mode=DELETE')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA foreign_keys=ON')
            if not size:
                self.db.executescript(SCHEMA)
                directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            if self.db.execute('SELECT version FROM metadata WHERE id=1').fetchall() != [(1,)]:
                raise ValueError('Unknown runtime history version')
            if self.db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise ValueError('Runtime history integrity check failed')
            self.file_identity = (opened.st_dev, opened.st_ino)
        except BaseException:
            self.close()
            raise
        finally:
            os.close(fd)

    def seed(self, root):
        baseline = load_baseline(root)
        if baseline is None:
            return
        digest, value = baseline
        with self.db:
            added = self.db.execute('INSERT OR IGNORE INTO origins VALUES(?,?)',
                                    (digest, json_bytes(value).decode())).rowcount
            if added:
                self.db.executemany('INSERT INTO seeds(test,duration,origin) VALUES(?,?,?)',
                    ((row['test_id'], row['duration_ns'], digest) for row in value['tests']))

    def begin(self, source, workers):
        with self.db:
            return self.db.execute('INSERT INTO runs(source,workers,platform,started) VALUES(?,?,?,?)',
                (source, workers, json_bytes(platform_identity()).decode(), now())).lastrowid

    def start(self, run, node, identity, worker):
        if not all(type(v) is str and v for v in (node, identity, worker)):
            raise ValueError('A native test identity is required before execution')
        with self.db:
            state = self.db.execute('SELECT finished FROM runs WHERE id=?', (run,)).fetchone()
            if state != (None,):
                raise ValueError('A live runtime attempt requires an unfinished run')
            self.db.execute('INSERT INTO attempts(run,node,test,worker,started) VALUES(?,?,?,?,?)',
                            (run, node, identity, worker, now()))

    def observe(self, run, node, identity, worker, phase, duration, outcome, *, subtest=False):
        with self.db:
            row = self.db.execute('SELECT id,test,worker FROM attempts WHERE run=? AND node=?',
                                  (run, node)).fetchone()
            if row is None:
                raise ValueError('Runtime phase does not match the started test')
            attempt = row[0]
            if row[1:] != (identity, worker):
                self.db.execute('UPDATE attempts SET invalid=1 WHERE id=?', (attempt,))
                return
            if subtest:
                if outcome != 'passed':
                    self.db.execute('UPDATE attempts SET invalid=1 WHERE id=?', (attempt,))
                return
            if (phase not in PHASES or type(duration) not in (int, float)
                    or not math.isfinite(duration) or duration < 0 or duration > 86400):
                self.db.execute('UPDATE attempts SET invalid=1 WHERE id=?', (attempt,))
                return
            previous = self.db.execute('SELECT 1 FROM phases WHERE attempt=? AND phase=?',
                                       (attempt, phase)).fetchone()
            if previous:
                self.db.execute('UPDATE attempts SET invalid=1 WHERE id=?', (attempt,))
                return
            order = self.db.execute('SELECT phase FROM phases WHERE attempt=? ORDER BY rowid', (attempt,)).fetchall()
            if [p[0] for p in order] != list(PHASES[:PHASES.index(phase)]):
                self.db.execute('UPDATE attempts SET invalid=1 WHERE id=?', (attempt,))
            self.db.execute('INSERT INTO phases VALUES(?,?,?,?,?)',
                            (attempt, phase, round(duration * 1_000_000_000), outcome, now()))
            if outcome != 'passed':
                self.db.execute('UPDATE attempts SET invalid=1 WHERE id=?', (attempt,))
            if phase == 'teardown':
                phases = self.db.execute('SELECT phase,outcome FROM phases WHERE attempt=?', (attempt,)).fetchall()
                if dict(phases) == dict.fromkeys(PHASES, 'passed'):
                    self.db.execute('UPDATE attempts SET complete=1 WHERE id=?', (attempt,))

    def finish(self, run, code, *, invalid=False):
        with self.db:
            if invalid:
                self.db.execute('UPDATE attempts SET invalid=1 WHERE run=?', (run,))
            self.db.execute('UPDATE runs SET finished=?,exit_code=? WHERE id=?', (now(), code, run))

    def verify_run(self, run, pairs, outcomes):
        """A successful gate requires its own durable matching records, not old values."""
        current = self.path.lstat()
        if (current.st_nlink != 1 or not stat.S_ISREG(current.st_mode)
                or (current.st_dev, current.st_ino) != self.file_identity):
            raise ValueError('Runtime history was replaced during execution')
        rows = self.db.execute('SELECT node,test,invalid,complete FROM attempts WHERE run=?', (run,)).fetchall()
        observed = {node: identity for node, identity, _, _ in rows}
        if observed != pairs or any((outcomes.get(identity) == 'passed') != (not invalid and bool(complete))
                                    for _, identity, invalid, complete in rows):
            raise ValueError('The successful observation lacks matching durable phases')

    def snapshot(self, identities):
        ids = sorted(set(identities))
        # Both queries must see the same database generation.
        self.db.execute('BEGIN')
        try:
            attempts = self.db.execute('''SELECT a.id,a.test,a.invalid,a.complete,SUM(p.duration)
                FROM attempts a LEFT JOIN phases p ON p.attempt=a.id
                WHERE a.id IN (SELECT MAX(id) FROM attempts GROUP BY test) GROUP BY a.id''').fetchall()
            seeds = self.db.execute('''SELECT test,duration,origin FROM seeds
                WHERE id IN (SELECT MAX(id) FROM seeds GROUP BY test)''').fetchall()
        finally:
            self.db.rollback()
        latest = {test: {'test_id': test, 'attempt': attempt,
                        'duration_ns': duration if not invalid and complete else None}
                  for attempt, test, invalid, complete, duration in attempts}
        historic = {test: {'test_id': test, 'origin_sha256': origin, 'duration_ns': duration}
                    for test, duration, origin in seeds}
        return {'format_version': 1, 'kind': 'specroad-latest-runtime-snapshot-v1',
                'tests': [latest.get(i, historic.get(i, {'test_id': i, 'duration_ns': None})) for i in ids]}

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def filter_latest(selected, snapshot):
    if (set(snapshot) != {'format_version', 'kind', 'tests'} or snapshot['format_version'] != 1
            or snapshot['kind'] != 'specroad-latest-runtime-snapshot-v1'):
        raise ValueError('Unknown runtime snapshot')
    rows = snapshot['tests']
    if type(rows) is not list or not rows or any(type(r) is not dict for r in rows):
        raise ValueError('Invalid runtime snapshot records')
    for row in rows:
        if (set(row) not in ({'test_id','duration_ns'}, {'test_id','duration_ns','attempt'},
                             {'test_id','duration_ns','origin_sha256'})
                or type(row.get('test_id')) is not str or not row['test_id']
                or ('attempt' in row and (type(row['attempt']) is not int or row['attempt'] < 1))
                or ('origin_sha256' in row and (type(row['origin_sha256']) is not str
                    or len(row['origin_sha256']) != 64
                    or any(c not in '0123456789abcdef' for c in row['origin_sha256'])))):
            raise ValueError('Invalid runtime snapshot identity or origin')
    ids = [r['test_id'] for r in rows]
    if ids != sorted(set(ids)) or not set(selected.values()) <= set(ids):
        raise ValueError('Snapshot must cover the complete current selection')
    for row in rows:
        duration = row['duration_ns']
        if duration is not None and (type(duration) is not int or duration < 0):
            raise ValueError('Invalid current runtime duration')
    measured = [r for r in rows if r['duration_ns'] is not None]
    excluded = sorted(r['test_id'] for r in sorted(measured,
        key=lambda r: (-r['duration_ns'], r['test_id']))[:len(measured)//5])
    kept = {n: i for n, i in selected.items() if i not in set(excluded)}
    if not kept:
        raise ValueError('An empty filtered partition cannot pass')
    receipt = {'format_version': 2, 'snapshot_sha256': sha256(json_bytes(snapshot)).hexdigest(),
               'current_tests': len(rows), 'measured_tests': len(measured),
               'excluded_test_ids': excluded, 'partition_tests': len(selected),
               'partition_excluded_test_ids': sorted(set(selected.values()) & set(excluded))}
    return kept, receipt
