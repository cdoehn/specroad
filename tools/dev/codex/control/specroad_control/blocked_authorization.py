"""Explicit same-source grant after a proven terminal, patchless blocked answer."""
from hashlib import sha256
from pathlib import Path

from .blocked_authorization_history import (active, complete, decode, history_hash, persist,
                                            records, validate_history)
from .clarification_authorization import require_installed
from .config import digest, load
from .job_contract import new_contract, scope
from .ledger import Ledger
from .blocked_authorization_proof import PATH, CAPABILITY, fail, evidence, verify, guard_original
from .local import read_private


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
            from .current_acceptance_history import require_no_pending as no_current_acceptance
            require_release(paths)
            ledger = Ledger(paths.state / 'automation.sqlite3', scope(config))
            try:
                no_current_acceptance(ledger)
                requested = engine.exchange.source(engine.core.result(Path(result)))
                from .current_acceptance_history import active as accepted
                if accepted(ledger, requested['sha256']) is not None:
                    fail('This Result already received an explicit current-state acceptance.')
                if requested['sha256'] != source_sha256:
                    fail('This mode requires the exact same Result, not a successor.')
                for row in records(ledger):
                    if row['source_sha'] == source_sha256:
                        doc = decode(ledger, row)
                        from .clarification_authorization_history import stable
                        if doc['reason'] != reason.strip() or stable({'source': doc['source']}) != stable({'source': requested}):
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
                doc = {'version': 1, 'source': current['source'], 'scope': scope(config),
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
