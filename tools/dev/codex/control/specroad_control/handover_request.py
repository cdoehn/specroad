"""Closed deferred-request evidence, lifecycle proof and guarded completion."""
from contextlib import closing
from hashlib import sha256
import math
import os

from .config import digest, identity, load
from .errors import ControlError
from .handover import metadata_cwd
from .handover_evidence import canonical, receipt
from .handover_history import history_digest, last_receipt, verify_commit
from .job_contract import scope
from .ledger import Ledger
from .local import decode_object, json_read, read_private, write_private
from .state import read_state

REQUEST = 'thread-handover-request.json'
STATUS = 'thread-handover-state.json'
FIELDS = {'version', 'id', 'created_at', 'old_config_sha256', 'old_scope', 'new_scope',
          'old_thread_id', 'thread_id', 'thread_cwd', 'from_thread_cwd', 'resume_after',
          'source_sha256', 'current_run_id', 'history_sha256'}


def request_read(paths):
    doc = json_read(paths.state/REQUEST)
    if doc is None:
        return None
    try:
        if set(doc) != FIELDS or type(doc['version']) is not int or doc['version'] != 1:
            raise ValueError
        for field in ('id', 'old_thread_id', 'thread_id', 'current_run_id'):
            identity(doc[field])
        for field in ('old_config_sha256', 'old_scope', 'new_scope', 'source_sha256', 'history_sha256'):
            digest(doc[field])
        if (doc['old_thread_id'] == doc['thread_id'] or doc['old_scope'] == doc['new_scope']
                or type(doc['resume_after']) is not bool or type(doc['created_at']) not in (int, float)
                or not math.isfinite(doc['created_at']) or doc['created_at'] < 0):
            raise ValueError
        metadata_cwd(doc['thread_cwd'])
        if doc['from_thread_cwd'] is not None:
            metadata_cwd(doc['from_thread_cwd'])
        if read_private(paths.state/REQUEST) != canonical(doc):
            raise ValueError
        return doc
    except (ValueError, TypeError, KeyError, ControlError):
        raise ControlError('invalid_handover_request', 'Deferred handover evidence is invalid; preserve it.') from None


def request_hash(doc):
    return sha256(canonical(doc)).hexdigest()


def state_read(paths, doc):
    state = json_read(paths.state/STATUS)
    if (not state or set(state) != {'version', 'request_sha256', 'phase', 'error'}
            or type(state['version']) is not int or state['version'] != 1
            or state['request_sha256'] != request_hash(doc)
            or state['phase'] not in ('armed', 'waiting', 'applying', 'blocked', 'complete')
            or (state['error'] is not None and not isinstance(state['error'], str))):
        raise ControlError('invalid_handover_request_state', 'Deferred handover state is missing or damaged.')
    return state


def state_write(paths, doc, phase, error=None):
    write_private(paths.state/STATUS, canonical({'version': 1, 'request_sha256': request_hash(doc),
                                               'phase': phase, 'error': error}))


def request_proof(paths, expected_sha):
    doc = request_read(paths)
    state = read_state(paths)
    if (doc is None or request_hash(doc) != expected_sha or state is None
            or state.get('handover_request_id') != doc['id'] or not state['active_job']
            or state_read(paths, doc)['phase'] != 'applying'):
        raise ControlError('handover_request_changed', 'The worker no longer owns this exact handover authority.')
    return expected_sha


def finish_request(paths, doc):
    if request_read(paths) != doc or state_read(paths, doc)['phase'] != 'complete':
        raise ControlError('handover_request_changed', 'The deferred request changed during handover.')
    config = load(paths, allow_deferred=True)
    if scope(config) != doc['new_scope']:
        raise ControlError('handover_request_changed', 'The completed request does not match the live configuration.')
    with closing(Ledger(paths.state/'automation.sqlite3', scope(config))) as history:
        raw = last_receipt(history.db)
        proof = receipt(decode_object(raw)) if raw else None
        if (proof is None or proof.get('request_sha256') != request_hash(doc)
                or proof['history_sha256'] != doc['history_sha256']
                or proof['new_config_sha256'] != sha256(read_private(paths.config)).hexdigest()
                or history_digest(history.db, exclude=proof['id']) != doc['history_sha256']):
            raise ControlError('handover_request_changed', 'Completed handover evidence changed before dispatch.')
        verify_commit(history, proof)
    # The dispatcher has durably honored pause/stop/resume authority before
    # removing the barrier which blocks ordinary startup.
    state = read_state(paths)
    if (state is None or state.get('handover_request_id') != doc['id']
            or (not doc['resume_after'] and state['desired'] != 'paused')):
        raise ControlError('handover_request_changed', 'Post-handover lifecycle authority has not been persisted.')
    archive = paths.state/'handovers'/(doc['id']+'.json')
    write_private(archive, canonical(doc), exclusive=True)
    (paths.state/STATUS).unlink()
    (paths.state/REQUEST).unlink()  # Remove the ordinary-start barrier last.
    fd = os.open(paths.state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def public_status(paths):
    try:
        doc = request_read(paths)
        if doc is None:
            if os.path.lexists(paths.state/STATUS):
                return {'phase': 'blocked', 'error': 'handover_request_conflict'}
            return None
        state = state_read(paths, doc)
        return {'phase': state['phase'], 'resume_after': doc['resume_after'], 'error': state['error']}
    except (ControlError, OSError) as exc:
        return {'phase': 'blocked', 'error': exc.code if isinstance(exc, ControlError) else 'local_io_error'}
