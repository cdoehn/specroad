"""Additive authority for one new attempt; original request rows stay immutable."""
import math
import sqlite3
import time

from .apply_reconcile_proof import canonical, hashed
from .config import digest
from .contracts import facts
from .errors import ControlError
from .handover_history import history_digest
from .job_contract import contract, new_contract
from .local import decode_object

TABLE = 'blocked_clarification_authorizations'


def fail(message):
    raise ControlError('blocked_clarification_invalid', message)


def records(ledger):
    if not ledger.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone():
        return []
    return ledger.db.execute('SELECT * FROM blocked_clarification_authorizations ORDER BY rowid').fetchall()


def history_hash(ledger):
    return history_digest(ledger.db, ignore={TABLE})


def decode(ledger, row):
    doc = decode_object(row['proof'])
    fields = {'version', 'source', 'scope', 'config_sha256', 'history_sha256', 'previous_contract',
              'selected_contract', 'original_job', 'attempt_number', 'evidence', 'reason'}
    if (set(doc) != fields or type(doc['version']) is not int or doc['version'] != 1
            or hashed(doc) != row['proof_sha'] or row['state'] not in ('pending', 'completed')
            or row['output_kind'] not in (None, 'patch_ready', 'patch_ready_with_clarification', 'unknown')):
        raise ValueError('Invalid grant record')
    source = facts(doc['source'], 'result')
    if source['sha256'] != row['source_sha']:
        raise ValueError('Wrong source')
    for key in ('scope', 'config_sha256', 'history_sha256'):
        digest(doc[key])
    previous, selected = contract(doc['previous_contract']), contract(doc['selected_contract'])
    if (previous['version'] != 4 or previous['clarification_allowed']
            or previous['clarification_continuation'] or previous['clarifications_remaining'] <= 0
            or selected != new_contract(previous['clarifications_remaining'], version=4)
            or ledger.recorded_contract(row['source_sha']) != previous):
        raise ValueError('Original authority or budget changed')
    before = doc['original_job']
    if (set(before) != {'stage', 'error', 'patch_sha', 'updated'}
            or before['stage'] != 'uncertain' or before['error'] != 'dev_blocked'
            or before['patch_sha'] is not None or type(before['updated']) not in (int, float)
            or not math.isfinite(before['updated'])
            or type(doc['attempt_number']) is not int or not 0 <= doc['attempt_number'] <= 8
            or not isinstance(doc['reason'], str) or not doc['reason'].strip()
            or doc['reason'] != doc['reason'].strip() or len(doc['reason']) > 512
            or not doc['reason'].isprintable()
            or set(doc['evidence']) != {'attempt.json', 'dispatch.json', 'protocol-completion.json', 'completion.json'}):
        raise ValueError('Invalid original attempt')
    for name, value in doc['evidence'].items():
        if name != 'dispatch.json' or value is not None:
            digest(value)
    old = ledger.db.execute('SELECT * FROM jobs WHERE sha=?', (row['source_sha'],)).fetchone()
    if (old is None or decode_object(old['source']) != source
            or ledger.db.execute('SELECT output_kind FROM request_contracts WHERE sha=?', (row['source_sha'],)).fetchone()[0] is not None):
        raise ValueError('Original claim changed')
    if row['output_kind'] is not None and old['patch_sha'] is None:
        raise ValueError('Handoff lacks package')
    if row['state'] == 'pending':
        if (row['output_kind'] is not None or any(old[k] != v for k, v in before.items())
                or ledger.current()['sha'] != row['source_sha']
                or ledger.db.execute('SELECT scope FROM meta WHERE id=1').fetchone()[0] != doc['scope']
                or history_hash(ledger) != doc['history_sha256']):
            raise ValueError('Pending history changed')
    return doc


def validate_history(ledger):
    try:
        pending = [decode(ledger, row) for row in records(ledger) if row['state'] == 'pending']
        for row in records(ledger):
            decode(ledger, row)
        if pending:
            from .clarification_authorization_history import records as successor_records
            from .apply_reconcile_history import records as reconciliation_records
            if any(row['state'] == 'pending' for row in successor_records(ledger) + reconciliation_records(ledger)):
                raise ValueError('Competing offline transition')
        if len(pending) > 1:
            raise ValueError('Competing grants')
        return pending[0] if pending else None
    except (sqlite3.Error, ValueError, KeyError, IndexError, TypeError, UnicodeError):
        fail('Damaged blocked-authorization history is preserved; no dispatch.')


def active(ledger, source_sha):
    for row in records(ledger):
        if row['source_sha'] == source_sha and row['state'] == 'completed':
            try:
                return decode(ledger, row)
            except (sqlite3.Error, ValueError, KeyError, IndexError, TypeError, UnicodeError):
                fail('Invalid effective authorization.')
    return None


def persist(ledger, doc):
    with ledger.transaction():
        if validate_history(ledger) is not None or history_hash(ledger) != doc['history_sha256']:
            fail('History changed before publication.')
        ledger.db.execute('CREATE TABLE IF NOT EXISTS blocked_clarification_authorizations '
                          '(source_sha TEXT PRIMARY KEY, proof TEXT NOT NULL, proof_sha TEXT NOT NULL, '
                          'state TEXT NOT NULL, output_kind TEXT)')
        ledger.db.execute("INSERT INTO blocked_clarification_authorizations VALUES(?,?,?,'pending',NULL)",
                          (doc['source']['sha256'], canonical(doc).decode(), hashed(doc)))
        validate_history(ledger)


def complete(ledger, doc):
    try:
        with ledger.transaction():
            if validate_history(ledger) != doc:
                fail('Authorization changed before adoption.')
            # Only the current lifecycle summary advances. The complete old
            # summary is pinned in the additive proof; all old files and the
            # request_contracts/budgets rows retain their original bytes/values.
            ledger.db.execute("UPDATE jobs SET stage='ready',error=NULL,updated=? WHERE sha=?",
                              (time.time(), doc['source']['sha256']))
            ledger.db.execute("UPDATE blocked_clarification_authorizations SET state='completed' WHERE source_sha=?",
                              (doc['source']['sha256'],))
            validate_history(ledger)
    except sqlite3.Error:
        fail('Authorization adoption rolled back together with the lifecycle update.')


def require_no_pending(ledger):
    if validate_history(ledger) is not None:
        raise ControlError('clarification_authorization_pending', 'Resolve the pinned blocked authorization first.')


def directory(paths, ledger, source_sha, number):
    from .retry_ledger import attempt_directory
    grant = active(ledger, source_sha)
    if grant is not None and number >= grant['attempt_number']:
        return paths.state / 'jobs' / source_sha / 'authorized' / f'{number:04d}'
    return attempt_directory(paths, source_sha, number)
