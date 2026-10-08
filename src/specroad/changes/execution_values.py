"""Stable execution data contracts; no built-in write or authorization service."""
from dataclasses import dataclass
from hashlib import sha256
from .errors import ChangePlanError
from .values import ChangePlan
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object

EXECUTION_VERSION = 'change-execution-v1'


class ChangeExecutionError(ChangePlanError):
    """An apply adapter failure. Unknown publication is never safe to retry blindly."""
    def __init__(self, reason, *, exit_code=5, write_state='not_committed'):
        super().__init__(reason, code='SRV146')
        self.exit_code = exit_code
        self.write_state = write_state

    def diagnostic(self):
        return {**super().diagnostic(), 'write_state': self.write_state,
                'retry_safe': False, 'automatic_rollback': False}


def _text(value):
    return type(value) is str and bool(value.strip()) and '\0' not in value


@dataclass(frozen=True)
class ChangeBackend:
    """Trusted application registration, not deserialized plan data.

    transaction(request) returns a context manager with read_model() and
    publish(request). It must fail closed on denied authorization/recovery,
    hold the actual writer lock through revalidation/publication/readback,
    verify inventory completeness, and persist its own bound request receipt.
    No such native filesystem backend is provided in this step.
    """
    backend_id: str
    version: str
    transaction: object

    def __post_init__(self):
        if not _text(self.backend_id) or not _text(self.version) or not callable(self.transaction):
            raise ChangeExecutionError('registered_transaction_backend_required', exit_code=2)


@dataclass(frozen=True)
class PublicationReceipt:
    """Backend attestation, not independently authenticated/durable-file evidence."""
    request_sha256: str
    target_root_sha256: str
    request_id: str | None
    published_paths: tuple
    receipt_id: str

    def __post_init__(self):
        for v in (self.request_sha256, self.target_root_sha256):
            if type(v) is not str or len(v) != 64 or any(c not in '0123456789abcdef' for c in v):
                raise ChangeExecutionError('invalid_publication_receipt', exit_code=3)
        from .request_ids import normalize_request_id
        if self.request_id is not None and type(self.request_id) is not str:
            raise ChangeExecutionError("invalid_publication_receipt", exit_code=3)
        normalize_request_id(self.request_id)
        if not _text(self.receipt_id):
            raise ChangeExecutionError('invalid_publication_receipt', exit_code=3)
        if (type(self.published_paths) is not tuple or
                any(not _text(p) for p in self.published_paths) or
                len(set(self.published_paths)) != len(self.published_paths)):
            raise ChangeExecutionError('invalid_publication_receipt', exit_code=3)


def _source_binding(model):
    return {'project_id': model.binding.project_id,
            'source_root': model.binding.source_root,
            'root_identity': list(model.binding.root_identity),
            'resources_sha256': model.resources_sha256,
            'sources': [{'path': p, 'sha256': sha256(b).hexdigest()}
                        for p, b in sorted(model.source_files.items())]}


@dataclass(frozen=True, init=False)
class PublicationRequest:
    """Frozen handoff binding. Possessing it is not a write capability."""
    _encoded: bytes
    _plan_bytes: bytes
    documents: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError('Use the checked change execution path')

    @classmethod
    def _create(cls, assessment, model):
        from .authoring import require_direct_authoring
        authoring = require_direct_authoring(assessment.plan)
        value = assessment.data
        old = model.source_files
        if {d.path for d in model.documents} - {d.path for d in assessment.documents}:
            raise ChangeExecutionError('deletion_requires_specialized_backend', exit_code=3)
        changed = tuple(d for d in assessment.publication_documents if old.get(d.path) != d.content)
        data = {'version': EXECUTION_VERSION, 'plan_sha256': assessment.plan.sha256,
                'plan_bytes_sha256': sha256(assessment.plan.source_bytes).hexdigest(),
                'request_id': assessment.plan.data['request_id'],
                'assessment_sha256': assessment.sha256,
                'authoring_binding': authoring.data, 'authoring_sha256': authoring.sha256,
                'base': _source_binding(model),
                'target_root_sha256': value['binding']['target_model_root'],
                'changed_paths': [d.path for d in changed],
                'target_files': [{'path': d.path, 'sha256': sha256(d.content).hexdigest()}
                                 for d in assessment.publication_documents]}
        obj = object.__new__(cls)
        object.__setattr__(obj, '_encoded', canonical_json_bytes(data))
        object.__setattr__(obj, '_plan_bytes', assessment.plan.source_bytes)
        object.__setattr__(obj, 'documents', changed)
        return obj

    def detached(self):
        # No caller-owned mutable mappings or backend-retained request objects.
        from ..validation import ModelDocument
        obj = object.__new__(PublicationRequest)
        object.__setattr__(obj, '_encoded', self._encoded)
        object.__setattr__(obj, '_plan_bytes', self._plan_bytes)
        object.__setattr__(obj, 'documents', tuple(ModelDocument(d.path, d.content) for d in self.documents))
        return obj

    @property
    def data(self): return parse_json_object(self._encoded)
    @property
    def sha256(self): return sha256(self._encoded).hexdigest()
    @property
    def plan(self): return ChangePlan(self._plan_bytes)


@dataclass(frozen=True, init=False)
class ChangeExecutionResult:
    """Full plan/diff/impact/diagnostics, separate from publication state."""
    _encoded: bytes
    _plan_bytes: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use dry_run_change or apply_change_plan')

    @classmethod
    def _create(cls, assessment, *, dry_run, fail_on_change=False, receipt=None, backend=None):
        value = assessment.data
        changed = (value['base_manifest'] != value['target_manifest'] or
                   bool(value.get('representation', {}).get('changed_paths', [])))
        valid = assessment.target_validated
        exit_code = value['validation']['exit_code']
        if not valid and exit_code == 0:
            exit_code = 3  # Missing command gates never yield a successful request.
        if valid:
            exit_code = 1 if dry_run and fail_on_change and changed else 0
        data = {'format_version': EXECUTION_VERSION, 'dry_run': dry_run,
                'fail_on_change': fail_on_change, 'would_change': changed,
                'exit_code': exit_code, 'status': 'success' if exit_code == 0 else 'failed',
                'write_state': 'committed' if receipt is not None else 'not_committed',
                'target_validated': valid, 'plan': assessment.plan.data,
                'plan_sha256': assessment.plan.sha256, 'assessment': value,
                'diff': value['diff'], 'impact': value['impact'],
                'diagnostics': value['validation']['diagnostics'],
                'expected_model_root': value['binding']['target_model_root'],
                'backend_receipt': None if receipt is None else {
                    'backend_id': backend.backend_id, 'backend_version': backend.version,
                    'receipt_id': receipt.receipt_id, 'request_id': receipt.request_id,
                    'request_sha256': receipt.request_sha256,
                    'target_root_sha256': receipt.target_root_sha256,
                    'published_paths': sorted(receipt.published_paths)},
                'validation_scope': 'supplied_model_execution_adapter',
                'receipt_file_verified': False, 'durability_verified': False,
                'project_inventory_verified': False, 'approval_granted': False}
        obj = object.__new__(cls)
        object.__setattr__(obj, '_encoded', canonical_json_bytes(data))
        object.__setattr__(obj, '_plan_bytes', assessment.plan.source_bytes)
        return obj

    @property
    def data(self): return parse_json_object(self._encoded)
    @property
    def plan(self): return ChangePlan(self._plan_bytes)
    @property
    def exit_code(self): return self.data['exit_code']
    @property
    def write_state(self): return self.data['write_state']

    def __bool__(self):
        raise TypeError('Inspect exit_code, target_validated and write_state explicitly')
