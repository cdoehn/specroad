"""Shared dry-run/direct/saved-plan path with explicit publication delegation.

No filesystem backend is installed by this module. A trusted host registers a
transaction factory that owns authorization, live inventory, locks, journaling,
receipts and durability. A callback name is not evidence of these properties.
The dry-run path never enters that factory. This is not a sandbox for host code.
"""
from dataclasses import dataclass
from hashlib import sha256
from .errors import ChangePlanError
from .values import ChangePlan
from .target import assess_change_target, prepare_change_target
from .target_model import TargetModel
from .target_values import TargetAssessment, TargetPolicy
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
    request_id: str
    published_paths: tuple
    receipt_id: str

    def __post_init__(self):
        for v in (self.request_sha256, self.target_root_sha256):
            if type(v) is not str or len(v) != 64 or any(c not in '0123456789abcdef' for c in v):
                raise ChangeExecutionError('invalid_publication_receipt', exit_code=3)
        if not _text(self.request_id) or not _text(self.receipt_id):
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
        value = assessment.data
        old = {d.path: d.content for d in model.documents}
        if set(old) - {d.path for d in assessment.documents}:
            raise ChangeExecutionError('deletion_requires_specialized_backend', exit_code=3)
        changed = tuple(d for d in assessment.documents if old.get(d.path) != d.content)
        data = {'version': EXECUTION_VERSION, 'plan_sha256': assessment.plan.sha256,
                'plan_bytes_sha256': sha256(assessment.plan.source_bytes).hexdigest(),
                'request_id': assessment.plan.data['request_id'],
                'assessment_sha256': assessment.sha256,
                'base': _source_binding(model),
                'target_root_sha256': value['binding']['target_model_root'],
                'changed_paths': [d.path for d in changed],
                'target_files': [{'path': d.path, 'sha256': sha256(d.content).hexdigest()}
                                 for d in assessment.documents]}
        obj = object.__new__(cls)
        object.__setattr__(obj, '_encoded', canonical_json_bytes(data))
        object.__setattr__(obj, '_plan_bytes', assessment.plan.source_bytes)
        object.__setattr__(obj, 'documents', changed)
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
        changed = value['base_manifest'] != value['target_manifest']
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


def _arguments(plan, model, policy, gates, strict, fail_on_change):
    if type(plan) is not ChangePlan or type(model) is not TargetModel or type(policy) is not TargetPolicy:
        raise ChangeExecutionError('plan_model_policy_required', exit_code=2)
    if type(strict) is not bool or type(fail_on_change) is not bool:
        raise ChangeExecutionError('explicit_boolean_options_required', exit_code=2)
    if type(gates) not in (list, tuple):
        raise ChangeExecutionError('explicit_gate_sequence_required', exit_code=2)
    return ChangePlan(plan.source_bytes), model.snapshot(), tuple(gates)


def dry_run_change(plan, model, *, policy, gates=(), strict=False, fail_on_change=False):
    """Read supplied bytes only. No backend, lock, journal, receipt or output file.

    Trusted gates must themselves obey their read-only contract. This API does
    not sandbox Python extensions; no plan field registers one. An invalid
    target retains the full plan and diagnostics, not a success-only summary.
    """
    plan, model, gates = _arguments(plan, model, policy, gates, strict, fail_on_change)
    assessment = assess_change_target(plan, model, policy=policy, gates=gates, strict=strict)
    return ChangeExecutionResult._create(assessment, dry_run=True, fail_on_change=fail_on_change)


def apply_change_plan(plan, model, *, policy, backend=None, gates=(), strict=False):
    """Revalidate the SAME plan inside a host transaction and check its readback.

    No native publication is available without explicit trusted integration.
    No automatic retry/rollback on errors, including failures after publication.
    A receipt is evidence of the adapter's assertion, not an fsync/auth proof.
    """
    plan, model, gates = _arguments(plan, model, policy, gates, strict, False)
    checked = assess_change_target(plan, model, policy=policy, gates=gates, strict=strict)
    if not checked.target_validated:
        return ChangeExecutionResult._create(checked, dry_run=False)
    if type(backend) is not ChangeBackend:
        raise ChangeExecutionError('transaction_backend_required')
    request = PublicationRequest._create(checked, model)
    completed = None
    try:
        with backend.transaction(request) as transaction:
            current = transaction.read_model()
            if type(current) is not TargetModel:
                raise ChangeExecutionError('backend_model_required')
            current = current.snapshot()
            if _source_binding(current) != request.data['base']:
                raise ChangeExecutionError('publication_base_changed', exit_code=6)
            fresh = assess_change_target(plan, current, policy=policy, gates=gates, strict=strict)
            if not fresh.target_validated:
                return ChangeExecutionResult._create(fresh, dry_run=False)
            fresh_request = PublicationRequest._create(fresh, current)
            if fresh_request.sha256 != request.sha256:
                raise ChangeExecutionError('publication_assessment_changed', exit_code=6)
            receipt = transaction.publish(fresh_request)
            if (type(receipt) is not PublicationReceipt or
                    receipt.request_sha256 != request.sha256 or
                    receipt.target_root_sha256 != request.data['target_root_sha256'] or
                    receipt.request_id != request.data['request_id'] or
                    set(receipt.published_paths) != set(request.data['changed_paths'])):
                raise ChangeExecutionError('publication_receipt_mismatch')
            after = transaction.read_model()
            if type(after) is not TargetModel:
                raise ChangeExecutionError('backend_model_required')
            after = after.snapshot()
            expected_files = dict(current.source_files)
            expected_files.update({d.path: d.content for d in fresh.documents})
            if (after.binding != current.binding or after.source_files != expected_files or
                    after.resources_sha256 != current.resources_sha256 or
                    after.manifest(after.artifacts, plan.data['base']['scope_descriptor']).sha256 != request.data['target_root_sha256']):
                raise ChangeExecutionError('publication_target_mismatch')
            completed = ChangeExecutionResult._create(fresh, dry_run=False, receipt=receipt, backend=backend)
        if completed is None:
            raise ChangeExecutionError('publication_not_confirmed')
        return completed
    except Exception as error:
        # Even entering/closing a supplied transaction can have side effects.
        # Never claim rollback, unmodified files or retry safety here.
        reason = error.reason if type(error) is ChangeExecutionError else 'transaction_backend_error'
        code = error.exit_code if type(error) is ChangeExecutionError else 5
        raise ChangeExecutionError(reason, exit_code=code, write_state='unknown') from error


def execute_change_request(model, operations, *, dry_run, policy, backend=None,
        gates=(), strict=False, fail_on_change=False, **plan_fields):
    """Direct authoring and dry-run share identical plan construction.

    IDs/actor/request/time must be explicitly supplied, never generated here.
    fail_on_change belongs to the dry-run, not a write followed by error code 1.
    """
    if type(dry_run) is not bool or type(fail_on_change) is not bool:
        raise ChangeExecutionError('explicit_boolean_options_required', exit_code=2)
    if fail_on_change and not dry_run:
        raise ChangeExecutionError('fail_on_change_requires_dry_run', exit_code=2)
    if type(gates) not in (tuple, list) or type(strict) is not bool:
        raise ChangeExecutionError('explicit_gate_sequence_and_boolean_required', exit_code=2)
    assessment = prepare_change_target(model, operations, policy=policy, gates=tuple(gates),
                                       strict=strict, **plan_fields)
    if dry_run:
        return ChangeExecutionResult._create(assessment, dry_run=True, fail_on_change=fail_on_change)
    return apply_change_plan(assessment.plan, model, policy=policy, backend=backend,
                             gates=tuple(gates), strict=strict)
