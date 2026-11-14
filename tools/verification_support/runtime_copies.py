"""Explicit authorized attempt groups; old attempts and phase rows are retained."""
import json
import re


def upgrade(db):
    from .runtime_attempts import upgrade as moves_upgrade
    moves_upgrade(db)
    with db:
        db.execute('BEGIN IMMEDIATE')
        version = db.execute('SELECT version FROM metadata WHERE id=1').fetchone()[0]
        if version == 3:
            return
        if version != 2:
            raise ValueError('Unknown attempt group schema')
        db.execute('CREATE TABLE speculative_runs (run INTEGER PRIMARY KEY REFERENCES runs(id))')
        db.execute('''CREATE TABLE speculative_attempts (
            run INTEGER NOT NULL REFERENCES runs(id), node TEXT NOT NULL, worker TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE, attempt INTEGER UNIQUE REFERENCES attempts(id),
            state TEXT NOT NULL, confirmation TEXT, failed INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(run,node,worker))''')
        db.execute('''CREATE TABLE speculative_winners (
            run INTEGER NOT NULL REFERENCES runs(id), node TEXT NOT NULL,
            worker TEXT NOT NULL, token TEXT NOT NULL UNIQUE, PRIMARY KEY(run,node))''')
        db.execute('UPDATE metadata SET version=3 WHERE id=1')


def enabled(db, run):
    return (db.execute('SELECT version FROM metadata WHERE id=1').fetchone()[0] == 3
            and db.execute('SELECT 1 FROM speculative_runs WHERE run=?', (run,)).fetchone() is not None)


def enable(db, run):
    upgrade(db)
    with db:
        if db.execute('SELECT finished FROM runs WHERE id=?', (run,)).fetchone() != (None,):
            raise ValueError('Attempt group needs a live run')
        db.execute('INSERT INTO speculative_runs VALUES(?)', (run,))


def authorize(db, run, node, worker, token):
    if not enabled(db, run):
        raise ValueError('Speculation was not enabled for this run')
    with db:
        db.execute('BEGIN IMMEDIATE')
        if (db.execute('SELECT finished FROM runs WHERE id=?', (run,)).fetchone() != (None,)
                or type(token) is not str or not re.fullmatch('[0-9a-f]{32}', token)
                or type(worker) is not str or not re.fullmatch('gw[0-9]+', worker)
                or type(node) is not str or not node):
            raise ValueError('Invalid or closed speculative reservation')
        if db.execute('SELECT 1 FROM speculative_winners WHERE run=? AND node=?', (run, node)).fetchone():
            raise ValueError('Completed test cannot receive another attempt')
        db.execute('INSERT INTO speculative_attempts VALUES(?,?,?,?,NULL,?,NULL,0)',
                   (run, node, worker, token, 'reserved'))


def allowed(db, run, node, worker):
    row = db.execute('SELECT attempt,state FROM speculative_attempts WHERE run=? AND node=? AND worker=?',
                     (run, node, worker)).fetchone()
    if row != (None, 'reserved'):
        raise ValueError('Duplicate attempt lacks its exact controller reservation')


def started(db, run, node, worker, attempt):
    if enabled(db, run):
        allowed(db, run, node, worker)
        db.execute("UPDATE speculative_attempts SET attempt=?,state='running' WHERE run=? AND node=? AND worker=?",
                   (attempt, run, node, worker))


def complete(db, run, node, worker, token):
    with db:
        row = db.execute('SELECT attempt,state,token FROM speculative_attempts WHERE run=? AND node=? AND worker=?',
                         (run, node, worker)).fetchone()
        if row is None or row[1:] != ('running', token):
            raise ValueError('Completion lacks an active authorized attempt')
        phases = dict(db.execute('SELECT phase,outcome FROM phases WHERE attempt=?', (row[0],)))
        if 'setup' not in phases or 'teardown' not in phases:
            raise ValueError('Completion arrived before durable teardown')
        db.execute("UPDATE speculative_attempts SET state='complete' WHERE attempt=?", (row[0],))
        return bool(db.execute('INSERT OR IGNORE INTO speculative_winners VALUES(?,?,?,?)',
                               (run, node, worker, token)).rowcount)


