"""One additive operator receipt per accepted Result; never rewrite old authority."""
import math
import sqlite3
import time

from .apply_reconcile_proof import canonical, hashed
from .config import digest
from .contracts import facts
from .current_acceptance_proof import fail, stable
from .handover_history import history_digest
from .job_contract import contract, new_contract
from .local import decode_object

TABLE = 'current_acceptances'


def selection(previous, output_kind, clarification, mode):
    # A published clarification may not yet have reached inherit_contract.
    # Charge it once when archiving that source, never silently restore it.
    debit = int(mode == 'successor' and (output_kind == 'spec_clarification'
        or output_kind == 'patch_ready_with_clarification' and not previous.get('clarification_continuation')))
    remaining = previous['clarifications_remaining'] - debit
    if remaining < 0 or clarification and remaining == 0:
        raise ValueError('No unspent clarification budget')
    return new_contract(remaining, version=4,
        allowed=clarification or mode == 'same_ready' and previous['clarification_allowed'])


def records(ledger):
    if not ledger.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone():
        return []
    return ledger.db.execute('SELECT * FROM current_acceptances ORDER BY rowid').fetchall()


def history_hash(ledger):
    return history_digest(ledger.db, ignore={TABLE})


def document(row):
    doc = decode_object(row['proof'])
    fields = {'version', 'source', 'target', 'scope', 'config_sha256', 'history_sha256',
              'previous_contract', 'previous_output_kind', 'selected_contract', 'original_job', 'mode',
              'attempt_number', 'evidence', 'reason', 'clarification', 'artifacts'}
    if (set(doc) != fields or type(doc['version']) is not int or doc['version'] != 1
            or hashed(doc) != row['proof_sha'] or row['state'] not in ('pending', 'completed')
            or row['output_kind'] not in (None, 'patch_ready', 'patch_ready_with_clarification', 'unknown')):
        raise ValueError('Invalid acceptance receipt')
    source, target = facts(doc['source'], 'result'), facts(doc['target'], 'result')
    if source['sha256'] != row['source_sha'] or target['sha256'] != row['target_sha']:
        raise ValueError('Receipt identity changed')
    for field in ('scope', 'config_sha256', 'history_sha256'):
        digest(doc[field])
    previous, selected = contract(doc['previous_contract']), contract(doc['selected_contract'])
    if (previous['version'] not in (3, 4) or previous.get('clarification_continuation')
            or type(doc['clarification']) is not bool
            or doc['clarification'] and previous['clarifications_remaining'] == 0
            or doc['previous_output_kind'] not in (None, 'unknown', 'patch_ready', 'spec_clarification', 'patch_ready_with_clarification')
            or selected != selection(previous, doc['previous_output_kind'], doc['clarification'], doc['mode'])):
        raise ValueError('Receipt changed the preserved budget or selected authority')
    before = doc['original_job']
    if (set(before) != {'stage', 'error', 'patch_sha', 'updated'}
            or before['stage'] not in ('ready', 'uncertain', 'waiting_result', 'no_work')
            or type(before['updated']) not in (int, float) or not math.isfinite(before['updated'])
            or doc['mode'] not in ('successor', 'same_ready', 'same_blocked')
            or (source['sha256'] == target['sha256']) != (doc['mode'] != 'successor')
            or type(doc['attempt_number']) is not int or not 0 <= doc['attempt_number'] <= 8
            or not isinstance(doc['reason'], str) or doc['reason'] != doc['reason'].strip()
            or not doc['reason'] or len(doc['reason']) > 512 or not doc['reason'].isprintable()):
        raise ValueError('Invalid operator intent')
    if doc['mode'] != 'successor' and doc['previous_output_kind'] is not None:
        raise ValueError('Same-source retry already produced output')
    if doc['mode'] == 'same_ready' and (before['stage'] != 'ready' or before['patch_sha'] is not None or doc['attempt_number'] != 0):
        raise ValueError('A ready Result must be unissued')
    if doc['mode'] == 'same_blocked':
        if (before['stage'] != 'uncertain' or before['error'] != 'dev_blocked'
                or before['patch_sha'] is not None or previous['version'] != 4
                or previous['clarification_allowed'] or not doc['clarification']
                or set(doc['evidence']) != {'attempt.json', 'dispatch.json', 'protocol-completion.json', 'completion.json'}):
            raise ValueError('Unsupported same-source retry')
        for key, value in doc['evidence'].items():
            if key != 'dispatch.json' or value is not None:
                digest(value)
    elif doc['evidence'] is not None:
        raise ValueError('Unexpected retry evidence')
    artifacts = doc['artifacts']
    if set(artifacts) != {'parent', 'patch', 'result', 'plan_sha256', 'program_sha256', 'snapshot_sha256'}:
        raise ValueError('Invalid selected-state proof')
    for key in ('plan_sha256', 'program_sha256', 'snapshot_sha256'):
        digest(artifacts[key])
    for key in ('parent', 'patch', 'result'):
        facts(artifacts[key], 'patch' if key == 'patch' else 'result')
    if (stable(artifacts['result']) != stable(target) or not target['success'] or target['dirty']
            or target['dry_run'] or target['operation'] != 'apply' or not target['entrypoint_started']
            or target['completed_commit'] != target['binding']['base_commit']
            or artifacts['patch']['sha256'] != target['patch_sha256']
            or artifacts['patch']['binding'] != artifacts['parent']['binding']
            or target['expected'] != artifacts['parent']['binding']
            or target['repository_path'] != source['repository_path']):
        raise ValueError('Selected state is not a complete same-repository Apply')
    return doc


