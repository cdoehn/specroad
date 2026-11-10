"""Explicit offline transfer of future dispatches; never reset existing work."""
from contextlib import ExitStack, closing
from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import stat
import time
from specroad_control.toml_compat import tomllib
from uuid import uuid4

from .automation import Engine, Gate
from .codex_proxy import Proxy
from .commands import offline, ready
from .config import identity, load, parse, render
from .errors import ControlError
from .job_contract import scope
from .handover_evidence import canonical, receipt as validate_receipt, conflict as fail
from .handover_history import history_digest, last_receipt, open_history, commit_history, verify_commit
from .ledger import Ledger
from .local import json_read, lock, read_private, write_private
from .state import read_state


PENDING = 'thread-handover-pending.json'


def lifecycle_digest(paths, request_sha=None):
    if request_sha is not None:
        from .handover_queue import request_proof
        return request_proof(paths, request_sha)
    state = read_state(paths)
    if state is not None and (state['active_job'] or state['phase'] not in ('stopped', 'paused', 'idle')):
        raise ControlError('handover_worker_unproven', 'The worker must have finished its work before handover.')
    try:
        raw = b'present\0' + read_private(paths.state_file)
    except FileNotFoundError:
        raw = b'absent'
    return sha256(raw).hexdigest()


def candidate_for(old, paths, thread_id, thread_cwd):
    try:
        identity(thread_id)
        target = Path(thread_cwd)
        if not target.is_absolute() or target != target.resolve():
            raise ValueError
        for parent in (target, *target.parents):
            if not stat.S_ISDIR(parent.lstat().st_mode):
                raise ValueError
        if target not in (old.repository.resolve(), old.repository.resolve().parent):
            raise ValueError
        candidate = replace(old, session_id=thread_id, thread_cwd=target)
        return parse(tomllib.loads(render(candidate)), paths)
    except (OSError, ValueError, TypeError, KeyError):
        raise ControlError('invalid_handover_target', 'An explicit existing thread and exact Dev or parent cwd are required.') from None


def read_intent(paths, requested_id, requested_cwd, from_cwd=None, request_sha=None):
    intent = json_read(paths.state / PENDING)
    if intent is None:
        return None
    try:
        if set(intent) != {'version', 'old_config', 'new_config', 'receipt'} or type(intent['version']) is not int or intent['version'] != 1:
            raise ValueError
        old = parse(tomllib.loads(intent['old_config']), paths)
        new = parse(tomllib.loads(intent['new_config']), paths)
        expected = candidate_for(old, paths, requested_id, requested_cwd)
        receipt = validate_receipt(intent['receipt'])
        if new != expected or old.session_id == new.session_id:
            raise ValueError
        if (receipt['old_scope'] != scope(old) or receipt['new_scope'] != scope(new)
                or receipt['old_config_sha256'] != sha256(intent['old_config'].encode()).hexdigest()
                or receipt['new_config_sha256'] != sha256(intent['new_config'].encode()).hexdigest()
                or receipt['from_thread_id'] != old.session_id or receipt['to_thread_id'] != new.session_id
                or receipt['thread_cwd'] != str(new.thread_cwd)):
            raise ValueError
        identity(receipt['id'])
        if (receipt.get('from_thread_cwd') != (str(from_cwd) if from_cwd else None)
                or receipt.get('request_sha256') != request_sha):
            raise ValueError
        return intent, old, new
    except (ValueError, TypeError, KeyError, AttributeError, ControlError):
        raise ControlError('invalid_handover_intent', 'Pending handover or requested target differs; evidence is preserved.') from None


def check_boundary(history, paths):
    from .apply_reconcile_history import require_no_pending
    require_no_pending(history)
    row = history.current()
    if row['stage'] not in ('ready', 'waiting_result', 'no_work') or row['error'] is not None:
        raise ControlError('handover_job_unresolved', 'Existing work must reach a proven quiet boundary before handover.')
    if row['stage'] == 'ready' and os.path.lexists(paths.state / 'jobs' / row['sha']):
        raise ControlError('handover_attempt_present', 'A prepared attempt keeps its original thread binding.')
    return row


def check_target(config):
    with Proxy(config) as proxy:
        thread = proxy.thread()
        if thread['cwd'] != str(config.thread_cwd):
            raise ControlError('handover_cwd_mismatch', 'The target must report the exact explicitly confirmed cwd.')


def handover(paths, *, thread_id, thread_cwd, from_cwd=None):
    try:
        return perform_handover(paths, thread_id=thread_id, thread_cwd=thread_cwd, from_cwd=from_cwd)
    except (sqlite3.Error, ValueError, TypeError, UnicodeError):
        raise ControlError('invalid_handover_history', 'Unreadable handover data is preserved; no inferred completion.') from None


def perform_handover(paths, *, thread_id, thread_cwd, from_cwd=None):
    with offline(paths):
        return _handover_locked(paths, thread_id=thread_id, thread_cwd=thread_cwd, from_cwd=from_cwd)