def cancelled(db, run, node, identity, worker, token, confirmation, *, moved=False):
    with db:
        row = db.execute('''SELECT a.id,a.test,s.state,s.token,a.invalid FROM attempts a JOIN speculative_attempts s
            ON s.attempt=a.id WHERE a.run=? AND a.node=? AND a.worker=?''', (run, node, worker)).fetchone()
        if row is None or row[1:4] != (identity, 'running', token):
            raise ValueError('Cancellation lacks its exact active attempt')
        receipt = json.loads(confirmation)
        if (receipt.get('cancelled') is not True or receipt.get('children_remaining') != 0
                or receipt.get('attempt', {}).get('token') != token):
            raise ValueError('Cancellation lacks termination evidence')
        phases = dict(db.execute('SELECT phase,outcome FROM phases WHERE attempt=?', (row[0],)))
        db.execute('UPDATE speculative_attempts SET state=?,confirmation=?,failed=? WHERE attempt=?',
                   ('moved' if moved else 'cancelled', confirmation, row[4], row[0]))
        db.execute('UPDATE attempts SET invalid=1 WHERE id=?', (row[0],))
        return phases


def group(db, run, node, *, host=None):
    """Return this group's canonical measurement, never an older group's value."""
    rows = db.execute('''SELECT a.id,a.test,a.invalid,a.complete,s.state,h.host,
        s.worker,s.failed FROM speculative_attempts s LEFT JOIN attempts a ON a.id=s.attempt
        LEFT JOIN attempt_hosts h ON h.attempt=a.id WHERE s.run=? AND s.node=?''', (run, node)).fetchall()
    winner = db.execute('SELECT worker FROM speculative_winners WHERE run=? AND node=?', (run, node)).fetchone()
    if (not rows or winner is None or any(r[4] not in ('complete', 'cancelled', 'moved') for r in rows)
            or any(r[7] for r in rows)
            or any(r[4] == 'complete' and (r[2] or not r[3]) for r in rows)
            or db.execute('''SELECT 1 FROM phases p JOIN speculative_attempts s ON s.attempt=p.attempt
                             WHERE s.run=? AND s.node=? AND p.outcome!='passed' LIMIT 1''', (run, node)).fetchone()):
        return None
    for r in rows:
        if r[4] == 'moved':
            successor = db.execute('''SELECT s.id FROM attempt_moves m JOIN attempts s ON s.id=m.successor
                WHERE m.attempt=? AND s.run=? AND s.node=? AND s.test=? AND s.worker=m.target_worker''',
                (r[0],run,node,r[1])).fetchone()
            if successor is None:
                return None
    candidates = [r for r in rows if r[4] == 'complete' and (r[5] == host if host is not None else r[6] == winner[0])]
    if not candidates:
        return None
    # Host-local completion timestamps share one clock and are durable phase times.
    row = min(candidates, key=lambda r: db.execute("SELECT recorded FROM phases WHERE attempt=? AND phase='teardown'", (r[0],)).fetchone()[0])
    duration = db.execute('SELECT SUM(duration) FROM phases WHERE attempt=?', (row[0],)).fetchone()[0]
    return row[0], row[1], duration


def verify(db, run, pairs, outcomes):
    rows = db.execute('SELECT node,test FROM attempts WHERE run=?', (run,)).fetchall()
    if dict(rows) != pairs:
        raise ValueError('Attempt groups differ from the fixed collection')
    for node, identity in pairs.items():
        if (outcomes.get(identity) == 'passed') != (group(db, run, node) is not None):
            raise ValueError('Attempt group has unresolved or failed evidence')


def latest_ids(db, *, run=None):
    """Read-only SQL selecting a group's winner, or its newest uncompleted start."""
    where = '' if run is None else ' WHERE run=' + str(int(run))
    key = 'test' if run is None else 'node'
    latest = 'SELECT MAX(id) FROM attempts' + where + ' GROUP BY ' + key
    if db.execute('SELECT version FROM metadata WHERE id=1').fetchone()[0] != 3:
        return latest
    return ('''SELECT COALESCE(s.attempt,a.id) FROM attempts a
        LEFT JOIN speculative_winners w ON w.run=a.run AND w.node=a.node
        LEFT JOIN speculative_attempts s ON s.run=w.run AND s.node=w.node AND s.worker=w.worker
        WHERE a.id IN (''' + latest + ')')
