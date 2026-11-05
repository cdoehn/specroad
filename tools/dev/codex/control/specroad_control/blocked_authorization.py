"""Explicit same-source grant after a proven terminal, patchless blocked answer."""
from hashlib import sha256
from pathlib import Path

from .apply_reconcile_proof import member
from .blocked_authorization_history import (active, complete, decode, history_hash, persist,
                                            records, validate_history)
from .clarification_authorization import require_installed
from .config import digest, load
from .errors import ControlError
from .job_contract import contract, new_contract, scope
from .ledger import Ledger
from .local import decode_object, read_private
from .mixed_contract import supports_v4
from .retry_ledger import attempt_directory

PATH = 'verification/blocked_clarification_authorization.json'
CAPABILITY = {'format_version': 1, 'decision_rule': 'SPECROAD-DECISION-1',
              'decision_contract_version': 4, 'authorization_mode': 'explicit_blocked_attempt',
              'budget_policy': 'preserve', 'maximum_grants_per_source': 1}


def fail(message):
    raise ControlError('blocked_clarification_rejected', message)


def evidence(engine, doc):
    source = doc['source']
    directory = attempt_directory(engine.paths, source['sha256'], doc['attempt_number'])
    files = {}
    values = {}
    for name in ('attempt.json', 'dispatch.json', 'protocol-completion.json', 'completion.json'):
        try:
            raw = read_private(directory / name)
        except FileNotFoundError:
            if name != 'dispatch.json':
                fail('The original blocked attempt and both completion records are required.')
            values[name] = None
            continue
        values[name], files[name] = sha256(raw).hexdigest(), decode_object(raw)
    attempt, terminal, answer = files['attempt.json'], files['protocol-completion.json'], files['completion.json']
    if (attempt.get('source_sha256') != source['sha256']
            or attempt.get('thread_id') != engine.config.session_id
            or attempt.get('number') != doc['attempt_number']
            or contract(attempt.get('request_contract')) != doc['previous_contract']
            or attempt.get('request_source') != {k: source[k] for k in ('path', 'sha256', 'binding', 'run_id')}
            or terminal.get('completed') is not True or terminal.get('thread_id') != engine.config.session_id
            or terminal.get('transport') != engine.config.transport or terminal.get('answer') != answer
            or set(answer) != {'source_result_sha256', 'status', 'patch_sha256', 'message'}
            or not all(isinstance(v, str) for v in answer.values())
            or answer['source_result_sha256'] != source['sha256']
            or answer['status'] != 'blocked' or answer['patch_sha256'] != ''):
        fail('No exact terminal patchless blocked answer with its original authority.')
    if engine.config.transport == 'app-server-proxy':
        dispatch = files.get('dispatch.json', {})
        if (not isinstance(terminal.get('turn_id'), str) or not terminal['turn_id']
                or dispatch.get('turn_id') != terminal['turn_id']
                or dispatch.get('thread_id') != engine.config.session_id):
            fail('The exact proxy turn dispatch and completion are required.')
    return values


def verify(engine, ledger, doc, *, require_unused=True):
    if (scope(engine.config) != doc['scope']
            or sha256(read_private(engine.paths.config)).hexdigest() != doc['config_sha256']
            or evidence(engine, doc) != doc['evidence']):
        fail('Configuration or original completion evidence changed.')
    source = engine.exchange.source(doc['source'])
    raw = member(source, 'base/' + PATH)
    capability = decode_object(raw)
    if (len(raw) > 4096 or set(capability) != set(CAPABILITY)
            or any(type(capability[k]) is not type(v) or capability[k] != v for k, v in CAPABILITY.items())
            or not supports_v4(source) or not source['success'] or source['dirty'] or source['dry_run']):
        fail('The clean native Result must explicitly support blocked-attempt authorization.')
    if require_unused:
        engine.exchange.assert_current(source, ledger.known_runs())
        # Check all native-bound outputs, not only the engine's filtered list.
        if engine.exchange.patches(source):
            fail('A bound patch already exists; adoption takes priority over a new attempt.')
    if evidence(engine, doc) != doc['evidence'] or sha256(read_private(engine.paths.config)).hexdigest() != doc['config_sha256']:
        fail('Evidence changed during native validation.')


