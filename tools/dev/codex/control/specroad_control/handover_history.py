"""Preserve existing ledger cells while atomically adding a thread handover."""
from hashlib import sha256
import re

from .errors import ControlError
from .job_contract import scope
from .ledger import Ledger
from .handover_evidence import canonical, validate_chain, conflict as fail


TABLE = 'thread_handovers'


def history_digest(db, *, exclude=None, ignore=frozenset()):
    """Bind every existing schema and cell, except the intentionally changed scope."""
    result = sha256()
    schemas = db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    for kind, name, sql in schemas:
        if name == TABLE or name in ignore:
            continue
        result.update(canonical([kind, name, sql]))
        if kind != 'table':
            continue
        if not re.fullmatch('[a-z_][a-z0-9_]*', name):
            fail('Unsupported history table name.')
        cursor = db.execute('SELECT * FROM "' + name + '"')
        columns = [value[0] for value in cursor.description]
        rows = []
        for record in cursor:
            row = dict(zip(columns, record))
            if name == 'meta':
                row.pop('scope', None)
            rows.append(canonical(row))
        for raw in sorted(rows):
            result.update(raw)
    if any(name == TABLE for _, name, _ in schemas):
        for record_id, receipt in db.execute('SELECT id,receipt FROM thread_handovers ORDER BY rowid'):
            if record_id != exclude:
                result.update(canonical([record_id, receipt]))
    return result.hexdigest()


def last_receipt(db):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone():
        return None
    row = db.execute('SELECT receipt FROM thread_handovers ORDER BY rowid DESC LIMIT 1').fetchone()
    return row[0] if row else None


def open_history(path, old, new, intent):
    try:
        return Ledger(path, scope(old))
    except ControlError as exc:
        if exc.code != 'ledger_scope_mismatch' or intent is None:
            raise
        return Ledger(path, scope(new))


def commit_history(history, receipt):
    """Scope and additive receipt either both commit or neither does."""
    raw = canonical(receipt).decode()
    db = history.db
    with history.transaction():
        actual_scope = db.execute('SELECT scope FROM meta WHERE id=1').fetchone()[0]
        db.execute('CREATE TABLE IF NOT EXISTS thread_handovers (id TEXT PRIMARY KEY, receipt TEXT NOT NULL)')
        existing = db.execute('SELECT receipt FROM thread_handovers WHERE id=?', (receipt['id'],)).fetchone()
        if actual_scope == receipt['new_scope']:
            if existing is None or existing[0] != raw:
                fail('New history scope has no matching handover receipt.')
        elif actual_scope == receipt['old_scope']:
            if existing is not None or history_digest(db) != receipt['history_sha256']:
                fail('History changed before handover.')
            previous = last_receipt(db)
            if (sha256(previous.encode()).hexdigest() if previous else None) != receipt['previous_sha256']:
                fail('Earlier handover evidence changed.')
            db.execute('INSERT INTO thread_handovers VALUES (?,?)', (receipt['id'], raw))
            db.execute('UPDATE meta SET scope=? WHERE id=1 AND scope=?', (receipt['new_scope'], receipt['old_scope']))
        else:
            fail('Neither original nor intended history scope is present.')
        if history_digest(db, exclude=receipt['id']) != receipt['history_sha256']:
            fail('Existing history changed during handover.')


def verify_commit(history, receipt):
    current_scope = history.db.execute('SELECT scope FROM meta WHERE id=1').fetchone()[0]
    validate_chain(history.db, current_scope)
    row = history.db.execute('SELECT receipt FROM thread_handovers WHERE id=?', (receipt['id'],)).fetchone()
    if current_scope != receipt['new_scope'] or row is None or row[0] != canonical(receipt).decode():
        fail('Committed scope or handover receipt changed before publication.')
