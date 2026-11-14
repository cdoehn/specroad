"""Explicit fresh runtime cycles; repository bytes are never reset or restored."""
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from .config import load
from .correction_budget import bind
from .errors import ControlError
from .job_contract import fresh_contract, scope
from .ledger import Ledger
from .local import json_read, json_write, lock

from .cycle_state import REQUEST, ACTIVE, pending, active_cycle, enqueue, _finish, public_status


def is_checkpoint(paths, source):
    cycle = active_cycle(paths)
    return cycle is not None and cycle['source_sha256'] == source['sha256']


def _checkpoint(engine, request):
    """Reuse a captured checkpoint after interruption; revalidate its live tree."""
    from .handoff_rebase import require_current
    target = engine.paths.state / 'start-requests' / request['id'] / 'checkpoint.json'
    saved = json_read(target)
    if saved is not None:
        try:
            source = engine.exchange.source(saved)
            require_current(engine, source, {source['run_id']})
            return source
        except ControlError as exc:
            if exc.code not in ('source_superseded', 'current_repository_mismatch'):
                raise
            # This is still the explicit operator request for the actual tree.
            # Keep the obsolete capture as evidence, not as dispatch authority.
            retained = target.parent / (saved['sha256'] + '.json')
            if json_read(retained) is None:
                json_write(retained, saved)
    source = engine.core.checkpoint()
    json_write(target, source)
    return source


def _pending_patch(engine, source):
    """A foreign unpublished result may still own this tree; never race Apply."""
    binding = source['binding']
    for package in engine.exchange.candidates('patch',
            lambda manifest: all(manifest.get(k) == v for k, v in binding.items())):
        engine.core.validate(Path(package['path']), source)
        completed = engine.exchange.following(source, package['sha256'])
        if not any(r.get('entrypoint_started') and not r.get('dry_run') for r in completed):
            return True
    return False


def _waiting(engine, reason):
    engine.update(stage='start_current_waiting', error=None, start_wait_reason=reason)
    return {'halted': False, 'again': False, 'retry_after': 2}


def advance(engine):
    """Before opening any old ledger, observe idle and capture the actual tree."""
    paths = engine.paths
    request = pending(paths)
    if request is None:
        return None
    if not engine.gate.allowed:
        return {'halted': False, 'again': False}
    from .budget_config import configured, values
    file_config = load(paths, allow_deferred=True)
    if request['scope'] != scope(engine.config) or replace(engine.config, **values(file_config)) != file_config:
        raise ControlError('start_configuration_changed', 'Start again for the current configuration.')
    activity = engine.codex.activity()
    if activity == 'active':
        return _waiting(engine, 'dev_turn_active')
    if activity not in ('idle', 'notLoaded'):
        raise ControlError('dev_activity_unknown', 'Dev activity cannot be established.')
    with lock(paths.state / 'operation.lock'):
        if pending(paths) != request:
            return {'halted': False, 'again': True}
        try:
            cycle = active_cycle(paths)
        except ControlError as exc:
            if exc.code not in ('invalid_current_cycle', 'invalid_state'):
                raise
            cycle = None  # The old runtime pointer is not restart authority.
        if cycle is not None and cycle['id'] == request['id']:
            # Publication completed before a worker interruption. Never refill twice.
            _finish(paths)
            return {'halted': False, 'again': True}
        try:
            source = _checkpoint(engine, request)
            if (source['binding']['repo_id'] != engine.config.repo_id
                    or Path(source['repository_path']).resolve() != engine.config.apply_directory.resolve()
                    or source['operation'] != 'bundle' or source['dry_run'] or not source['success']):
                raise ControlError('wrong_checkpoint', 'A current native Apply snapshot is required.')
            from .handoff_rebase import require_current
            require_current(engine, source, {source['run_id']})
            if _pending_patch(engine, source):
                return _waiting(engine, 'pending_patch')
        except ControlError as exc:
            if exc.code == 'repository_busy':
                return _waiting(engine, exc.code)
            raise
        # Each publication has its own database inode: concurrent readers retain
        # their snapshot and can never attach old SQLite sidecars to the new cycle.
        selected_config = configured(file_config, request.get('overrides', {}))
        name = str(uuid4()) + '.sqlite3'
        with closing(Ledger(paths.state / 'cycles' / name, scope(engine.config), initial=source)) as ledger:
            ledger.bind_contract(fresh_contract(source, allowed=selected_config.clarification_allowed, limit=selected_config.clarification_limit))
            bind(ledger, source, selected_config.correction_limit)
        def publish():
            if pending(paths) != request or load(paths, allow_deferred=True) != file_config:
                raise ControlError('start_configuration_changed', 'Start request changed before publication.')
            json_write(paths.state / ACTIVE, {'version': 1, 'id': request['id'],
                       'ledger': name, 'source_sha256': source['sha256'],
                       'overrides': request.get('overrides', {})})
            _finish(paths)
        try:
            require_current(engine, source, {source['run_id']})
            if _pending_patch(engine, source):
                return _waiting(engine, 'pending_patch')
            if engine.codex.activity() not in ('idle', 'notLoaded'):
                raise ControlError('dev_turn_active', 'Dev became active before publication.')
            # Slow native/SSH observations must not hold Gate's IPC mutex.
            activated = engine.gate.enter(publish)
        except ControlError as exc:
            if exc.code in ('repository_busy', 'dev_turn_active'):
                return _waiting(engine, exc.code)
            raise
        if not activated:
            return {'halted': False, 'again': False}
    engine.excluded.clear()
    engine.update(stage='ready', source_sha256=source['sha256'], error=None, start_wait_reason=None)
    return {'halted': False, 'again': True}
