"""Explicit offline intent; only the existing idle-thread worker advances history."""
from hashlib import sha256
from pathlib import Path

from . import continuation
from .apply_reconcile_proof import canonical, hashed, prove, fail
from .config import load
from .errors import ControlError
from .job_contract import contract, scope
from .mixed_contract import IMPLEMENTATIONS
from .ledger import Ledger
from .local import decode_object, read_private
from .retry_ledger import attempt_directory

from .apply_reconcile_history import (history_hash, stable, records, validate_history,
                                      persist, complete, require_no_pending)


def _evidence(engine, ledger, *, blocked=False):
    row = ledger.current()
    if blocked:
        if (row['stage'] != 'uncertain' or row['error'] != 'dev_blocked'
                or row['patch_sha'] is not None or ledger.output_kind() is not None):
            fail('Only an unclassified dev_blocked job can use correction-chain recovery.')
    elif row['stage'] != 'waiting_result' or ledger.output_kind() not in IMPLEMENTATIONS:
        fail('Only a classified pending normal patch can be reconciled.')
    retry = ledger.retry_info(row['sha'])
    directory = attempt_directory(engine.paths, row['sha'], retry['number'] if retry else 0)
    names = ('attempt.json', 'protocol-completion.json', 'completion.json')
    raw = {name: read_private(directory / name) for name in names}
    attempt, protocol, answer = [decode_object(raw[name]) for name in names]
    if (protocol.get('completed') is not True or protocol.get('answer') != answer
            or protocol.get('transport') not in ('exec', 'app-server-proxy')
            or not isinstance(attempt.get('thread_id'), str) or not attempt['thread_id']
            or protocol.get('thread_id') != attempt.get('thread_id')
            or set(answer) != {'source_result_sha256', 'status', 'patch_sha256', 'message'}
            or answer['status'] != ('blocked' if blocked else ledger.output_kind())
            or answer['source_result_sha256'] != row['sha']
            or answer['patch_sha256'] != ('' if blocked else row['patch_sha'])
            or not isinstance(answer['message'], str)
            or attempt.get('source_sha256') != row['sha']
            or contract(attempt.get('request_contract')) != ledger.request_contract()):
        fail('Original dispatch and completion do not prove the pending normal handoff.')
    continuation.request_prompt(attempt, row['source'])
    return {name: sha256(content).hexdigest() for name, content in raw.items()}


def evidence(engine, ledger, *, blocked=False):
    try:
        return _evidence(engine, ledger, blocked=blocked)
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError):
        fail('Missing or malformed original dispatch/completion evidence.')


def proof_function(doc):
    if doc['version'] == 3:
        from .blocked_chain_extended import prove as extended_prove
        return extended_prove
    if doc['version'] == 2:
        from .blocked_chain_proof import prove as blocked_prove
        return blocked_prove
    return prove


def verify(engine, ledger, doc):
    if (sha256(read_private(engine.paths.config)).hexdigest() != doc['config_sha256']
            or scope(engine.config) != doc['scope'] or history_hash(ledger) != doc['history_sha256']
            or evidence(engine, ledger, blocked=doc['version'] in (2, 3)) != doc['evidence']):
        fail('Configuration, history or original completion changed after the explicit request.')
    chain = doc['artifacts']
    original = chain['steps'][0]['patch'] if doc['version'] == 3 else chain['original']
    actual = proof_function(doc)(engine, chain['source'], original['sha256'], chain['result'])
    if stable(actual) != stable(chain):
        fail('Pinned continuation proof changed.')
    return actual


