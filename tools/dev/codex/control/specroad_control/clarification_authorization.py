"""Explicit authority for one NEW successor; no replay or implicit budget reset."""
from hashlib import sha256
from pathlib import Path

from .clarification_authorization_proof import prove
from .config import digest, load
from .errors import ControlError
from .job_contract import scope, new_contract, contract
from .ledger import Ledger
from .local import read_private, decode_object


def fail(message):
    raise ControlError('clarification_authorization_rejected', message)


def require_installed(paths):
    from .releases import active_entrypoint
    from .local import json_read
    active_entrypoint(paths)  # Revalidates the entire pinned release and deployment state.
    receipt = json_read(paths.home / 'active-release.json')
    required = {'specroad_control/' + name for name in
                ('clarification_authorization.py', 'clarification_authorization_history.py',
                 'clarification_authorization_contract.py')}
    if receipt is None or not required <= set(receipt.get('files', {})):
        fail('Install the tested authorization-capable Control release before queuing a grant.')


def original(ledger):
    row, selected = ledger.current(), ledger.request_contract()
    unclassified = row['stage'] == 'waiting_result' and ledger.output_kind() == 'unknown'
    abandoned = (row['stage'] == 'uncertain' and row['error'] in ('dev_blocked', 'codex_turn_failed')
                 and row['patch_sha'] is None and ledger.output_kind() is None)
    if not (unclassified or abandoned):
        fail('Only an unresolved attempt or unclassified manual handoff can be superseded explicitly.')
    if (selected is None or selected['version'] not in (3, 4)
            or selected['clarifications_remaining'] <= 0 or selected.get('clarification_continuation', False)):
        fail('A positive recorded budget without an unfinished clarification is required.')
    return row, selected


def evidence(engine, ledger, source_sha, selected):
    retry = ledger.retry_info(source_sha)
    directory = ledger.attempt_directory(engine.paths, source_sha, retry['number'] if retry else 0)
    values = {}
    for name in ('attempt.json', 'dispatch.json', 'protocol-completion.json', 'completion.json'):
        try:
            raw = read_private(directory / name)
        except FileNotFoundError:
            values[name] = None
        else:
            values[name] = sha256(raw).hexdigest()
            if name == 'attempt.json':
                attempt = decode_object(raw)
                if (attempt.get('source_sha256') != source_sha
                        or attempt.get('thread_id') != engine.config.session_id
                        or contract(attempt.get('request_contract')) != selected):
                    fail('Original request does not match the recorded source, thread and authority.')
    return values


def verify(engine, ledger, doc):
    from .clarification_authorization_history import stable
    if (scope(engine.config) != doc['scope']
            or sha256(read_private(engine.paths.config)).hexdigest() != doc['config_sha256']
            or evidence(engine, ledger, doc['source_sha256'], doc['previous_contract']) != doc['evidence']):
        fail('Configuration or original attempt evidence changed after authorization.')
    actual = prove(engine, ledger, doc['artifacts']['source'], doc['artifacts']['result'])
    if (stable(actual) != stable(doc['artifacts'])
            or evidence(engine, ledger, doc['source_sha256'], doc['previous_contract']) != doc['evidence']
            or sha256(read_private(engine.paths.config)).hexdigest() != doc['config_sha256']):
        fail('Pinned native Apply evidence changed.')
    return actual


