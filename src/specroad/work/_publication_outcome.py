"""Frozen Work publication result assembled only from bound native receipts.

The coordinator owns all Work and transaction activity. This module only checks
and projects their already obtained observations; it opens no files or locks.
"""

from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from .resume import _require


@dataclass(frozen=True, init=False)
class NormativeWorkPublication:
    """Verified native receipt, separate from final normative Work delivery."""

    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use publish_normative_work')

    def as_dict(self):
        return parse_json_object(self._raw)

    def __bool__(self):
        raise TypeError('Inspect the confirmed transaction result explicitly')


def _publication_result(current, resolution, completion, *, published):
    value = current.as_dict()
    resolved, committed = resolution.data, completion.data
    _require(resolved['action'] == 'replay' and resolved['receipt_verified'],
             'normative_receipt_required')
    result_object = resolved['result_object']
    # The two native readers each verify their own observation. Bind those
    # observations to one receipt before combining them into a Work result.
    _require(committed['commit_completed'] and committed['receipt_verified']
             and committed['state'] == 'committed'
             and committed['transaction_id'] == result_object['transaction_id']
             and committed['request_id'] == resolved['request_id'] == value['request_id']
             and committed['project_id'] == resolved['original_request']['project_id']
                 == value['source_bindings']['project_id']
             and committed['target_model_root_sha256'] == result_object['target_model_root_sha256']
             and committed['receipts']['request'] == resolved['receipt'],
             'normative_receipt_binding_changed')
    result = object.__new__(NormativeWorkPublication)
    object.__setattr__(result, '_raw', canonical_json_bytes({
        'format_version': 'normative-work-publication-v1', 'work_id': value['work_id'],
        'checkpoint_generation': value['checkpoint_generation'],
        'checkpoint_sha256': value['checkpoint_sha256'], 'checkpoint_changed': False,
        'work_completion_recorded': False, 'publication_performed': published,
        'transaction': committed, 'request_resolution': resolved,
        'result_object': result_object}))
    return result
