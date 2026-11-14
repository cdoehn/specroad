"""Explicit fresh runtime cycles; repository bytes are never reset or restored."""
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

from .config import load
from .correction_budget import bind
from .errors import ControlError
from .job_contract import fresh_contract, scope
from .ledger import Ledger
from .local import json_read, json_write, lock, read_private

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
    for name in (HANDOVER, HANDOVER_STATUS, REQUEST):
        target = paths.state / name
        try:
            read_private(target)
        except FileNotFoundError:
            continue
        target.unlink()


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
    if request['scope'] != scope(engine.config) or load(paths) != engine.config:
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
            source = engine.core.checkpoint()
            if (source['binding']['repo_id'] != engine.config.repo_id
                    or Path(source['repository_path']).resolve() != engine.config.apply_directory.resolve()
                    or source['operation'] != 'bundle' or source['dry_run'] or not source['success']):
                raise ControlError('wrong_checkpoint', 'A current native Apply snapshot is required.')
            from .handoff_rebase import require_current
            require_current(engine, source, {source['run_id']})
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
            if pending(paths) != request or load(paths) != engine.config:
                raise ControlError('start_configuration_changed', 'Start request changed before publication.')
            json_write(paths.state / ACTIVE, {'version': 1, 'id': request['id'],
                       'ledger': name, 'source_sha256': source['sha256']})
            _finish(paths)
        try:
            require_current(engine, source, {source['run_id']})
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