def active(ledger, target_sha):
    try:
        for row in records(ledger):
            if row['target_sha'] == target_sha and row['state'] == 'completed':
                return document(row)
    except (sqlite3.Error, ValueError, KeyError, TypeError, UnicodeError):
        fail('Damaged effective current-state acceptance.')
    return None


def validate_history(ledger):
    try:
        pending = []
        for row in records(ledger):
            doc = document(row)
            old = ledger.db.execute('SELECT * FROM jobs WHERE sha=?', (row['source_sha'],)).fetchone()
            if old is None or stable(decode_object(old['source'])) != stable(doc['source']):
                raise ValueError('Original job changed')
            previous = (ledger.recorded_contract(row['source_sha']) if doc['mode'] != 'successor'
                        else ledger.request_contract(row['source_sha']))
            if previous != doc['previous_contract']:
                raise ValueError('Original authority changed')
            output = (ledger.output_kind(row['source_sha']) if doc['mode'] == 'successor'
                else ledger.db.execute('SELECT output_kind FROM request_contracts WHERE sha=?', (row['source_sha'],)).fetchone()[0])
            if output != doc['previous_output_kind']:
                raise ValueError('Original output classification changed')
            target = ledger.db.execute('SELECT * FROM jobs WHERE sha=?', (row['target_sha'],)).fetchone()
            if row['state'] == 'pending':
                if (ledger.current()['sha'] != row['source_sha'] or row['output_kind'] is not None
                        or any(old[k] != v for k, v in doc['original_job'].items())
                        or history_hash(ledger) != doc['history_sha256']
                        or doc['mode'] == 'successor' and target is not None
                        or ledger.db.execute('SELECT scope FROM meta WHERE id=1').fetchone()[0] != doc['scope']):
                    raise ValueError('Pending intent changed')
                pending.append(doc)
            elif (target is None or stable(decode_object(target['source'])) != stable(doc['target'])
                    or doc['mode'] == 'successor' and (old['stage'] != 'done'
                        or any(old[k] != doc['original_job'][k] for k in ('error', 'patch_sha')))
                    or row['output_kind'] is not None and target['patch_sha'] is None):
                raise ValueError('Completed adoption changed')
        if len(pending) > 1:
            raise ValueError('Competing acceptances')
        if pending:
            for table in ('apply_reconciliations', 'clarification_authorizations', 'blocked_clarification_authorizations'):
                if ledger.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                    if ledger.db.execute(f"SELECT 1 FROM {table} WHERE state='pending'").fetchone():
                        raise ValueError('Competing offline transition')
        return pending[0] if pending else None
    except (sqlite3.Error, ValueError, KeyError, TypeError, UnicodeError, IndexError):
        fail('Damaged current-state acceptance history is preserved; no dispatch.')


def require_no_pending(ledger):
    if validate_history(ledger) is not None:
        fail('A current-state acceptance is already pending.')


def persist(ledger, doc):
    with ledger.transaction():
        if validate_history(ledger) is not None or history_hash(ledger) != doc['history_sha256']:
            fail('History changed before receipt publication.')
        ledger.db.execute('CREATE TABLE IF NOT EXISTS current_acceptances '
            '(target_sha TEXT PRIMARY KEY, source_sha TEXT NOT NULL, proof TEXT NOT NULL, '
            'proof_sha TEXT NOT NULL, state TEXT NOT NULL, output_kind TEXT)')
        ledger.db.execute("INSERT INTO current_acceptances VALUES(?,?,?,?,'pending',NULL)",
            (doc['target']['sha256'], doc['source']['sha256'], canonical(doc).decode(), hashed(doc)))
        validate_history(ledger)


def complete(ledger, doc):
    try:
        with ledger.transaction():
            if validate_history(ledger) != doc:
                fail('Acceptance changed before adoption.')
            target = doc['target']
            if doc['mode'] == 'successor':
                ledger.db.execute("UPDATE jobs SET stage='done',updated=? WHERE sha=?", (time.time(), doc['source']['sha256']))
                ledger.db.execute("INSERT INTO jobs VALUES(?,?,?,'ready',NULL,NULL,?)",
                    (target['run_id'], target['sha256'], canonical(target).decode(), time.time()))
                ledger._insert_contract(target['sha256'], doc['selected_contract'])
                ledger.db.execute('UPDATE meta SET current=? WHERE id=1', (target['run_id'],))
            else:
                ledger.db.execute("UPDATE jobs SET stage='ready',error=NULL,updated=? WHERE sha=?", (time.time(), target['sha256']))
            ledger.db.execute("UPDATE current_acceptances SET state='completed' WHERE target_sha=?", (target['sha256'],))
            validate_history(ledger)
            from .apply_reconcile_history import validate_history as recovery
            from .clarification_authorization_history import validate_history as successor
            from .blocked_authorization_history import validate_history as blocked
            recovery(ledger); successor(ledger); blocked(ledger)
    except sqlite3.Error:
        fail('Acceptance and lifecycle changes rolled back together.')
