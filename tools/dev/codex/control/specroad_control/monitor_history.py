"""Inspect bounded ledger bytes in memory; never connect SQLite to live state."""
import os
import sqlite3
import stat
import time
from .errors import ControlError
from .local import outside
from .job_contract import scope

MAX_BYTES = 32 * 1024 * 1024
RECEIPTS = ('current_acceptances', 'apply_reconciliations',
            'clarification_authorizations', 'blocked_clarification_authorizations')


def history(paths, config):
    path = paths.state/'automation.sqlite3'
    outside(path)
    def quiet():
        if any(os.path.lexists(str(path)+suffix) for suffix in ('-journal', '-wal', '-shm')):
            raise ControlError('history_busy', 'Live SQLite sidecars require a later read.')
    quiet()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                or before.st_mode & 0o077 or before.st_nlink != 1 or before.st_size > MAX_BYTES):
            raise ControlError('unsafe_ledger', 'History must be a bounded private regular file.')
        raw = stream.read(MAX_BYTES+1)
        after = path.lstat()
        signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if signature(before) != signature(after) or len(raw) != before.st_size:
            raise ControlError('history_busy', 'History changed during the read.')
    quiet()
    db = sqlite3.connect(':memory:')
    deadline = time.monotonic()+0.2
    try:
        db.deserialize(raw)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA trusted_schema=OFF')
        db.execute('PRAGMA query_only=ON')
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        meta = db.execute('SELECT version,scope,current FROM meta WHERE id=1').fetchone()
        if meta is None or meta['version'] != 1 or meta['scope'] != scope(config):
            raise ControlError('ledger_scope_mismatch', 'History belongs to another configuration.')
        job = db.execute('SELECT run_id,sha,stage,patch_sha,error,updated FROM jobs WHERE run_id=?',
                         (meta['current'],)).fetchone()
        if job is None:
            raise ControlError('history_unavailable', 'No current job is present.')
        known = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 128")}
        report = {'observed_at': time.time(), 'evidence': 'unverified_snapshot', 'job': dict(job), 'receipts': {}}
        for table, fields in (('request_contracts', 'version,allowed,output_kind'),
                              ('clarification_budgets', 'maximum,remaining'),
                              ('clarification_continuations', 'pending')):
            if table in known:
                row = db.execute('SELECT '+fields+' FROM '+table+' WHERE sha=?', (job['sha'],)).fetchone()
                report[table] = dict(row) if row else None
        for table in RECEIPTS:
            if table in known:
                report['receipts'][table] = [dict(row) for row in db.execute(
                    'SELECT source_sha,state FROM '+table+' ORDER BY rowid DESC LIMIT 8')]
        return report
    except (sqlite3.Error, AttributeError, ValueError):
        raise ControlError('history_unavailable', 'History could not be inspected within its read budget.') from None
    finally:
        db.close()
