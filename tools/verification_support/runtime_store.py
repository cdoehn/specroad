"""Durable per-phase timing records; no scheduler and no automatic test retry."""
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import sqlite3
import stat

from .common import json_bytes
from .identity import platform_identity

PHASES = ('setup', 'call', 'teardown')


def now():
    return datetime.now(timezone.utc).isoformat()


def journal_path(path, root):
    path = Path(os.path.abspath(path))
    root = Path(root).resolve()
    if path == root or root in path.parents and path.relative_to(root).parts[0] != 'build':
        raise ValueError('Timing journals belong in build/ or outside source inputs')
    for parent in path.parents:
        if os.path.lexists(parent) and not stat.S_ISDIR(parent.lstat().st_mode):
            raise ValueError('Timing journal has an unsafe parent')
    if os.path.lexists(path):
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Timing journal must be a single regular file')
    return path


def binding(source, pairs, workers):
    if (type(workers) is not int or workers < 2 or not pairs
            or len(set(pairs.values())) != len(pairs)):
        raise ValueError('Parallel complete unique collection is required')
    return {'format_version': 1, 'source_sha256': source,
            'pairs': dict(sorted(pairs.items())), 'workers': workers,
            'platform': platform_identity()}


SCHEMA = '''
CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
CREATE TABLE runs (id INTEGER PRIMARY KEY, started TEXT NOT NULL,
    finished TEXT, valid INTEGER NOT NULL DEFAULT 1, error TEXT);
CREATE TABLE selection (run INTEGER NOT NULL, node TEXT NOT NULL,
    PRIMARY KEY(run,node), FOREIGN KEY(run) REFERENCES runs(id));
CREATE TABLE phases (run INTEGER NOT NULL, node TEXT NOT NULL, phase TEXT NOT NULL,
    duration_ns INTEGER NOT NULL, outcome TEXT NOT NULL, worker TEXT NOT NULL,
    recorded TEXT NOT NULL, PRIMARY KEY(run,node,phase),
    FOREIGN KEY(run,node) REFERENCES selection(run,node));
CREATE TABLE issues (run INTEGER NOT NULL, node TEXT NOT NULL,
    PRIMARY KEY(run,node), FOREIGN KEY(run,node) REFERENCES selection(run,node));
'''


def _metadata(db):
    if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
        raise ValueError('Timing journal integrity check failed')
    rows = db.execute('SELECT value FROM metadata WHERE id=1').fetchall()
    if len(rows) != 1:
        raise ValueError('Missing timing journal binding')
    value = json.loads(rows[0][0])
    if set(value) != {'format_version', 'source_sha256', 'pairs', 'workers', 'platform'} or value['format_version'] != 1:
        raise ValueError('Unknown timing journal format')
    return value


def _completed(db, meta):
    rows = db.execute('''SELECT p.run,p.node,p.phase,p.duration_ns,p.outcome,p.worker,p.recorded
        FROM phases p JOIN runs r ON r.id=p.run WHERE r.valid=1
        AND NOT EXISTS (SELECT 1 FROM issues i WHERE i.run=p.run AND i.node=p.node)
        ORDER BY p.run,p.node,p.phase''').fetchall()
    groups = {}
    for run, node, phase, duration, outcome, worker, recorded in rows:
        groups.setdefault((run, node), {})[phase] = (duration, outcome, worker, recorded)
    complete = {}
    for (run, node), phases in groups.items():
        if (node in complete or node not in meta['pairs'] or set(phases) != set(PHASES)
                or any(v[1] != 'passed' or type(v[0]) is not int or v[0] < 0 for v in phases.values())
                or len({v[2] for v in phases.values()}) != 1
                or not all(v[2].startswith('gw') for v in phases.values())):
            continue
        complete[node] = {'nodeid': node, 'test_id': meta['pairs'][node],
                          'phase_ns': {p: phases[p][0] for p in PHASES},
                          'attempt': run, 'recorded': max(v[3] for v in phases.values())}
    return complete


