"""Explicit fresh runtime cycles; repository bytes are never reset or restored."""
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

from .config import load
from .correction_budget import bind
from .errors import ControlError
from .job_contract import fresh_contract, scope
from .ledger import Ledger
from .local import json_read, json_write, lock, read_private, write_private

REQUEST = 'start-current.json'
ACTIVE = 'current-cycle.json'


def _identity(value):
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def pending(paths):
    value = json_read(paths.state / REQUEST)
    if value is not None and (set(value) != {'version', 'id', 'scope'}
            or type(value['version']) is not int or value['version'] != 1
            or not _identity(value['id']) or type(value['scope']) is not str):
        raise ControlError('invalid_start_request', 'The explicit start request is invalid.')
    return value


def active_cycle(paths):
    value = json_read(paths.state / ACTIVE)
    if value is not None and (set(value) != {'version', 'id', 'ledger', 'source_sha256'}
            or type(value['version']) is not int or value['version'] != 1
            or not _identity(value['id']) or type(value['ledger']) is not str
            or not value['ledger'].endswith('.sqlite3')
            or not _identity(value['ledger'][:-8])
            or type(value['source_sha256']) is not str or len(value['source_sha256']) != 64
            or any(c not in '0123456789abcdef' for c in value['source_sha256'])):
        raise ControlError('invalid_current_cycle', 'The current runtime pointer is invalid.')
    return value


def enqueue(paths, config):
    """Caller holds operation.lock. Repeated pending requests are idempotent."""
    try:
        value = pending(paths)
    except ControlError as exc:
        if exc.code not in ('invalid_start_request', 'invalid_state'):
            raise
        value = None  # Explicit operator replacement, never an automatic repair.
    if value is None or value['scope'] != scope(config):
        value = {'version': 1, 'id': str(uuid4()), 'scope': scope(config)}
        json_write(paths.state / REQUEST, value)
    return value


def is_checkpoint(paths, source):
    cycle = active_cycle(paths)
    return cycle is not None and cycle['source_sha256'] == source['sha256']


def _finish(paths):
    # An explicit new cycle supersedes old deferred operator requests. This
    # runs only between worker jobs; no running handover or Dev turn is killed.
    from .handover_request import REQUEST as HANDOVER, STATUS as HANDOVER_STATUS
    request = pending(paths)
    if request is None:
        return
    archive = paths.state / 'start-requests' / request['id'] / 'superseded'
    for name in (HANDOVER, HANDOVER_STATUS, REQUEST):
        target = paths.state / name
        try:
            raw = read_private(target)
        except FileNotFoundError:
            continue
        saved = archive / name
        try:
            prior = read_private(saved)
        except FileNotFoundError:
            write_private(saved, raw, exclusive=True)
        else:
            if prior != raw:
                raise ControlError('start_archive_conflict', 'Superseded evidence changed; preserve both states.')
        target.unlink()


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


def public_status(paths):
    request = pending(paths)
    try:
        cycle = active_cycle(paths)
    except ControlError as exc:
        if request is None:
            raise
        return {'pending': True, 'request_id': request['id'], 'cycle_id': None,
                'source_sha256': None, 'previous_error': exc.code}
    return {'pending': request is not None, 'request_id': request['id'] if request else None,
            'cycle_id': cycle['id'] if cycle else None,
            'source_sha256': cycle['source_sha256'] if cycle else None}


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
    if request['scope'] != scope(engine.config) or load(paths, allow_deferred=True) != engine.config:
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
        name = str(uuid4()) + '.sqlite3'
        with closing(Ledger(paths.state / 'cycles' / name, scope(engine.config), initial=source)) as ledger:
            ledger.bind_contract(fresh_contract(source, allowed=engine.config.clarification_allowed))
            bind(ledger, source, engine.config.correction_limit)
        def publish():
            if pending(paths) != request or load(paths, allow_deferred=True) != engine.config:
                raise ControlError('start_configuration_changed', 'Start request changed before publication.')
            json_write(paths.state / ACTIVE, {'version': 1, 'id': request['id'],
                       'ledger': name, 'source_sha256': source['sha256']})
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
