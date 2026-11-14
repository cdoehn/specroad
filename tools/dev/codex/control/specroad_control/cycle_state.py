"""Private cycle pointers, restart requests and retained superseded evidence."""
from uuid import UUID, uuid4
from .errors import ControlError
from .job_contract import scope
from .local import json_read, json_write, read_private, write_private

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