class TimingStore:
    """One controller owns a writer lease; every native report commits with FULL sync."""

    def __init__(self, path, root, expected):
        self.path = journal_path(path, root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        journal_path(self.path, root)
        self.db = None
        self.fd = None
        try:
            try:
                self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                created = True
            except FileExistsError:
                self.fd = os.open(self.path, os.O_RDWR | os.O_NOFOLLOW)
                created = False
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if not created and os.read(self.fd, 16) != b'SQLite format 3\x00':
                raise ValueError('Existing file is not a timing journal')
            self.db = sqlite3.connect(self.path, timeout=30)
            self.db.execute('PRAGMA journal_mode=DELETE')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA foreign_keys=ON')
            if created:
                self.db.executescript(SCHEMA)
                with self.db:
                    self.db.execute('INSERT INTO metadata VALUES(1,?)', (json_bytes(expected).decode(),))
                directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            self.meta = _metadata(self.db)
            if self.meta != expected:
                raise ValueError('Source, collection, platform or worker count differs; use a new journal')
        except BaseException:
            self.close()
            raise

    def begin(self, selected):
        if not selected or any(self.meta['pairs'].get(n) != i for n, i in selected.items()):
            raise ValueError('Selection differs from the bound collection')
        with self.db:
            run = self.db.execute('INSERT INTO runs(started) VALUES(?)', (now(),)).lastrowid
            self.db.executemany('INSERT INTO selection VALUES(?,?)', [(run, n) for n in selected])
        return run

    def observe(self, run, node, identity, phase, duration, outcome, worker, *, subtest=False):
        if (self.meta['pairs'].get(node) != identity
                or not self.db.execute('SELECT 1 FROM selection WHERE run=? AND node=?', (run, node)).fetchone()):
            self.invalidate(run, 'unexpected_test_identity')
            raise ValueError('Unexpected measurement identity')
        if subtest:
            if outcome != 'passed':
                with self.db:
                    self.db.execute('INSERT OR IGNORE INTO issues VALUES(?,?)', (run, node))
            return
        if (phase not in PHASES or type(duration) not in (int, float)
                or not math.isfinite(duration) or duration < 0
                or not math.isfinite(duration * 1e9) or duration * 1e9 >= 2**63
                or outcome not in ('passed', 'failed', 'error', 'skipped', 'expected_failure', 'unexpected_success')
                or type(worker) is not str or not worker.startswith('gw')):
            self.invalidate(run, 'invalid_native_report')
            raise ValueError('Invalid native measurement report')
        try:
            with self.db:
                self.db.execute('INSERT INTO phases VALUES(?,?,?,?,?,?,?)',
                    (run, node, phase, round(duration * 1e9), outcome, worker, now()))
        except sqlite3.IntegrityError:
            self.invalidate(run, 'duplicate_phase')
            raise ValueError('Ambiguous repeated test phase') from None

    def invalidate(self, run, reason):
        with self.db:
            self.db.execute('UPDATE runs SET valid=0,error=? WHERE id=?', (reason, run))

    def finish(self, run):
        with self.db:
            self.db.execute('UPDATE runs SET finished=? WHERE id=?', (now(), run))

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def read_store(path, root):
    path = journal_path(path, root)
    if not path.is_file():
        raise ValueError('Timing journal does not exist')
    source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)
    snapshot = sqlite3.connect(':memory:')
    try:
        source.execute('PRAGMA query_only=ON')
        # SQLite's online backup takes short read locks, including while a
        # writer commits. Slow validation/ranking happens after source.close().
        source.backup(snapshot, pages=128, sleep=0.01)
    finally:
        source.close()
    try:
        meta = _metadata(snapshot)
        complete = _completed(snapshot, meta)
        attempts = snapshot.execute('SELECT count(*) FROM runs').fetchone()[0]
        phase_count = snapshot.execute('SELECT count(*) FROM phases').fetchone()[0]
        imports = []
        if snapshot.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='measurement_imports'").fetchone():
            imports = [json.loads(row[0]) for row in snapshot.execute('SELECT detail FROM measurement_imports ORDER BY id')]
        return meta, complete, {'attempts': attempts, 'persisted_phases': phase_count, 'measurement_imports': imports}
    finally:
        snapshot.close()


def measurement_from_store(path, root, expected_source):
    meta, complete, info = read_store(path, root)
    if meta['source_sha256'] != expected_source or set(complete) != set(meta['pairs']):
        raise ValueError('Incomplete or changed timing coverage; measure missing tests first')
    result = {'format_version': 2, 'kind': 'specroad-resumable-test-runtimes-v2',
            'source_sha256': expected_source, 'measured_at': max(r['recorded'] for r in complete.values()),
            'workers': meta['workers'], 'coverage_complete': True, 'full_suite_passed': None,
            'attempts': info['attempts'],
            'tests': [{k: r[k] for k in ('nodeid', 'test_id', 'phase_ns')}
                      for n, r in sorted(complete.items())]}

    if info['measurement_imports']:
        result.update(format_version=3, kind='specroad-resumable-test-runtimes-v3',
                      measurement_imports=info['measurement_imports'])
    return result
