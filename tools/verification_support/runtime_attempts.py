"""Durable operator cancellation and explicitly linked fresh attempts."""
import sqlite3


def upgrade(db):
    if db.execute('SELECT version FROM metadata WHERE id=1').fetchone() == (2,):
        return
    # All old ids, timestamps, hosts and phase rows survive byte-for-byte as
    # values. Older writers reject version 2 rather than silently joining two
    # attempts. Ordinary duplicate starts remain forbidden by start_allowed.
    db.commit()
    db.execute('PRAGMA foreign_keys=OFF')
    try:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT version FROM metadata WHERE id=1').fetchone() != (1,):
            raise ValueError('Runtime history changed during attempt migration')
        db.execute('''CREATE TABLE move_attempts (id INTEGER PRIMARY KEY, run INTEGER NOT NULL,
            node TEXT NOT NULL, test TEXT NOT NULL, worker TEXT NOT NULL, started TEXT NOT NULL,
            invalid INTEGER NOT NULL DEFAULT 0, complete INTEGER NOT NULL DEFAULT 0,
            UNIQUE(run,node,worker), FOREIGN KEY(run) REFERENCES runs(id))''')
        db.execute('INSERT INTO move_attempts SELECT * FROM attempts')
        db.execute('DROP TABLE attempts')
        db.execute('ALTER TABLE move_attempts RENAME TO attempts')
        db.execute('CREATE INDEX attempts_test ON attempts(test,id)')
        db.execute('''CREATE TABLE attempt_moves (attempt INTEGER PRIMARY KEY, token TEXT NOT NULL UNIQUE,
            target_worker TEXT NOT NULL, confirmed TEXT NOT NULL, successor INTEGER UNIQUE,
            FOREIGN KEY(attempt) REFERENCES attempts(id), FOREIGN KEY(successor) REFERENCES attempts(id))''')
        db.execute('UPDATE metadata SET version=2 WHERE id=1')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Attempt migration broke a runtime reference')
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.execute('PRAGMA foreign_keys=ON')


def start_allowed(db, run, node, identity, worker):
    old = db.execute('SELECT id,test FROM attempts WHERE run=? AND node=? ORDER BY id DESC LIMIT 1', (run, node)).fetchone()
    if old is None:
        return None
    if db.execute('SELECT version FROM metadata WHERE id=1').fetchone() == (2,):
        move = db.execute('SELECT target_worker,successor FROM attempt_moves WHERE attempt=?', (old[0],)).fetchone()
        if old[1] == identity and move == (worker, None):
            return old[0]
    raise sqlite3.IntegrityError('A second attempt needs a confirmed bound operator move')


def cancel(db, run, node, identity, worker, target_worker, token, confirmed):
    upgrade(db)
    with db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT id,test,worker,invalid FROM attempts WHERE run=? AND node=? ORDER BY id DESC LIMIT 1',
                         (run, node)).fetchone()
        if row is None or row[1:3] != (identity, worker) or row[3]:
            raise ValueError('Failed, invalid or foreign attempt cannot be replaced')
        phases = dict(db.execute('SELECT phase,outcome FROM phases WHERE attempt=?', (row[0],)))
        if any(v != 'passed' for v in phases.values()):
            raise ValueError('A real test failure cannot be hidden by relocation')
        db.execute('INSERT INTO attempt_moves VALUES(?,?,?,?,NULL)', (row[0], token, target_worker, confirmed))
        db.execute('UPDATE attempts SET invalid=1 WHERE id=?', (row[0],))
        return phases


def verify_moves(db, run):
    if db.execute('SELECT version FROM metadata WHERE id=1').fetchone() == (1,):
        return
    rows = db.execute('''SELECT a.id,a.node,a.test,a.invalid,m.target_worker,m.successor,
        s.run,s.node,s.test,s.worker FROM attempts a LEFT JOIN attempt_moves m ON m.attempt=a.id
        LEFT JOIN attempts s ON s.id=m.successor WHERE a.run=? AND a.id NOT IN
          (SELECT MAX(id) FROM attempts WHERE run=? GROUP BY node)''', (run, run)).fetchall()
    for old, node, identity, invalid, worker, successor, newer_run, newer_node, newer_id, newer_worker in rows:
        if (not invalid or successor is None or successor <= old
                or (newer_run, newer_node, newer_id, newer_worker) != (run, node, identity, worker)):
            raise ValueError('Incomplete or foreign runtime attempt lineage')