def enqueue(paths, result, *, blocked=False, extended_chain=False):
    if extended_chain and not blocked:
        fail('Extended-chain recovery requires the explicit blocked-recovery command.')
    from .commands import configured_offline
    with configured_offline(paths, allow_apply_reconciliation=True) as (config, engine):
        ledger = Ledger(paths.state / 'automation.sqlite3', scope(config))
        try:
            from .clarification_authorization_history import require_no_pending as require_no_authorization
            require_no_authorization(ledger)
            requested_path = Path(result)
            if not requested_path.is_absolute():
                fail('An explicit absolute Result path is required.')
            requested = engine.core.result(requested_path)
            # source() proves the requested bytes also exist in the configured Exchange.
            requested = engine.exchange.source(requested)
            existing = validate_history(ledger)
            if existing:
                if (existing['version'] != (3 if extended_chain else 2 if blocked else 1)
                        or existing['artifacts']['result']['sha256'] != requested['sha256']):
                    fail('A different recovery is already pending.')
                verify(engine, ledger, existing)
                return reply(existing)
            row = ledger.current()
            receipt = evidence(engine, ledger, blocked=blocked)
            version = 3 if extended_chain else 2 if blocked else 1
            artifacts = proof_function({'version': version})(engine, row['source'], row['patch_sha'], requested)
            if version == 3 and (any(step['result']['run_id'] in ledger.known_runs() for step in artifacts['steps'])
                                 or any(step['patch']['sha256'] in ledger.published_hashes() for step in artifacts['steps'])):
                fail('A chain Result or package was already assigned to another job.')
            if version == 2 and (artifacts['checkpoint']['run_id'] in ledger.known_runs()
                            or any(artifacts[key]['sha256'] in ledger.published_hashes()
                                   for key in ('original', 'resumed'))):
                fail('Intermediate Result or manual package was already assigned to another job.')
            if requested['run_id'] in ledger.known_runs():
                fail('This Result was already claimed.')
            config_sha = sha256(read_private(paths.config)).hexdigest()
            doc = {'version': version, 'scope': scope(config), 'config_sha256': config_sha,
                   'history_sha256': history_hash(ledger), 'evidence': receipt, 'artifacts': artifacts}
            engine.codex.activity()  # Known active is permitted only for this intent, never adoption.
            verify(engine, ledger, doc)
            persist(ledger, doc)
            return reply(doc)
        finally:
            ledger.close()


def reply(doc):
    return {'queued': True, 'stage': 'apply_reconciliation_pending',
            'source_sha256': doc['artifacts']['source']['sha256'],
            'result_sha256': doc['artifacts']['result']['sha256'],
            'model_called': False, 'service_started': False, 'history_advanced': False}


def tick(engine, ledger, doc):
    engine.update(stage='apply_reconciliation_pending', error=None)
    if not engine.gate.allowed:
        return {'halted': False, 'again': False}
    if engine.codex.activity() == 'active':
        engine.update(stage='apply_reconciliation_waiting', thread_status='active')
        return {'halted': False, 'again': False, 'retry_after': 2}
    verify(engine, ledger, doc)
    if engine.codex.activity() == 'active':
        engine.update(stage='apply_reconciliation_waiting', thread_status='active')
        return {'halted': False, 'again': False, 'retry_after': 2}
    actual = verify(engine, ledger, doc)  # Bind inputs again after the final metadata observation.
    # Pause/stop can close the gate during inspection. No model call in this tick.
    advanced = engine.gate.enter(lambda: complete(ledger, doc, actual))
    engine.update(stage='ready' if advanced else 'apply_reconciliation_pending',
                  source_sha256=actual['result']['sha256'] if advanced else doc['artifacts']['source']['sha256'])
    return {'halted': False, 'again': advanced}


def verify_completed(engine, ledger):
    """No new work from a reconciled source whose archived evidence disappeared."""
    current = ledger.current()
    if current['stage'] != 'ready':
        return
    for row in records(ledger):
        doc = decode_object(row['proof'])
        chain = doc['artifacts']
        if row['state'] == 'completed' and chain['result']['sha256'] == current['sha']:
            retry = ledger.retry_info(chain['source']['sha256'])
            directory = attempt_directory(engine.paths, chain['source']['sha256'], retry['number'] if retry else 0)
            for name, expected in doc['evidence'].items():
                if sha256(read_private(directory / name)).hexdigest() != expected:
                    fail('Original completion changed after recovery.')
            original = chain['steps'][0]['patch'] if doc['version'] == 3 else chain['original']
            actual = proof_function(doc)(engine, chain['source'], original['sha256'], chain['result'], check_current=False)
            if stable(actual) != stable(chain):
                fail('Completed recovery evidence changed before new work.')


def public_status(paths):
    config = load(paths)
    if not config.enabled:
        return None
    ledger = Ledger(paths.state / 'automation.sqlite3', scope(config))
    try:
        doc = validate_history(ledger)
        return reply(doc) if doc else None
    finally:
        ledger.close()
