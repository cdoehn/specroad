"""Durable Apply repair budgets, separate from model retries and clarification.

Rows bind actual sources and their predecessor. Reading, restart and retry do
not spend a place. Only adoption of a bound repair Result advances the count.
"""
import json
import sqlite3
from hashlib import sha256

from .errors import ControlError


TABLE = 'apply_correction_budgets'


def _fail():
    raise ControlError('correction_budget_invalid', 'Preserve invalid correction budget history; no new dispatch.')


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _row(ledger, source_sha):
    try:
        if not ledger.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone():
            return None
        row = ledger.db.execute('SELECT proof,sha256 FROM ' + TABLE + ' WHERE source_sha=?', (source_sha,)).fetchone()
        if row is None:
            return None
        value = json.loads(row[0])
        if (set(value) != {'version', 'source_sha256', 'previous_sha256', 'maximum', 'remaining', 'active', 'reason'}
                or value['version'] != 1 or type(value['version']) is not int
                or value['source_sha256'] != source_sha
                or type(value['maximum']) is not int or not 1 <= value['maximum'] <= 5
                or type(value['remaining']) is not int or not 0 <= value['remaining'] <= value['maximum']
                or type(value['active']) is not bool
                or value['reason'] not in ('initial_checkpoint', 'verified_clean_apply', 'repair_result', 'preserved')
                or _canonical(value) != row[0] or sha256(row[0].encode()).hexdigest() != row[1]):
            _fail()
        for identity in (source_sha, value['previous_sha256']):
            if identity is not None and not ledger.db.execute('SELECT 1 FROM jobs WHERE sha=?', (identity,)).fetchone():
                _fail()
        if value['previous_sha256'] == source_sha:
            _fail()
        return value
    except (sqlite3.Error, ValueError, KeyError, TypeError):
        _fail()


def read(ledger, source_sha):
    value = _row(ledger, source_sha)
    cursor, seen = value, set()
    while cursor is not None:
        identity = cursor['source_sha256']
        if identity in seen:
            _fail()
        seen.add(identity)
        parent = cursor['previous_sha256']
        if parent is None:
            if (cursor['reason'] != 'initial_checkpoint'
                    or cursor['remaining'] != cursor['maximum']):
                _fail()
            break
        old = _row(ledger, parent)
        if old is None or cursor['reason'] == 'initial_checkpoint':
            _fail()
        if cursor['reason'] == 'verified_clean_apply':
            job = ledger.db.execute('SELECT source FROM jobs WHERE sha=?', (identity,)).fetchone()
            try:
                complete = _complete(json.loads(job[0]))
            except (ValueError, KeyError, TypeError):
                _fail()
            if not complete or cursor['active'] or cursor['remaining'] != cursor['maximum']:
                _fail()
        else:
            debit = int(cursor['reason'] == 'repair_result')
            if (cursor['maximum'] != old['maximum']
                    or cursor['remaining'] != old['remaining'] - debit
                    or debit and (not old['active'] or not cursor['active'])
                    or old['active'] and not cursor['active']):
                _fail()
        cursor = old
    return value


def _insert(ledger, value):
    ledger.db.execute('CREATE TABLE IF NOT EXISTS ' + TABLE +
                     ' (source_sha TEXT PRIMARY KEY,proof TEXT NOT NULL,sha256 TEXT NOT NULL)')
    raw = _canonical(value)
    ledger.db.execute('INSERT INTO ' + TABLE + ' VALUES(?,?,?)',
                     (value['source_sha256'], raw, sha256(raw.encode()).hexdigest()))


def _complete(source):
    return bool(source['success'] and not source['dirty'] and source.get('completed_commit')
                and source['completed_commit'] == source['binding']['base_commit'])


def _initial(source, limit):
    if type(limit) is not int or not 1 <= limit <= 5:
        _fail()
    # A successful initial bundle capture is not a failed Apply.
    return dict(version=1, source_sha256=source['sha256'], previous_sha256=None,
                maximum=limit, remaining=limit,
                active=source['operation'] == 'apply' and not _complete(source),
                reason='initial_checkpoint')


def bind(ledger, source, limit):
    with ledger.transaction():
        value = read(ledger, source['sha256'])
        if value is None:
            value = _initial(source, limit)
            _insert(ledger, value)
        return value


def advance(ledger, previous, source, limit, *, verified):
    """Called only inside the ledger's existing source-adoption transaction."""
    old = read(ledger, previous['sha256'])
    if old is None:
        old = _initial(previous, limit)
        _insert(ledger, old)
    if verified and _complete(source):
        value = dict(_initial(source, limit), active=False, reason='verified_clean_apply')
    else:
        # A failed initial implementation opens the repair sequence. Subsequent
        # bound Results spend one place whether or not a partial stage committed.
        spent = int(old['active'])
        if spent and old['remaining'] == 0:
            _fail()
        value = dict(old, source_sha256=source['sha256'],
                     remaining=old['remaining'] - spent,
                     active=old['active'] or not _complete(source),
                     reason='repair_result' if spent else 'preserved')
    value['previous_sha256'] = previous['sha256']
    _insert(ledger, value)


def require_available(value):
    if value['active'] and value['remaining'] == 0:
        raise ControlError('correction_budget_exhausted',
                           'Five or the configured number of Apply repairs are exhausted; operator action is required.')


def preserve(ledger, previous_sha, source):
    """Manual/unknown transitions carry an existing budget, never refill it."""
    old = read(ledger, previous_sha)
    if old is not None and previous_sha != source['sha256']:
        _insert(ledger, dict(old, source_sha256=source['sha256'],
                            previous_sha256=previous_sha, reason='preserved'))
