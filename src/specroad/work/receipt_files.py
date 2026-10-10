"""External delivery of a complete, already committed native request receipt.

This adapter only reads native transaction proof. It cannot apply a plan, take a
project writer lock, recover a transaction or mark normative Work completed.
"""

from dataclasses import dataclass

from ..changes.authoring import bind_plan_authoring
from ..changes.idempotency import resolve_normative_request
from ..changes.receipt_read import read_transaction_completion
from ..model.canonical import canonical_json_bytes
from ._publication_outcome import _publication_result
from ._resume_restore import restore_normative_checkpoint
from .publication import _arguments, _checked_work, _source
from .result_files import _ensure_work, _verify_files, _publish_file
from ._result_projection import native_result_projection
from .resume import _require


def _receipt(current, model, plan):
    source = _source(model)
    resolution = resolve_normative_request(source, bind_plan_authoring(plan))
    value = resolution.data
    _require(value['action'] == 'replay' and value['receipt_verified'],
             'normative_receipt_required')
    completion = read_transaction_completion(source, value['result_object']['transaction_id'])
    _publication_result(current, resolution, completion, published=False)
    # Keep the complete original request resolution. Cleanup observations from
    # TransactionCompletion are deliberately not part of this historical result.
    return canonical_json_bytes(value)


def _ensure_source(store, held, pointer, current, build, model, plan, raw):
    _ensure_work(store, held, pointer, current, build)
    _require(_receipt(current, model, plan) == raw, 'normative_delivery_source_changed')
    _ensure_work(store, held, pointer, current, build)


def _projection(store, held, options):
    build = _arguments(store, **options)
    pointer, current = restore_normative_checkpoint(store, held, options['registry'], build)
    current, plan = _checked_work(current, options['registry'], build)
    raw = _receipt(current, options['model'], plan)
    value = current.as_dict()
    files, result = native_result_projection(held.path, value, raw)
    _ensure_source(store, held, pointer, current, build, options['model'], plan, raw)
    return pointer, current, build, plan, raw, files, result


@dataclass(frozen=True, init=False)
class NormativeWorkResultDelivery:
    """Live verified output references, separate from the native commit proof."""

    _store: object
    _options: object
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use publish_normative_receipt_files')

    def as_dict(self):
        with self._store._location.inspect_checkpoint() as held:
            pointer, current, build, plan, raw, files, result = _projection(
                self._store, held, self._options)
            _require(canonical_json_bytes(result) == self._raw, 'result_delivery_binding_changed')
            _verify_files(held, files)
            _ensure_source(self._store, held, pointer, current, build,
                           self._options['model'], plan, raw)
            return result

    def __bool__(self):
        raise TypeError('Inspect the freshly verified result delivery explicitly')


def publish_normative_receipt_files(store, *, registry, model, policy, actor, request_id):
    """Deliver a proven historical result without any normative write or retry.

    Missing or conflicting native proof refuses delivery, even if output files
    already exist. Output failures preserve the native commit, checkpoint and
    actual result bytes; an explicit retry only fills missing output files.
    """
    options = dict(registry=registry, model=model, policy=policy, actor=actor, request_id=request_id)
    _arguments(store, **options)
    with store._location.inspect_checkpoint() as held:
        pointer, current, build, plan, raw, files, result = _projection(store, held, options)
        complete = _verify_files(held, files, allow_missing=True)
        _ensure_source(store, held, pointer, current, build, model, plan, raw)
        expected = canonical_json_bytes(result)
    if not complete:
        with store._location.for_checkpoint() as held:
            new_pointer, new_current, new_build, _, new_raw, new_files, new_result = _projection(
                store, held, options)
            _require(new_pointer == pointer and new_current.raw == current.raw
                     and new_build == build and new_raw == raw and new_files == files
                     and canonical_json_bytes(new_result) == expected,
                     'result_delivery_binding_changed')
            _verify_files(held, files, allow_missing=True)
            ensure = lambda: _ensure_source(store, held, pointer, current, build, model, plan, raw)
            for name, content in files:
                _publish_file(held, name, content, ensure)
            _verify_files(held, files)
            ensure()
    delivery = object.__new__(NormativeWorkResultDelivery)
    object.__setattr__(delivery, '_store', store)
    object.__setattr__(delivery, '_options', options)
    object.__setattr__(delivery, '_raw', expected)
    delivery.as_dict()
    return delivery
