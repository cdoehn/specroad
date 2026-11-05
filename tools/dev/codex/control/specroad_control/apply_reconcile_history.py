"""Atomic, additive persistence for a hash-bound Apply reconciliation request."""
import sqlite3
import time
from .decision_policy import successor_contract
from .mixed_contract import IMPLEMENTATIONS
from .apply_reconcile_proof import canonical, hashed, fail
from .config import digest
from .contracts import facts
from .errors import ControlError
from .handover_history import history_digest
from .local import decode_object

TABLE = 'apply_reconciliations'
ARTIFACTS = ('source', 'original', 'checkpoint', 'resumed', 'result')


def history_hash(ledger):
    return history_digest(ledger.db, ignore={TABLE})

def stable(proof):
    # The opt-in is re-derived from the SAME hash-validated ZIP. Its additive
    # reader field must not invalidate older immutable recovery receipts.
    if 'steps' in proof:
        return {**stable({key: value for key, value in proof.items() if key != 'steps'}),
                'steps': [{**{key: value for key, value in step.items() if key not in ('source', 'patch', 'result')},
                           **{key: {name: value for name, value in step[key].items()
                                    if name not in ('path', 'development_contract')}
                              for key in ('source', 'patch', 'result')}} for step in proof['steps']]}
    return {k: ({key: item for key, item in value.items() if key not in ('path', 'development_contract')}
                if k in ARTIFACTS else value) for k, value in proof.items()}


def validate_extended(chain):
    if set(chain) != {'source', 'result', 'steps', 'chain_sha256'} or not isinstance(chain['steps'], list) or not 0 < len(chain['steps']) <= 32:
        raise ValueError
    digest(chain['chain_sha256']); facts(chain['source'], 'result'); facts(chain['result'], 'result')
    previous, seen, patches, hashes = chain['source'], {chain['source']['run_id']}, set(), []
    for step in chain['steps']:
        if set(step) != {'source', 'patch', 'result', 'kind', 'plan_sha256', 'program_sha256', 'progress_sha256', 'snapshot_sha256'}:
            raise ValueError
        for key in ('source', 'patch', 'result'):
            facts(step[key], 'patch' if key == 'patch' else 'result')
        source, patch, result = (step[key] for key in ('source', 'patch', 'result'))
        if (stable({'source': source}) != stable({'source': previous})
                or patch['binding'] != source['binding'] or result['expected'] != source['binding']
                or result['patch_sha256'] != patch['sha256'] or result['run_id'] in seen
                or patch['sha256'] in patches or result['repository_path'] != source['repository_path']
                or result['operation'] != 'apply' or result['dry_run'] or not result['entrypoint_started']):
            raise ValueError
        if step['kind'] == 'unchanged_push':
            if (step['plan_sha256'] is not None or step['program_sha256'] is not None
                    or result['binding'] != source['binding'] or not result['success']
                    or result['dirty'] or result['completed_commit'] is not None):
                raise ValueError
        elif step['kind'] in ('completed_plan', 'failed_gate', 'timeout'):
            digest(step['plan_sha256']); digest(step['program_sha256'])
            if step['kind'] == 'completed_plan':
                if not result['success'] or result['dirty'] or result['completed_commit'] != result['binding']['base_commit']:
                    raise ValueError
            elif (result['success'] or not result['dirty'] or result['completed_commit'] is not None
                  or result['primary_kind'] != ('timeout' if step['kind'] == 'timeout' else 'entrypoint_exit')):
                raise ValueError
        else:
            raise ValueError
        digest(step['progress_sha256']); digest(step['snapshot_sha256'])
        hashes.append({key: value for key, value in step.items() if key not in ('source', 'patch', 'result')}
                      | {key + '_sha256': step[key]['sha256'] for key in ('source', 'patch', 'result')})
        seen.add(result['run_id']); patches.add(patch['sha256']); previous = result
    if (chain['steps'][-1]['kind'] != 'completed_plan' or chain['chain_sha256'] != hashed(hashes)
            or stable({'result': previous}) != stable({'result': chain['result']})):
        raise ValueError

def records(ledger):
    if not ledger.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone():
        return []
    return ledger.db.execute('SELECT * FROM apply_reconciliations ORDER BY rowid').fetchall()

