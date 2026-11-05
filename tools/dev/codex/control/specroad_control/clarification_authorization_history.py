"""Atomic, additive user authorization; original attempts and budgets survive."""
import math
import sqlite3
import time

from .apply_reconcile_proof import canonical, hashed
from .handover_history import history_digest
from .job_contract import contract, new_contract
from .local import decode_object
from .errors import ControlError
from .config import digest
from .contracts import facts
from .mixed_contract import supports_v4

TABLE = 'clarification_authorizations'


def fail(message):
    raise ControlError('invalid_clarification_authorization', message)


def history_hash(ledger):
    return history_digest(ledger.db, ignore={TABLE})


def stable(artifacts):
    return {k: {n: v for n, v in value.items() if n != 'path'} if k in ('source', 'patch', 'result') else value
            for k, value in artifacts.items()}


def records(ledger):
    if not ledger.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone():
        return []
    return ledger.db.execute('SELECT * FROM clarification_authorizations ORDER BY rowid').fetchall()


def validate_history(ledger):
    try:
        pending = []
        for row in records(ledger):
            doc = decode_object(row['proof'])
            if (set(doc) != {'version', 'source_sha256', 'target_sha256', 'scope', 'config_sha256', 'history_sha256',
                            'previous_contract', 'selected_contract', 'reason', 'original_job', 'evidence', 'artifacts'}
                    or type(doc['version']) is not int or doc['version'] != 1 or hashed(doc) != row['proof_sha']
                    or row['state'] not in ('pending', 'completed') or row['source_sha'] != doc['source_sha256']
                    or row['target_sha'] != doc['target_sha256'] or row['source_sha'] == row['target_sha']):
                raise ValueError
            for key in ('source_sha256', 'target_sha256', 'scope', 'config_sha256', 'history_sha256'):
                digest(doc[key])
            if (not isinstance(doc['reason'], str) or not doc['reason'].strip()
                    or doc['reason'] != doc['reason'].strip() or len(doc['reason']) > 512
                    or not doc['reason'].isprintable()
                    or set(doc['evidence']) != {'attempt.json', 'dispatch.json', 'protocol-completion.json', 'completion.json'}):
                raise ValueError
            for value in doc['evidence'].values():
                if value is not None:
                    digest(value)
            before = doc['original_job']
            if (set(before) != {'stage', 'error', 'patch_sha', 'updated'}
                    or type(before['updated']) not in (int, float) or not math.isfinite(before['updated'])
                    or before['stage'] not in ('uncertain', 'waiting_result')
                    or (before['stage'] == 'uncertain' and (before['error'] not in ('dev_blocked', 'codex_turn_failed')
                        or before['patch_sha'] is not None or doc['evidence']['attempt.json'] is None))):
                raise ValueError
            if before['stage'] == 'waiting_result':
                digest(before['patch_sha'])
            previous, selected = contract(doc['previous_contract']), contract(doc['selected_contract'])
            if (previous['version'] not in (3, 4) or previous['clarifications_remaining'] <= 0
                    or previous.get('clarification_continuation', False)
                    or selected != new_contract(previous['clarifications_remaining'], version=4)
                    or ledger.request_contract(row['source_sha']) != previous):
                raise ValueError
            artifacts = doc['artifacts']
            if set(artifacts) != {'source', 'patch', 'result', 'plan_sha256', 'completion_sha256'}:
                raise ValueError
            for key in ('plan_sha256', 'completion_sha256'):
                digest(artifacts[key])
            for key in ('source', 'patch', 'result'):
                facts(artifacts[key], 'patch' if key == 'patch' else 'result')
            target = artifacts['result']
            if (not target['success'] or target['dirty'] or target['dry_run'] or target['operation'] != 'apply'
                    or not target['entrypoint_started'] or not target.get('completed_commit')
                    or target['completed_commit'] != target['binding']['base_commit'] or not supports_v4(target)):
                raise ValueError
            if (artifacts['source']['sha256'] != row['source_sha'] or artifacts['result']['sha256'] != row['target_sha']
                    or artifacts['patch']['binding'] != artifacts['source']['binding']
                    or artifacts['result']['expected'] != artifacts['source']['binding']
                    or artifacts['result']['patch_sha256'] != artifacts['patch']['sha256']):
                raise ValueError
            old = ledger.db.execute('SELECT * FROM jobs WHERE sha=?', (row['source_sha'],)).fetchone()
            if old is None or stable({'source': decode_object(old['source'])}) != stable({'source': artifacts['source']}):
                raise ValueError
            if (old['error'] != before['error'] or old['patch_sha'] != before['patch_sha']
                    or (before['patch_sha'] is not None and before['patch_sha'] != artifacts['patch']['sha256'])):
                raise ValueError
            output = ledger.output_kind(row['source_sha'])
            if output != ('unknown' if before['stage'] == 'waiting_result' else None):
                raise ValueError
            if row['state'] == 'pending':
                if old['stage'] != before['stage'] or old['updated'] != before['updated']:
                    raise ValueError
                if ledger.db.execute('SELECT scope FROM meta WHERE id=1').fetchone()[0] != doc['scope']:
                    raise ValueError
                from .clarification_authorization import original
                current, _ = original(ledger)
                if current['sha'] != row['source_sha'] or history_hash(ledger) != doc['history_sha256']:
                    raise ValueError
                if ledger.db.execute('SELECT 1 FROM jobs WHERE sha=? OR run_id=?',
                                     (row['target_sha'], artifacts['result']['run_id'])).fetchone():
                    raise ValueError
                pending.append(doc)
            else:
                target = ledger.db.execute('SELECT source FROM jobs WHERE sha=?', (row['target_sha'],)).fetchone()
                if (old['stage'] != 'done' or target is None
                        or stable({'result': decode_object(target['source'])}) != stable({'result': artifacts['result']})
                        or ledger.request_contract(row['target_sha']) != selected):
                    raise ValueError
        if pending:
            from .apply_reconcile_history import records as reconciliations
            if any(row['state'] == 'pending' for row in reconciliations(ledger)):
                raise ValueError
        if len(pending) > 1:
            raise ValueError
        return pending[0] if pending else None
    except (sqlite3.Error, ValueError, KeyError, IndexError, TypeError, UnicodeError):
        fail('Damaged authorization history is preserved; no dispatch.')


