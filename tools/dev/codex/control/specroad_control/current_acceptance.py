"""Explicit accept-current intent; only an idle, enabled worker may adopt it."""
from hashlib import sha256
from pathlib import Path

from .current_acceptance_history import (complete, document, history_hash,
    persist, records, selection, validate_history)
from .current_acceptance_proof import checked, fail
from .current_acceptance_guard import (blocked_evidence, guard_inputs, verify,
    guard_dispatch, guard_original)
from .job_contract import scope
from .ledger import Ledger
from .local import json_read, read_private
from .config import load


def require_release(paths):
    from .clarification_authorization import require_installed
    require_installed(paths)
    receipt = json_read(paths.home / 'active-release.json')
    required = {'specroad_control/' + name for name in
        ('current_acceptance.py', 'current_acceptance_history.py', 'current_acceptance_proof.py', 'current_acceptance_guard.py')}
    if not receipt or not required <= set(receipt.get('files', {})):
        fail('Install the tested accept-current release before queuing this action.')


def enqueue(paths, result, *, clarification=None, reason, reset_budget=False):
    from .commands import configured_offline
    from .apply_reconcile_history import validate_history as recoveries
    from .clarification_authorization_history import validate_history as successors
    from .blocked_authorization_history import validate_history as blocked, active as old_grant
    from .handover_queue import public_status as handover
    try:
        if (not Path(result).is_absolute() or clarification is not None and type(clarification) is not bool
                or type(reset_budget) is not bool or reset_budget and clarification is False
                or not isinstance(reason, str) or not reason.strip() or len(reason) > 512
                or not reason.isprintable()):
            fail('An absolute Result and short explicit reason are required.')
        with configured_offline(paths, allow_apply_reconciliation=True) as (config, engine):
            require_release(paths)
            clarification = config.clarification_allowed if clarification is None else clarification
            if reset_budget and not clarification:
                fail('An explicit budget reset requires clarification authority.')
            ledger = Ledger(paths.state / 'automation.sqlite3', scope(config))
            try:
                requested = engine.exchange.source(engine.core.result(Path(result)))
                for row in records(ledger):
                    if row['target_sha'] == requested['sha256']:
                        doc = document(row)
                        if (doc['reason'] != reason.strip() or doc['clarification'] != clarification
                                or doc.get('reset_budget', False) != reset_budget):
                            fail('A different acceptance already exists for this Result.')
                        verify(engine, ledger, doc, unused=row['state'] == 'pending')
                        return reply(doc, completed=row['state'] == 'completed')
                if any((validate_history(ledger), recoveries(ledger), successors(ledger), blocked(ledger), handover(paths))):
                    fail('Another offline transition is pending.')
                old, previous = ledger.current(), ledger.request_contract()
                if (old['stage'] not in ('ready', 'uncertain', 'waiting_result', 'no_work')
                        or previous is None or previous['version'] not in (3, 4)
                        or previous.get('clarification_continuation')
                        or clarification and previous['clarifications_remaining'] == 0 and not reset_budget
                        or reset_budget and previous['version'] != 4):
                    fail('No active/retrying work, unknown budget or unfinished clarification may be bypassed.')
                mode, number = 'successor', 0
                if requested['sha256'] == old['sha']:
                    if old_grant(ledger, old['sha']) is not None:
                        fail('This Result already received an explicit retry grant.')
                    retry = ledger.retry_info(old['sha'])
                    number = retry['number'] if retry else 0
                    if old['stage'] == 'ready' and old['patch_sha'] is None and not retry:
                        mode = 'same_ready'
                        directory = paths.state / 'jobs' / old['sha']
                        if directory.exists() and any(p.is_file() for p in directory.rglob('*')):
                            fail('The ready Result already has attempt files.')
                    elif (old['stage'] == 'uncertain' and old['error'] == 'dev_blocked'
                            and old['patch_sha'] is None and ledger.output_kind() is None
                            and previous['version'] == 4 and not previous['clarification_allowed'] and clarification):
                        mode = 'same_blocked'
                    else:
                        fail('Same-source acceptance requires an unissued ready job or a terminal patchless ungranted blocker.')
                elif (requested['run_id'] in ledger.known_runs()
                        or ledger.db.execute('SELECT 1 FROM jobs WHERE sha=?', (requested['sha256'],)).fetchone()):
                    fail('The selected successor was already claimed.')
                strict_choice = mode == 'same_ready' and previous['clarification_allowed'] and not clarification
                doc = {'version': 3 if strict_choice else 2 if reset_budget else 1, 'source': old['source'], 'target': requested,
                    'scope': scope(config), 'config_sha256': sha256(read_private(paths.config)).hexdigest(),
                    'history_sha256': history_hash(ledger), 'previous_contract': previous,
                    'previous_output_kind': ledger.output_kind(),
                    'selected_contract': selection(previous, ledger.output_kind(), clarification, mode, reset_budget=reset_budget,
                        reset_limit=requested['development_contract']['clarification_limit'], strict_choice=strict_choice),
                    'original_job': {k: old[k] for k in ('stage', 'error', 'patch_sha', 'updated')},
                    'mode': mode, 'attempt_number': number, 'evidence': None,
                    'reason': reason.strip(), 'clarification': clarification,
                    'artifacts': checked(engine, requested, reset_budget=reset_budget)}
                if strict_choice or reset_budget:
                    doc['reset_budget'] = reset_budget
                if mode == 'same_blocked':
                    doc['evidence'] = blocked_evidence(engine, doc)
                # A known active user turn permits queuing, never adoption.
                engine.codex.activity()
                verify(engine, ledger, doc)
                persist(ledger, doc)
                return reply(doc)
            finally:
                ledger.close()
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        fail('Invalid or unavailable acceptance evidence; no state was accepted.')


def reply(doc, *, completed=False):
    return {'queued': not completed, 'completed': completed,
        'stage': 'current_acceptance_completed' if completed else 'current_acceptance_pending',
        'source_sha256': doc['source']['sha256'], 'result_sha256': doc['target']['sha256'],
        'request_contract': doc['selected_contract'], 'model_called': False,
        'service_started': False, 'history_advanced': completed,
        **({'budget_reset': True} if doc.get('reset_budget') is True else {})}


def tick(engine, ledger, doc):
    engine.update(stage='current_acceptance_pending', error=None)
    if not engine.gate.allowed:
        return {'halted': False, 'again': False}
    if engine.codex.activity() == 'active':
        engine.update(stage='current_acceptance_waiting', thread_status='active')
        return {'halted': False, 'again': False, 'retry_after': 2}
    verify(engine, ledger, doc)
    if engine.codex.activity() == 'active':
        return {'halted': False, 'again': False, 'retry_after': 2}
    verify(engine, ledger, doc)
    def adopt():
        guard_inputs(engine, ledger, doc)
        complete(ledger, doc)
    advanced = engine.gate.enter(adopt)
    engine.update(stage='ready' if advanced else 'current_acceptance_pending',
        source_sha256=doc['target']['sha256'] if advanced else doc['source']['sha256'])
    return {'halted': False, 'again': advanced}


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
