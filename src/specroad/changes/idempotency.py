"""Normative retries use confirmed local receipts, never a second publication.

A missing receipt is an observation, not a reservation or writer permission.
The native locked publication gate checks again. Read-only analysis correlation
is not an AuthoringRequest and cannot enter this API. No plan/model is rebuilt.
"""
from dataclasses import dataclass
import os
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from .authoring import AuthoringRequest, prepare_authoring_request
from .execution_values import ChangeExecutionError
from ._lock_files import LockFiles
from ._journal_io import _read
from .receipt_read import read_transaction_completion
from .receipt_values import ReceiptError, RequestReceipt, request_receipt_path


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


def _request_bytes(files, path):
    """A descriptor-bound hint; completion proof is checked separately."""
    with files.directory(tuple(path.split('/')[:-1])) as directory:
        if directory is None:
            return None
        name = path.rsplit('/', 1)[-1]
        try:
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return None
        identity = (info.st_dev, info.st_ino)
        raw = _read(directory, name, expected_identity=identity)
        return raw, identity


def _confirmed_receipt(source, identity):
    path = request_receipt_path(identity)
    source.check_current()
    with LockFiles(source.boundary.root) as files:
        if files.boundary._root_identity != source.boundary._root_identity:
            raise ReceiptError('request_root_changed', exit_code=6)
        first = _request_bytes(files, path)
        if first is None:
            source.check_current()
            if _request_bytes(files, path) is not None:
                raise ReceiptError('request_receipt_changed', exit_code=6, path=path)
            return None
        receipt = RequestReceipt(first[0])
        if (receipt.path != path or receipt.data['request_id'] != identity
                or receipt.data['project_id'] != source.configuration.project_id):
            raise ReceiptError('request_project_binding_mismatch', exit_code=6, path=path)
        proof = read_transaction_completion(source, receipt.data['transaction_id'])
        if proof.data['receipts']['request'] != {'path': path, 'sha256': receipt.sha256}:
            raise ReceiptError('request_completion_link_mismatch', exit_code=6, path=path)
        if _request_bytes(files, path) != first:
            raise ReceiptError('request_receipt_changed', exit_code=6, path=path)
        source.check_current()
        return receipt


def resolve_normative_request(source, request):
    """Return the SAME stored semantic result/IDs for the same ID + op hash.

    Supply prepare_authoring_request(...) BEFORE planning or taking a writer
    lock. The historical actor/base/target are returned, not relabelled as the
    retry's actor or today's model. A receipt alone without committed proof is
    never success. This is not a generic analyzer request-ID lookup.
    """
    if type(source) is not ProjectSource or type(request) is not AuthoringRequest:
        raise ReceiptError('typed_normative_request_and_source_required', exit_code=2)
    try:
        data = request.data
        if data.get('namespace') != 'normative_write':
            raise ReceiptError('normative_request_namespace_required', exit_code=2)
        normalized = prepare_authoring_request(command_id=data['command_id'], actor=data['actor'],
            operations=data['operations'], request_id=data['request_id'],
            dry_run=data['dry_run'], as_proposal=data['as_proposal']).data
        extra = set(data) - set(normalized)
        plan_fields = {'plan_sha256', 'base_model_root_sha256', 'scope_descriptor'}
        if extra and extra != plan_fields:
            raise ReceiptError('normative_request_fields_invalid', exit_code=2)
        if any(data.get(key) != value for key, value in normalized.items()):
            raise ReceiptError('normative_request_binding_changed', exit_code=2)
        identity = normalized['request_id']
        if normalized['dry_run'] or identity is None:
            return RequestResolution._create(identity, applicable=False)
        receipt = _confirmed_receipt(source, identity)
        if receipt is not None and receipt.data['operations_sha256'] != normalized['operation_sequence_sha256']:
            raise RequestIdConflict(identity, receipt.data['operations_sha256'],
                                    normalized['operation_sequence_sha256'], path=receipt.path)
        return RequestResolution._create(identity, receipt)
    except (OSError, ModelError, SafetyViolation, ChangeExecutionError) as error:
        if isinstance(error, ReceiptError):
            raise
        raise ReceiptError(getattr(error, 'reason', 'request_receipt_read_failed'),
            exit_code=getattr(error, 'exit_code', 7 if isinstance(error, SafetyViolation) else 5),
            path=getattr(error, 'path', None)) from error
    except (KeyError, TypeError, ValueError) as error:
        raise ReceiptError('normative_request_fields_invalid', exit_code=2) from error
