"""Explicit queueing and idle observation in the existing Control worker."""
from contextlib import closing
from hashlib import sha256
import os
import time
from uuid import uuid4

from .config import load
from .errors import ControlError
from .handover import (candidate_for, check_boundary, lifecycle_digest, metadata_cwd,
                       observe_thread, _handover_locked)
from .handover_evidence import canonical
from .handover_history import history_digest
from .handover_request import (REQUEST, STATUS, request_read, request_hash, state_read,
                               state_write, request_proof, finish_request, public_status)
from .job_contract import scope
from .ledger import Ledger
from .local import lock, read_private, write_private


def validate_request(paths, config, doc):
    candidate = candidate_for(config, paths, doc['thread_id'], doc['thread_cwd'])
    if (load(paths, allow_deferred=True) != config
            or sha256(read_private(paths.config)).hexdigest() != doc['old_config_sha256']
            or scope(config) != doc['old_scope'] or config.session_id != doc['old_thread_id']
            or scope(candidate) != doc['new_scope']):
        raise ControlError('handover_request_changed', 'Configuration differs from the deferred handover authority.')
    with closing(Ledger(paths.state/'automation.sqlite3', scope(config))) as history:
        row = check_boundary(history, paths)
        if (row['sha'] != doc['source_sha256'] or row['run_id'] != doc['current_run_id']
                or history_digest(history.db) != doc['history_sha256']):
            raise ControlError('handover_request_changed', 'Existing work changed after the deferred request.')
    return candidate


def startup(paths):
    doc = request_read(paths)
    config = load(paths, allow_deferred=doc is not None)
    if doc:
        state = state_read(paths, doc)
        if state['phase'] not in ('armed', 'waiting') or state['error'] is not None:
            raise ControlError('handover_deferred_blocked', 'A prior handover attempt needs explicit review; no automatic retry.')
        validate_request(paths, config, doc)
    return config, doc


def enqueue(paths, *, thread_id, thread_cwd, from_cwd=None, resume_after=False):
    from .commands import offline, ready
    with offline(paths):
        existing = request_read(paths)
        if existing is None and os.path.lexists(paths.state/STATUS):
            raise ControlError('handover_request_conflict', 'Unmatched handover state is preserved for review.')
        config = load(paths, allow_deferred=existing is not None)
        ready(config)
        new = candidate_for(config, paths, thread_id, thread_cwd)
        old_cwd = metadata_cwd(from_cwd) if from_cwd is not None else None
        if config.session_id == new.session_id:
            raise ControlError('handover_same_thread', 'Deferred handover requires a distinct existing thread.')
        if type(resume_after) is not bool:
            raise ControlError('invalid_handover_request', 'Resume authority must be explicit.')
        if existing:
            if any(existing[key] != value for key, value in {
                    'thread_id': thread_id, 'thread_cwd': str(new.thread_cwd),
                    'from_thread_cwd': str(old_cwd) if old_cwd else None, 'resume_after': resume_after}.items()):
                raise ControlError('handover_request_changed', 'A different handover is already queued.')
            startup(paths)
            return {'queued': True, 'already_queued': True, 'model_called': False, 'service_started': False}
        lifecycle_digest(paths)
        with closing(Ledger(paths.state/'automation.sqlite3', scope(config))) as history:
            row = check_boundary(history, paths)
            doc = {'version': 1, 'id': str(uuid4()), 'created_at': time.time(),
                'old_config_sha256': sha256(read_private(paths.config)).hexdigest(),
                'old_scope': scope(config), 'new_scope': scope(new),
                'old_thread_id': config.session_id, 'thread_id': new.session_id,
                'thread_cwd': str(new.thread_cwd), 'from_thread_cwd': str(old_cwd) if old_cwd else None,
                'resume_after': resume_after, 'source_sha256': row['sha'], 'current_run_id': row['run_id'],
                'history_sha256': history_digest(history.db)}
        # Active is permitted only while queuing/observing, never while committing.
        observe_thread(config, exact_cwd=old_cwd)
        observe_thread(new, exact_cwd=new.thread_cwd)
        from .core import Core
        from .exchange import Exchange
        Exchange(config, Core(config)).source(row['source'])
        validate_request(paths, config, doc)
        write_private(paths.state/REQUEST, canonical(doc), exclusive=True)
        state_write(paths, doc, 'armed')
        return {'queued': True, 'already_queued': False, 'resume_after': resume_after,
                'model_called': False, 'service_started': False}


class DeferredHandover:
    """One metadata observation per worker tick; never a model-based loop."""
    def __init__(self, config, paths, gate, doc):
        self.config, self.paths, self.gate, self.doc = config, paths, gate, doc
        self.request_id = doc['id']
        self.view = {'stage': 'handover_waiting', 'error': None, 'model_called': False}
        state_write(paths, doc, 'waiting')

    def summary(self):
        return dict(self.view)

    def close(self):
        pass

    def tick(self):
        try:
            if request_read(self.paths) != self.doc or state_read(self.paths, self.doc)['phase'] != 'waiting':
                raise ControlError('handover_request_changed', 'The active handover authority changed.')
            new = validate_request(self.paths, self.config, self.doc)
            old_status = observe_thread(self.config, exact_cwd=self.doc['from_thread_cwd'])
            new_status = observe_thread(new, exact_cwd=new.thread_cwd)
            self.view.update(old_thread_status=old_status, new_thread_status=new_status)
            if 'active' in (old_status, new_status):
                return {'halted': False, 'again': False, 'retry_after': 2.0}
            with lock(self.paths.state/'operation.lock'):
                if not self.gate.enter(lambda: state_write(self.paths, self.doc, 'applying')):
                    return {'halted': False, 'again': True}
                self.view['stage'] = 'handover_applying'
                validate_request(self.paths, self.config, self.doc)
                _handover_locked(self.paths, thread_id=self.doc['thread_id'], thread_cwd=self.doc['thread_cwd'],
                                 from_cwd=self.doc['from_thread_cwd'], request_sha=request_hash(self.doc))
                state_write(self.paths, self.doc, 'complete')
            self.view['stage'] = 'handover_complete'
            return {'halted': False, 'handover_complete': True, 'resume_after': self.doc['resume_after']}
        except Exception as exc:
            code = exc.code if isinstance(exc, ControlError) else 'handover_deferred_failed'
            self.view.update(stage='handover_blocked', error=code)
            try:
                # Never overwrite malformed or foreign evidence merely to log an error.
                if request_read(self.paths) == self.doc:
                    state_read(self.paths, self.doc)
                    state_write(self.paths, self.doc, 'blocked', code)
            except (ControlError, OSError, ValueError):
                pass
            raise ControlError(code, 'Deferred handover is blocked; no automatic replay or model start.') from None
