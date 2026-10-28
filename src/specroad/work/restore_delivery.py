"""Complete native Restore output under the caller's retained Work lease.

Only the installed coordinator calls this after native execution/recovery. All
result bytes precede the delivery checkpoint and final completed generation.
A completed replay reads saved Work bytes, never executes a project operation.
"""
from hashlib import sha256
from dataclasses import dataclass
from functools import wraps

from ..model.canonical import canonical_json_bytes
from ..recovery.values import RestoreError, guarded, persisted_contract, require
from ..storage.json_syntax import parse_json_object
from ._completion import read_completion
from ._restore_completion import (transaction, outcome, projection, delivery_evidence,
                                  saved_delivery)
from .manifest import partition_work_manifest, complete_work_manifest
from .restore_execution import _bound, _build
from .result_files import _publish_file, _verify_files
from .resume import WorkResumeError


def _file_errors(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except WorkResumeError as error:
            raise RestoreError(error.reason, exit_code=error.exit_code) from error
    return call


def checked_progress(current, initial, registry, build):
    current, raw = _bound(current, registry, build)
    value = current.as_dict()
    done = current.entries('completed')
    terminal = value['state'] == 'completed'
    require((terminal and value['checkpoint_generation'] == 3 and len(done) == 2)
            or (value['state'] == 'running' and value['checkpoint_generation'] == len(done)
                and len(done) <= 2), 'restore_work_progress_conflict', exit_code=6)
    saved = None
    if done:
        saved = canonical_json_bytes(transaction(value, current.objects, initial=initial))
    if len(done) == 2:
        saved_delivery(value, current.objects)
    return current, raw, current.entries('tasks')[0]['unit_id'], saved


def _ensure(store, held, current, pointer, build, history):
    require(_build() == build and current.as_dict()['tool_build'] == build,
            'restore_work_build_changed', exit_code=6)
    require(store._pointer(held) == pointer, 'restore_work_pointer_changed', exit_code=6)
    require(store._read_chain(held, pointer[0]).raw == current.raw,
            'restore_work_bytes_changed', exit_code=6)
    require(store._pointer(held) == pointer, 'restore_work_pointer_changed', exit_code=6)
    history.check()
    held.check()


@_file_errors
def completed(store, held, current, pointer, build, history):
    value = current.as_dict()
    require(value['state'] == 'completed', 'restore_completed_work_required', exit_code=6)
    record = read_completion(value, current.objects, current._registry)
    document = record['outcome']
    files = projection(value, current.objects, document)
    _verify_files(held, files)
    _ensure(store, held, current, pointer, build, history)
    references = [{'path': str(held.path / 'results' / name), 'size': len(raw),
                   'sha256': sha256(raw).hexdigest()} for name, raw in files]
    return document, references


@_file_errors
def finish(store, held, current, pointer, native, build, history, progress):
    value = current.as_dict()
    require(native['result'] == 'restored' and native['recovery_required'] is False,
            'restore_work_native_completion_required', exit_code=6)
    # Validate the fresh native observation even when retaining an earlier
    # complete delivery. Current source/replay observations do not rewrite it.
    outcome(value, current.objects, native)
    document = (saved_delivery(value, current.objects)
                if len(current.entries('completed')) == 2 else native)
    files = projection(value, current.objects, document)
    _verify_files(held, files, allow_missing=True)
    ensure = lambda: _ensure(store, held, current, pointer, build, history)
    ensure()
    for name, raw in files:
        progress['writes'] = True
        _publish_file(held, name, raw, ensure)
    # Even recovered matching files must cross their durability boundary before
    # the unit is acknowledged (a previous process may have died during fsync).
    _verify_files(held, files, sync=True)
    ensure()
    if len(current.entries('completed')) == 1:
        unit = current.entries('tasks')[1]['unit_id']
        candidate = partition_work_manifest(current,
            {unit: delivery_evidence(value, current.objects, document)})
        _verify_files(held, files)
        ensure()
        current = store._publish_held(held, candidate, pointer)
        pointer = store._pointer(held)
    ensure()
    _verify_files(held, files)
    candidate = complete_work_manifest(current, document, exit_code=0)
    ensure()
    _verify_files(held, files)
    current = store._publish_held(held, candidate, pointer)
    pointer = store._pointer(held)
    document, references = completed(store, held, current, pointer, build, history)
    return current, document, references


@dataclass(frozen=True, init=False)
class RestoreWorkCompletion:
    manifest: object
    _store: object
    _registry: object
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resume_restore_work')

    @guarded
    @persisted_contract
    def as_dict(self):
        from .restore_owner import _held, _history
        from ._restore_owner_files import HandoffFiles
        with _held(self._store._location) as held:
            pointer = self._store._pointer(held)
            require(pointer is not None, 'restore_published_work_required', exit_code=5)
            current, _, _, _ = checked_progress(self._store._read_chain(held, pointer[0]),
                self._store._initial, self._registry, _build())
            require(current.raw == self.manifest.raw, 'restore_work_result_checkpoint_changed', exit_code=6)
            history = HandoffFiles(held)
            require(not _history(history, held, self._store, pointer), 'restore_work_handoff_unresolved')
            document, references = completed(self._store, held, current, pointer, _build(), history)
            value = parse_json_object(self._raw)
            require(value['restore'] == document and value['result_files'] == references,
                    'restore_work_delivery_binding_conflict', exit_code=6)
            return value

    def __bool__(self):
        raise TypeError('Inspect the checked complete Restore result explicitly')


def result(store, registry, current, document, references, *, finalized, handoff):
    value = current.as_dict()
    instance = object.__new__(RestoreWorkCompletion)
    object.__setattr__(instance, 'manifest', current)
    object.__setattr__(instance, '_store', store)
    object.__setattr__(instance, '_registry', registry)
    object.__setattr__(instance, '_raw', canonical_json_bytes({
        'format_version': 'restore-work-completion-v1', 'work_id': value['work_id'],
        'checkpoint_generation': value['checkpoint_generation'],
        'checkpoint_sha256': value['checkpoint_sha256'], 'work_state': value['state'],
        'progress': value['progress'], 'next_action': value['next_action'],
        'command_exit_code': 0, 'work_completion_recorded': True,
        'checkpoint_changed': finalized, 'native_execution_checked': finalized,
        'result_files': references, 'restore': document,
        'owner_handoff': None if handoff is None else handoff.as_dict()}))
    return instance