def validate_history(ledger):
    try:
        pending = []
        for row in records(ledger):
            doc = decode_object(row['proof'])
            if (set(doc) != {'version', 'scope', 'config_sha256', 'history_sha256', 'evidence', 'artifacts'}
                    or hashed(doc) != row['proof_sha'] or type(doc['version']) is not int or doc['version'] not in (1, 2, 3)
                    or doc['artifacts']['source']['sha256'] != row['source_sha']
                    or row['state'] not in ('pending', 'completed')):
                raise ValueError
            for field in ('scope', 'config_sha256', 'history_sha256'):
                digest(doc[field])
            if set(doc['evidence']) != {'attempt.json', 'protocol-completion.json', 'completion.json'}:
                raise ValueError
            for value in doc['evidence'].values():
                digest(value)
            chain = doc['artifacts']
            hash_fields = {'original_plan_sha256', 'resumed_plan_sha256', 'program_sha256', 'completion_sha256'}
            blocked = doc['version'] in (2, 3)
            extended = doc['version'] == 3
            if blocked and not extended:
                hash_fields |= {'checkpoint_progress_sha256', 'snapshot_sha256'}
            if extended:
                validate_extended(chain)
            else:
                if set(chain) != set(ARTIFACTS) | hash_fields:
                    raise ValueError
                for key in hash_fields:
                    digest(chain[key])
                for key in ARTIFACTS:
                    facts(chain[key], 'patch' if key in ('original', 'resumed') else 'result')
            old = ledger.db.execute('SELECT * FROM jobs WHERE sha=?', (row['source_sha'],)).fetchone()
            if (old is None or old['patch_sha'] != (None if blocked else chain['original']['sha256'])
                    or (blocked and old['error'] != 'dev_blocked')
                    or stable({'source': decode_object(old['source'])}) != stable({'source': chain['source']})):
                raise ValueError
            kind = ledger.db.execute('SELECT output_kind FROM request_contracts WHERE sha=?', (row['source_sha'],)).fetchone()
            if kind is None or (kind[0] is not None if blocked else kind[0] not in IMPLEMENTATIONS):
                raise ValueError
            if not extended and (chain['original']['binding'] != chain['source']['binding']
                    or chain['resumed']['binding'] != chain['checkpoint']['binding']
                    or chain['result']['expected'] != chain['checkpoint']['binding']
                    or chain['result']['patch_sha256'] != chain['resumed']['sha256']):
                raise ValueError
            if blocked and not extended and (chain['checkpoint']['expected'] != chain['source']['binding']
                            or chain['checkpoint']['patch_sha256'] != chain['original']['sha256']
                            or chain['checkpoint']['success'] or not chain['checkpoint']['dirty']
                            or not chain['result']['success'] or chain['result']['dirty']
                            or chain['result']['completed_commit'] != chain['result']['binding']['base_commit']):
                raise ValueError
            if row['state'] == 'pending':
                pending.append(doc)
                if (ledger.current()['sha'] != row['source_sha'] or old['stage'] != ('uncertain' if blocked else 'waiting_result')
                        or doc['history_sha256'] != history_hash(ledger)):
                    raise ValueError
            else:
                new = ledger.db.execute('SELECT source FROM jobs WHERE sha=?', (chain['result']['sha256'],)).fetchone()
                if old['stage'] != 'done' or new is None or stable({'result': decode_object(new['source'])}) != stable({'result': chain['result']}):
                    raise ValueError
        if len(pending) > 1:
            raise ValueError
        return pending[0] if pending else None
    except (sqlite3.Error, ValueError, KeyError, TypeError, UnicodeError, IndexError):
        raise ControlError('invalid_apply_reconciliation', 'Damaged recovery history is preserved; no dispatch.') from None

def persist(ledger, doc):
    with ledger.transaction():
        previous = validate_history(ledger)
        if previous is not None:
            if previous != doc:
                fail('A different reconciliation is already pending.')
            return
        if history_hash(ledger) != doc['history_sha256']:
            fail('History changed before queue publication.')
        ledger.db.execute('CREATE TABLE IF NOT EXISTS apply_reconciliations '
                          '(source_sha TEXT PRIMARY KEY, proof TEXT NOT NULL, proof_sha TEXT NOT NULL, state TEXT NOT NULL)')
        ledger.db.execute("INSERT INTO apply_reconciliations VALUES(?,?,?,'pending')",
                          (doc['artifacts']['source']['sha256'], canonical(doc).decode(), hashed(doc)))

def complete(ledger, doc, actual):
    try:
        with ledger.transaction():
            if validate_history(ledger) != doc:
                fail('The pending request changed before adoption.')
            if stable(actual) != stable(doc['artifacts']):
                fail('Adoption facts differ from the pinned request.')
            if doc['version'] in (2, 3):
                adopt_blocked(ledger, actual['result'])
            else:
                ledger._enqueue(actual['result'], decision_evidence={'verified': True})
            ledger.db.execute("UPDATE apply_reconciliations SET state='completed' WHERE source_sha=? AND state='pending'",
                              (doc['artifacts']['source']['sha256'],))
            validate_history(ledger)
    except sqlite3.Error:
        raise ControlError('apply_reconciliation_persist_failed', 'Proof and advancement rolled back together.') from None

def require_no_pending(ledger):
    from .clarification_authorization_history import require_no_pending as require_no_authorization
    require_no_authorization(ledger)
    if validate_history(ledger) is not None:
        raise ControlError('apply_reconciliation_pending', 'A pinned Apply recovery must finish before configuration, handover or other offline work.')


def adopt_blocked(ledger, source):
    """Called only inside the verified request transaction; no synthetic handoff."""
    old = ledger.current()
    if (old['stage'] != 'uncertain' or old['error'] != 'dev_blocked'
            or old['patch_sha'] is not None or ledger.output_kind() is not None):
        fail('The blocked claim changed before adoption.')
    if ledger.db.execute('SELECT 1 FROM jobs WHERE run_id=? OR sha=?',
                         (source['run_id'], source['sha256'])).fetchone():
        fail('The corrected Result was already claimed.')
    selected = successor_contract(ledger.request_contract(), 'unknown', source)
    ledger.db.execute("UPDATE jobs SET stage='done', updated=? WHERE run_id=?", (time.time(), old['run_id']))
    ledger.db.execute("INSERT INTO jobs VALUES(?,?,?,'ready',NULL,NULL,?)",
                      (source['run_id'], source['sha256'], canonical(source).decode(), time.time()))
    ledger.db.execute('UPDATE meta SET current=? WHERE id=1', (source['run_id'],))
    ledger._insert_contract(source['sha256'], selected)