def _handover_locked(paths, *, thread_id, thread_cwd, from_cwd=None, request_sha=None):
    """Caller holds operation and worker locks; deferred caller owns its lifecycle."""
    from_cwd = metadata_cwd(from_cwd) if from_cwd is not None else None
    pending = read_intent(paths, thread_id, thread_cwd, from_cwd, request_sha)
    if pending:
        intent, old, new = pending
    else:
        old = load(paths, allow_deferred=request_sha is not None)
        new = candidate_for(old, paths, thread_id, thread_cwd)
        intent = None
    ready(old)
    original = read_private(paths.config)
    try:
        actual = parse(tomllib.loads(original.decode()), paths)
    except (ValueError, TypeError, KeyError, UnicodeError):
        fail('Configuration changed before handover.')
    if not intent and actual != old:
        fail('Configuration changed before handover.')
    if intent and original not in (intent['old_config'].encode(), intent['new_config'].encode()):
        fail('Configuration changed while handover was pending.')
    if old.session_id == new.session_id:
        if old != new:
            fail('A changed cwd alone is not a different Dev thread.')
        with closing(Ledger(paths.state / 'automation.sqlite3', scope(old))) as history:
            check_boundary(history, paths)
        return {'handed_over': False, 'already_configured': True,
                'model_called': False, 'service_started': False}
    with Engine(old, paths, Gate()) as engine, ExitStack() as stack:
        target_key = sha256((str(new.codex_home.resolve()) + new.session_id).encode()).hexdigest()
        for root in paths.lock_roots:
            stack.enter_context(lock(root / ('thread-' + target_key + '.lock')))
        history = open_history(paths.state / 'automation.sqlite3', old, new, intent)
        stack.callback(history.close)
        row = check_boundary(history, paths)
        check_from(old, from_cwd)
        check_target(new)
        engine.exchange.source(row['source'])
        state_hash = lifecycle_digest(paths, request_sha)
        if intent is None:
            previous = last_receipt(history.db)
            receipt = {'id': str(uuid4()), 'created_at': time.time(), 'old_scope': scope(old),
                'new_scope': scope(new), 'from_thread_id': old.session_id, 'to_thread_id': new.session_id,
                'thread_cwd': str(new.thread_cwd), 'old_config_sha256': sha256(original).hexdigest(),
                'new_config_sha256': sha256(render(new).encode()).hexdigest(),
                'history_sha256': history_digest(history.db), 'lifecycle_sha256': state_hash,
                'current_run_id': row['run_id'], 'source_sha256': row['sha'],
                'previous_sha256': sha256(previous.encode()).hexdigest() if previous else None}
            if from_cwd is not None or request_sha is not None:
                receipt.update(version=2, from_thread_cwd=str(from_cwd) if from_cwd else None, request_sha256=request_sha)
            intent = {'version': 1, 'old_config': original.decode(), 'new_config': render(new), 'receipt': receipt}
            raw = canonical(intent)
            if len(raw) > 65536:
                raise ControlError('handover_intent_too_large', 'Pending handover exceeds the private-file budget.')
            write_private(paths.state / PENDING, raw, exclusive=True)
        receipt = intent['receipt']
        if (row['run_id'] != receipt['current_run_id'] or row['sha'] != receipt['source_sha256']
                or state_hash != receipt['lifecycle_sha256']):
            fail('Current work or lifecycle changed while handover was pending.')
        # Recheck both threads and source immediately before committing; the
        # operator must keep both threads idle for the entire command.
        check_from(old, from_cwd)
        check_target(new)
        engine.exchange.source(row['source'])
        if (read_private(paths.config) != original or lifecycle_digest(paths, request_sha) != state_hash
                or json_read(paths.state / PENDING) != intent):
            fail('Local handover evidence changed before publication.')
        commit_history(history, receipt)
        verify_commit(history, receipt)
        write_private(paths.config, intent['new_config'].encode())
        verify_commit(history, receipt)
        if (read_private(paths.config) != intent['new_config'].encode()
                or history_digest(history.db, exclude=receipt['id']) != receipt['history_sha256']
                or lifecycle_digest(paths, request_sha) != state_hash or json_read(paths.state / PENDING) != intent):
            fail('Handover verification failed; keep the journal for explicit completion.')
        (paths.state / PENDING).unlink()
        descriptor = os.open(paths.state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return {'handed_over': True, 'history_preserved': True, 'pause_preserved': True,
                'current_stage': row['stage'], 'thread_id': new.session_id,
                'thread_cwd': str(new.thread_cwd), 'execution_cwd': str(new.repository),
                'model_called': False, 'service_started': False, 'resumed_handover': pending is not None}


def metadata_cwd(value):
    try:
        path = Path(value)
        if (not path.is_absolute() or str(path) != str(value) or path != path.resolve()
                or any(p.is_symlink() or not p.is_dir() for p in (path, *path.parents))):
            raise ValueError
        return path
    except (OSError, ValueError, TypeError):
        raise ControlError('invalid_handover_from_cwd', 'An exact existing absolute old thread cwd is required.') from None


def observe_thread(config, *, exact_cwd=None):
    with Proxy(config) as proxy:
        if exact_cwd is None:
            thread = proxy.inspect_thread()
        else:
            thread = proxy.inspect_identity()
            if thread.get('cwd') != str(exact_cwd):
                raise ControlError('handover_cwd_mismatch', 'The observed thread cwd differs from the explicit handover binding.')
    status = thread.get('status')
    kind = status.get('type') if isinstance(status, dict) else None
    if kind not in ('idle', 'notLoaded', 'active'):
        raise ControlError('dev_thread_busy', 'Thread activity is unknown; preserve the handover request.')
    return kind


def check_from(config, from_cwd):
    if observe_thread(config, exact_cwd=from_cwd) == 'active':
        raise ControlError('dev_thread_busy', 'The original thread must be inactive before handover.')
