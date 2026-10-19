"""Full document data files through the existing atomic Work file publisher."""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes
from ..work._result_projection import read_only_result_projection
from ..work.checkpoints import CheckpointStore
from ..work.result_files import _ensure_work, _verify_files, _publish_file
from ..work.resume import _compatible_read, _require, _runtime_build
from .work import _checked_plan, _checked_final, _outcome, _SCHEMA


def _projection(store, held, registry):
    build = _runtime_build()
    initial = _compatible_read(_checked_plan, store._initial, registry, build)
    _require(initial.as_dict()['checkpoint_generation'] == 0
             and not initial.entries('completed'), 'initial_work_required')
    pointer = store._pointer(held)
    _require(pointer is not None, 'published_work_required')
    current = _compatible_read(store._read_chain, held, pointer[0])
    current = _compatible_read(_checked_plan, current, registry, build)
    value = current.as_dict()
    _require(value['state'] == 'completed', 'completed_work_required')
    _compatible_read(_checked_final, current, registry)
    outcome = _compatible_read(_outcome, current).as_dict()
    files, result = read_only_result_projection(held.path, value,
        canonical_json_bytes(outcome['result']), outcome, 0, _SCHEMA)
    _ensure_work(store, held, pointer, current, build)
    return pointer, current, build, files, result


@dataclass(frozen=True, init=False)
class DocumentResultDelivery:
    """Recheck the checkpoint and all output bytes on every reference access."""
    _store: object
    _registry: object
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use publish_document_result_files')

    def as_dict(self):
        with self._store._location.inspect_checkpoint() as held:
            pointer, current, build, files, result = _projection(self._store, held, self._registry)
            _require(canonical_json_bytes(result) == self._raw, 'result_delivery_binding_changed')
            _verify_files(held, files)
            _ensure_work(self._store, held, pointer, current, build)
            return result

    def __bool__(self):
        raise TypeError('Inspect freshly verified document delivery explicitly')


def publish_document_result_files(store, *, registry):
    """Publish complete result bytes and their manifest outside the project.

    Existing matching files are reused. Errors retain the actual Work and file
    state. No checkpoint, source project or normative request is changed here.
    """
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    with store._location.inspect_checkpoint() as held:
        pointer, current, build, files, result = _projection(store, held, registry)
        complete = _verify_files(held, files, allow_missing=True)
        _ensure_work(store, held, pointer, current, build)
        expected = canonical_json_bytes(result)
    if not complete:
        with store._location.for_checkpoint() as held:
            fresh_pointer, fresh, fresh_build, fresh_files, fresh_result = _projection(store, held, registry)
            _require(fresh_pointer == pointer and fresh.raw == current.raw and fresh_build == build
                and fresh_files == files and canonical_json_bytes(fresh_result) == expected,
                'result_delivery_binding_changed')
            _verify_files(held, files, allow_missing=True)
            ensure = lambda: _ensure_work(store, held, pointer, current, build)
            for name, raw in files:
                _publish_file(held, name, raw, ensure)
            _verify_files(held, files); ensure()
    delivery = object.__new__(DocumentResultDelivery)
    object.__setattr__(delivery, '_store', store)
    object.__setattr__(delivery, '_registry', registry)
    object.__setattr__(delivery, '_raw', expected)
    delivery.as_dict()
    return delivery