def require_release(paths):
    from .local import json_read
    require_installed(paths)
    receipt = json_read(paths.home / 'active-release.json')
    if not {'specroad_control/blocked_authorization.py', 'specroad_control/blocked_authorization_history.py'} <= set(receipt['files']):
        fail('Install the tested blocked-authorization release first.')


def enqueue(paths, result, *, source_sha256, reason):
    from .commands import configured_offline
    from .apply_reconcile_history import validate_history as reconciliation
    from .clarification_authorization_history import validate_history as successor
    try:
        digest(source_sha256)
        if not Path(result).is_absolute() or not isinstance(reason, str) or not reason.strip() or len(reason) > 512 or not reason.isprintable():
            fail('An absolute Result and short explicit authorization reason are required.')
        with configured_offline(paths, allow_apply_reconciliation=True) as (config, engine):
            require_release(paths)
            ledger = Ledger(paths.state / 'automation.sqlite3', scope(config))
            try:
                requested = engine.exchange.source(engine.core.result(Path(result)))
                if requested['sha256'] != source_sha256:
                    fail('This mode requires the exact same Result, not a successor.')
                for row in records(ledger):
                    if row['source_sha'] == source_sha256:
                        doc = decode(ledger, row)
                        if doc['reason'] != reason.strip() or doc['source'] != requested:
                            fail('A different authorization already exists for this source.')
                        verify(engine, ledger, doc, require_unused=row['state'] == 'pending')
                        return reply(doc, completed=row['state'] == 'completed')
                if any((validate_history(ledger), reconciliation(ledger), successor(ledger))):
                    fail('Another offline transition is pending.')
                current, previous = ledger.current(), ledger.request_contract()
                if (current['sha'] != source_sha256 or current['stage'] != 'uncertain'
                        or current['error'] != 'dev_blocked' or current['patch_sha'] is not None
                        or ledger.output_kind() is not None or previous is None or previous['version'] != 4
                        or previous['clarification_allowed'] or previous['clarification_continuation']
                        or previous['clarifications_remaining'] <= 0):
                    fail('Only an ungranted V4 blocked attempt with no handoff and a positive recorded budget is eligible.')
                retry = ledger.retry_info(source_sha256)
                doc = {'version': 1, 'source': requested, 'scope': scope(config),
                       'config_sha256': sha256(read_private(paths.config)).hexdigest(),
                       'history_sha256': history_hash(ledger), 'previous_contract': previous,
                       'selected_contract': new_contract(previous['clarifications_remaining'], version=4),
                       'original_job': {k: current[k] for k in ('stage', 'error', 'patch_sha', 'updated')},
                       'attempt_number': retry['number'] if retry else 0, 'reason': reason.strip()}
                doc['evidence'] = evidence(engine, doc)
                engine.codex.activity()  # Known active is allowed only for queuing.
                verify(engine, ledger, doc)
                persist(ledger, doc)
                return reply(doc)
            finally:
                ledger.close()
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        fail('Invalid or unavailable authorization evidence; nothing was granted.')


def reply(doc, *, completed=False):
    return {'queued': not completed, 'completed': completed, 'mode': 'explicit_blocked_attempt',
            'source_sha256': doc['source']['sha256'], 'request_contract': doc['selected_contract'],
            'model_called': False, 'service_started': False}


def tick(engine, ledger, doc):
    engine.update(stage='blocked_clarification_pending', error=None)
    if not engine.gate.allowed:
        return {'halted': False, 'again': False}
    if engine.codex.activity() == 'active':
        engine.update(thread_status='active')
        return {'halted': False, 'again': False, 'retry_after': 2}
    verify(engine, ledger, doc)
    if engine.codex.activity() == 'active':
        return {'halted': False, 'again': False, 'retry_after': 2}
    verify(engine, ledger, doc)
    adopted = engine.gate.enter(lambda: complete(ledger, doc))
    engine.update(stage='ready' if adopted else 'blocked_clarification_pending',
                  source_sha256=doc['source']['sha256'])
    return {'halted': False, 'again': adopted}


def guard_dispatch(engine, ledger, source):
    doc = active(ledger, source['sha256'])
    if doc is not None:
        verify(engine, ledger, doc)


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
