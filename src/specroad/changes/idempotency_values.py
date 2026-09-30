"""Owned retry values and conflict diagnostics; no filesystem or planning."""
from dataclasses import dataclass
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from .receipt_values import ReceiptError


class RequestIdConflict(ReceiptError):
    """A different operation sequence reused an already committed request ID."""
    def __init__(self, identity, expected_hash, received_hash, *, path):
        super().__init__('request_operations_conflict', exit_code=6, path=path)
        self.write_state = 'not_committed'
        self.request_id = identity
        self.expected_hash, self.received_hash = expected_hash, received_hash

    def diagnostic(self):
        return {**super().diagnostic(), 'request_id': self.request_id,
                'expected_operations_sha256': self.expected_hash,
                'received_operations_sha256': self.received_hash,
                'existing_request_committed': True, 'receipt_verified': True,
                'recovery_required': False, 'write_authorized': False}


@dataclass(frozen=True, init=False)
class RequestResolution:
    """Owned historical result or non-authorizing absence observation."""
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_normative_request')

    @classmethod
    def _create(cls, identity, receipt=None, *, applicable=True):
        obj = object.__new__(cls)
        saved = None if receipt is None else receipt.data
        value = {'format_version': 'normative-request-resolution-v1',
                 'namespace': 'normative_write', 'request_id': identity,
                 'action': ('replay' if saved is not None else 'new_request') if applicable else 'not_applicable',
                 'receipt_verified': saved is not None,
                 'receipt': None if saved is None else {'path': receipt.path, 'sha256': receipt.sha256},
                 'result_object': None if saved is None else saved['result_object'],
                 'created_ids': [] if saved is None else saved['created_ids'],
                 'original_request': saved, 'normative_writes': 0,
                 'write_authorized': False, 'atomic_snapshot': False,
                 'current_target_verified': False, 'authenticity_verified': False,
                 'locked_recheck_required': applicable and saved is None}
        object.__setattr__(obj, '_raw', canonical_json_bytes(value))
        return obj

    @property
    def data(self):
        return parse_json_object(self._raw)

    def __bool__(self):
        raise TypeError('Inspect action; a receipt is not permission to write')


