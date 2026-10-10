"""Complete external files for the existing closed read-only Work adapter.

The original result schema and diagnostics are preserved. This explicit host
API never executes a handler, changes a checkpoint, registers a CLI command or
claims incremental result generation: its saved source outcome is in memory.
"""

from dataclasses import dataclass
from hashlib import sha256
import os
import secrets

from ..changes._publication_io import replace_bound_image
from ..changes._staging_files import _write_new
from ..cli.commands import builtin_registry
from ..model.canonical import canonical_json_bytes
from ._checkpoint_files import _directory
from ._result_projection import read_only_result_projection
from .checkpoints import CheckpointStore, CheckpointStorageError, _read_file, _verify_bindings
from .resume import (_checked_plan, _compatible_read, _require, _runtime_build,
                     _saved_outcome, WorkResumeError)


def _projection(store, held):
    registry, build = builtin_registry(), _runtime_build()
    initial, _, _, _ = _checked_plan(store._initial, registry, build)
    _require(initial.as_dict()['checkpoint_generation'] == 0
             and not initial.entries('completed'), 'initial_work_required')
    pointer = store._pointer(held)
    _require(pointer is not None, 'published_work_required')
    current = _compatible_read(store._read_chain, held, pointer[0])
    current, request, invocation, unit = _checked_plan(current, registry, build)
    value = current.as_dict()
    _require(value['state'] == 'completed', 'completed_work_required')
    outcome, exit_code = _saved_outcome(current, request, invocation, unit)
    _require(outcome['result'] is not None, 'complete_result_payload_required')
    raw = canonical_json_bytes(outcome['result'])
    schema = invocation.command.protocol.result_schema
    files, result = read_only_result_projection(
        held.path, value, raw, outcome, exit_code, schema)
    _ensure_work(store, held, pointer, current, build)
    return pointer, current, build, files, result


def _ensure_work(store, held, pointer, current, build):
    _require(_runtime_build() == build, 'runtime_build_changed')
    _require(store._pointer(held) == pointer, 'checkpoint_pointer_changed')
    _require(_compatible_read(store._read_chain, held, pointer[0]).raw == current.raw,
             'checkpoint_bytes_changed')
    _require(store._pointer(held) == pointer, 'checkpoint_pointer_changed')
    held.check()


def _verify_files(held, files, *, allow_missing=False):
    complete, bindings = True, {}
    for name, raw in files:
        try:
            actual = _read_file(held, 'results', name, expected_size=len(raw), bindings=bindings)
        except CheckpointStorageError as error:
            if not allow_missing or error.reason != 'checkpoint_bytes_missing':
                raise
            complete = False
        else:
            _require(actual == raw, 'result_file_bytes_changed')
    _verify_bindings(held, bindings)
    return complete


def _publish_file(held, name, raw, ensure_work):
    if _verify_files(held, ((name, raw),), allow_missing=True):
        return
    directory = _directory(held, 'results')
    temporary = '.result-' + secrets.token_hex(16) + '.tmp'
    identity = _write_new(directory, temporary, raw)

    def before_replace():
        ensure_work()
        try:
            os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise WorkResumeError('result_file_appeared')

    replace_bound_image(directory, temporary, directory, name,
        size=len(raw), digest=sha256(raw).hexdigest(), identity=identity,
        source_changed=lambda: WorkResumeError('result_temporary_changed'),
        before_replace=before_replace)
    _verify_files(held, ((name, raw),))
    ensure_work()


@dataclass(frozen=True, init=False)
class WorkResultDelivery:
    """Revalidated file references; no serialized execution or write capability."""

    _store: object
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use publish_read_only_result_files')

    def as_dict(self):
        with self._store._location.inspect_checkpoint() as held:
            pointer, current, build, files, result = _projection(self._store, held)
            _require(canonical_json_bytes(result) == self._raw, 'result_delivery_binding_changed')
            _verify_files(held, files)
            _ensure_work(self._store, held, pointer, current, build)
            return result

    def __bool__(self):
        raise TypeError('Inspect the freshly verified result delivery explicitly')


def publish_read_only_result_files(store):
    """Materialize a complete saved result, then its bound manifest, exactly once.

    Both files are private and atomically installed in the existing Work root.
    Existing matching files are reused without writes. Any error retains the
    checkpoint and actual output/temporary bytes; there is no automatic retry,
    cleanup or handler execution. A returned value rechecks all bytes on access.
    """
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    with store._location.inspect_checkpoint() as held:
        pointer, current, build, files, result = _projection(store, held)
        complete = _verify_files(held, files, allow_missing=True)
        _ensure_work(store, held, pointer, current, build)
        expected = canonical_json_bytes(result)
    if not complete:
        with store._location.for_checkpoint() as held:
            fresh_pointer, fresh, fresh_build, fresh_files, fresh_result = _projection(store, held)
            _require(fresh_pointer == pointer and fresh.raw == current.raw
                     and fresh_build == build and fresh_files == files
                     and canonical_json_bytes(fresh_result) == expected,
                     'result_delivery_binding_changed')
            # Verify every already present file before creating any missing file.
            _verify_files(held, files, allow_missing=True)
            ensure = lambda: _ensure_work(store, held, pointer, current, build)
            for name, raw in files:
                _publish_file(held, name, raw, ensure)
            _verify_files(held, files)
            ensure()
    delivery = object.__new__(WorkResultDelivery)
    object.__setattr__(delivery, '_store', store)
    object.__setattr__(delivery, '_raw', expected)
    delivery.as_dict()
    return delivery