def enqueue(paths, result, *, source_sha256, reason):
    from .commands import configured_offline
    from .apply_reconcile_history import validate_history as reconciliation
    from .clarification_authorization_history import history_hash, records, persist, validate_history
    try:
        digest(source_sha256)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 512 or not reason.isprintable():
            fail('A short printable authorization reason is required.')
        requested_path = Path(result)
        if not requested_path.is_absolute():
            fail('An absolute successor Result path is required.')
        with configured_offline(paths, allow_apply_reconciliation=True) as (config, engine):
            require_installed(paths)
            ledger = Ledger(paths.state / 'automation.sqlite3', scope(config))
            try:
                from .current_acceptance_history import require_no_pending as no_current_acceptance
                no_current_acceptance(ledger)
                from .blocked_authorization_history import require_no_pending
                require_no_pending(ledger)
                if reconciliation(ledger) is not None:
                    fail('An Apply reconciliation is already pending.')
                requested = engine.exchange.source(engine.core.result(requested_path))
                pending = validate_history(ledger)
                existing = [row for row in records(ledger) if row['source_sha'] == source_sha256]
                if existing:
                    row = existing[0]; doc = decode_object(row['proof'])
                    if doc['target_sha256'] != requested['sha256'] or doc['reason'] != reason.strip():
                        fail('A different authorization already exists for this source.')
                    verify(engine, ledger, doc)
                    return reply(doc, completed=row['state'] == 'completed')
                if pending is not None:
                    fail('Another authorization is pending.')
                row, selected = original(ledger)
                if (row['sha'] != source_sha256 or requested['run_id'] in ledger.known_runs()
                        or ledger.db.execute('SELECT 1 FROM jobs WHERE sha=?', (requested['sha256'],)).fetchone()):
                    fail('The exact old source and a previously unclaimed successor are required.')
                artifacts = prove(engine, ledger, row['source'], requested)
                if row['patch_sha'] not in (None, artifacts['patch']['sha256']):
                    fail('The manual handoff differs from the pending bundle.')
                doc = {'version': 1, 'source_sha256': source_sha256, 'target_sha256': requested['sha256'],
                       'scope': scope(config), 'config_sha256': sha256(read_private(paths.config)).hexdigest(),
                       'history_sha256': history_hash(ledger), 'previous_contract': selected,
                       'selected_contract': new_contract(selected['clarifications_remaining'], version=4, limit=selected['clarification_limit']),
                       'reason': reason.strip(), 'original_job': {key: row[key] for key in ('stage', 'error', 'patch_sha', 'updated')},
                       'evidence': evidence(engine, ledger, source_sha256, selected),
                       'artifacts': artifacts}
                if row['stage'] == 'uncertain' and doc['evidence']['attempt.json'] is None:
                    fail('An unresolved attempt needs its original immutable request.')
                # Active is safe only for a pinned intent, never for adoption.
                engine.codex.activity()
                verify(engine, ledger, doc)
                persist(ledger, doc)
                return reply(doc)
            finally:
                ledger.close()
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        fail('Missing or invalid authorization inputs; no authority was granted.')


def reply(doc, *, completed=False):
    return {'queued': not completed, 'completed': completed,
            'stage': 'clarification_authorization_completed' if completed else 'clarification_authorization_pending',
            'source_sha256': doc['source_sha256'], 'result_sha256': doc['target_sha256'],
            'request_contract': doc['selected_contract'], 'model_called': False, 'service_started': False,
            'history_advanced': completed}


def tick(engine, ledger, doc):
    from .clarification_authorization_history import complete
    engine.update(stage='clarification_authorization_pending', error=None)
    if not engine.gate.allowed:
        return {'halted': False, 'again': False}
    if engine.codex.activity() == 'active':
        engine.update(stage='clarification_authorization_waiting', thread_status='active')
        return {'halted': False, 'again': False, 'retry_after': 2}
    verify(engine, ledger, doc)
    if engine.codex.activity() == 'active':
        return {'halted': False, 'again': False, 'retry_after': 2}
    actual = verify(engine, ledger, doc)
    advanced = engine.gate.enter(lambda: complete(ledger, doc, actual))
    engine.update(stage='ready' if advanced else 'clarification_authorization_pending',
                  source_sha256=doc['target_sha256'] if advanced else doc['source_sha256'])
    return {'halted': False, 'again': advanced}


def verify_completed(engine, ledger):
    from .clarification_authorization_history import records
    current = ledger.current()
    if current['stage'] != 'ready':
        return
    for row in records(ledger):
        if row['state'] == 'completed' and row['target_sha'] == current['sha']:
            verify(engine, ledger, decode_object(row['proof']))


def public_status(paths):
    from .clarification_authorization_history import validate_history
    config = load(paths)
    if not config.enabled:
        return None
    ledger = Ledger(paths.state / 'automation.sqlite3', scope(config))
    try:
        doc = validate_history(ledger)
        return reply(doc) if doc else None
    finally:
        ledger.close()