def persist(ledger, doc):
    with ledger.transaction():
        if validate_history(ledger) is not None or history_hash(ledger) != doc['history_sha256']:
            fail('History changed before authorization publication.')
        ledger.db.execute('CREATE TABLE IF NOT EXISTS clarification_authorizations '
                          '(source_sha TEXT PRIMARY KEY, target_sha TEXT UNIQUE NOT NULL, proof TEXT NOT NULL, '
                          'proof_sha TEXT NOT NULL, state TEXT NOT NULL)')
        ledger.db.execute("INSERT INTO clarification_authorizations VALUES(?,?,?,?,'pending')",
                          (doc['source_sha256'], doc['target_sha256'], canonical(doc).decode(), hashed(doc)))
        validate_history(ledger)


def complete(ledger, doc, actual):
    try:
        with ledger.transaction():
            if validate_history(ledger) != doc or stable(actual) != stable(doc['artifacts']):
                fail('Authorization changed before its atomic adoption.')
            source = actual['result']
            # Keep old error, output classification, contract and all job files.
            ledger.db.execute("UPDATE jobs SET stage='done',updated=? WHERE sha=?", (time.time(), doc['source_sha256']))
            ledger.db.execute("INSERT INTO jobs VALUES(?,?,?,'ready',NULL,NULL,?)",
                              (source['run_id'], source['sha256'], canonical(source).decode(), time.time()))
            ledger.db.execute('UPDATE meta SET current=? WHERE id=1', (source['run_id'],))
            ledger._insert_contract(source['sha256'], doc['selected_contract'])
            ledger.db.execute("UPDATE clarification_authorizations SET state='completed' WHERE source_sha=?", (doc['source_sha256'],))
            validate_history(ledger)
    except sqlite3.Error:
        fail('Authorization and source advancement rolled back together.')


def require_no_pending(ledger):
    from .blocked_authorization_history import require_no_pending as blocked_pending
    blocked_pending(ledger)
    if validate_history(ledger) is not None:
        raise ControlError('clarification_authorization_pending', 'Resolve the pinned authorization before other offline work.')
