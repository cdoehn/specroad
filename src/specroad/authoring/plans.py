"""Shared plan construction and read-only previews for native authoring families.

Operations are already normalized and contain explicit IDs and audit inputs.
This API neither allocates/reserves IDs nor discovers a complete live project.
An inspected plan is data; native execution must reauthorize and revalidate it.
"""
from ..changes.authoring import prepare_authoring_request
from ..changes.execution_values import ChangeExecutionResult
from ..changes.request_ids import AuthoringError
from ..changes.target import prepare_change_target as _prepare_target
from ..changes.target_values import TargetPolicy
from ..changes.target_model import TargetModel
from ..changes.values import ChangeOperation
from ..changes.update_lifecycle_gate import prepare_update_lifecycle_gate
from ..changes.lifecycle_gate import _prepare_lifecycle_gate
from ..changes.negative_reviews import prepare_review_outcome_gates
from ..changes.receipt_values import _created_ids
from ..validation import ModelGate

_OPERATIONS = {'artifact.create': ('create',), 'artifact.update': ('update',),
    'lifecycle.transition': ('transition', 'retire'),
    'relation.add': ('relation_add',), 'relation.remove': ('relation_remove',),
    'relation.review': ('relation_review_record',), 'baseline.create': ('baseline_create',),
    'evidence.record': ('evidence_record',),
    'document.create': ('create',), 'section.add': ('create', 'relation_add'),
    'section.move': ('relation_remove', 'relation_add'),
    'block.add': ('create', 'relation_add'), 'block.update': ('update',),
    'block.remove': ('retire',), 'section.remove': ('retire', 'relation_remove', 'relation_add')}
_DOCUMENT_MUTATIONS = ('block.add', 'block.update', 'block.remove', 'section.remove')
_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


def _operations(command_id, operations):
    if type(command_id) is str and command_id in _DOCUMENT_MUTATIONS:
        from ._document_mutations import _mutation_operations
        return _mutation_operations(command_id, operations)
    if type(command_id) is str and command_id in ('document.create', 'section.add', 'section.move'):
        from ._document_operations import _document_operations
        return _document_operations(command_id, operations)
    if type(command_id) is not str or command_id not in _OPERATIONS:
        raise AuthoringError('supported_authoring_command_required')
    if type(operations) not in (list, tuple) or len(operations) != 1:
        raise AuthoringError('one_authoring_operation_required')
    owned = [ChangeOperation(value).data for value in operations]
    if owned[0]['op'] not in _OPERATIONS[command_id]:
        raise AuthoringError('authoring_command_operation_mismatch')
    return owned


def prepare_authoring_target(model, operations, *, policy, **fields):
    """The native direct adapters and preview use exactly the same planner.

    This is plan construction only. Existing direct adapters enforce actor,
    allocation, inventory and authority before their own publication boundary.
    """
    if type(policy) is not TargetPolicy:
        raise AuthoringError('typed_authoring_policy_required')
    owned = _operations(policy.command_id, operations)
    return _prepare_target(model, owned, policy=policy, **fields)


def _execution_policy(command_id):
    if command_id == 'evidence.record':
        return TargetPolicy(command_id, 'evidence-record-v1', ('extension:evidence-record',))
    if command_id in ('document.create', 'section.add', 'section.move', *_DOCUMENT_MUTATIONS):
        return TargetPolicy(command_id, 'document-authoring-v1', ('extension:document-authoring',))
    return (TargetPolicy(command_id, 'review-outcome-v1', ('extension:review-withdrawal',))
        if command_id == 'relation.review' else TargetPolicy(command_id, '1', ()))


def _execution_inputs(model, command_id, operations, actor, planned_at, gates):
    owned = _operations(command_id, operations)
    if type(gates) not in (list, tuple):
        raise AuthoringError('explicit_authoring_gates_required')
    gates = tuple(gates)
    policy = _execution_policy(command_id)
    operation = ChangeOperation(owned[0])
    lifecycle = any(type(gate) is ModelGate and gate.gate_id == 'lifecycle' for gate in gates)
    if command_id == 'artifact.update' and not lifecycle:
        gates += (prepare_update_lifecycle_gate(model, operation,
            metadata_policy_version='change-metadata-v1', actor=actor, planned_at=planned_at),)
    elif command_id == 'lifecycle.transition' and not lifecycle:
        gates += (_prepare_lifecycle_gate(model, operation, actor=actor, planned_at=planned_at),)
    elif command_id == 'relation.review':
        gates += prepare_review_outcome_gates(model, operation, actor=actor, planned_at=planned_at)
    elif command_id == 'baseline.create':
        from ..changes.baselines import prepare_baseline_gates
        gates += prepare_baseline_gates(model, operation, actor=actor, planned_at=planned_at, gates=gates)
    elif command_id == 'evidence.record':
        from ..changes.evidence import prepare_evidence_gates
        gates += prepare_evidence_gates(model, operation, actor=actor, planned_at=planned_at, gates=gates)
    elif command_id in ('document.create', 'section.add', 'section.move', *_DOCUMENT_MUTATIONS):
        from ._document_validation import _document_gates
        mutation = command_id in _DOCUMENT_MUTATIONS
        if mutation:
            from ._document_mutations import _mutation_scope
            from ._document_mutation_validation import _mutation_lifecycle
            _mutation_scope(model, command_id, owned)
            if not lifecycle:
                gates += (_mutation_lifecycle(model, owned, actor=actor, planned_at=planned_at),)
        gates = _document_gates(model, command_id, owned, gates,
            block_semantics=mutation or command_id == 'section.move')
    return owned, policy, gates


def _audit(plan, command_id, *, dry_run, write_state, replayed=False):
    value = plan.data
    return {'format_version': 'authoring-audit-v1', 'command_id': command_id,
        'command_class': 'normative_write', 'dry_run': dry_run,
        'write_state': write_state, 'replayed': replayed,
        'change_plan_id': value['change_plan_id'], 'plan_sha256': plan.sha256,
        'request_id': value['request_id'], 'actor': value['actor'],
        'planned_at': value['planned_at'], 'operations': value['operations'],
        'base_model_root_sha256': value['base']['model_root_sha256'],
        'target_model_root_sha256': value['expected_result']['model_root_sha256'],
        'created_ids': _created_ids(value['operations']), 'approval_granted': False}


def preview_authoring_request(model, command_id, operations, *, actor, planned_at,
        change_plan_id, request_id=None, gates=(), strict=False, fail_on_change=False):
    """Return a saveable full plan, target, diff, impact, diagnostics and audit.

    No lock, receipt, authority callback, filesystem write or new identity.
    The host supplies typed model bytes, prepared operations and trusted gates.
    A later write must use the saved plan; reallocation is a different request.
    """
    if type(model) is not TargetModel:
        raise AuthoringError('typed_authoring_model_required')
    if type(strict) is not bool or type(fail_on_change) is not bool:
        raise AuthoringError('explicit_boolean_options_required')
    model = model.snapshot()
    owned = _operations(command_id, operations)
    request = prepare_authoring_request(command_id=command_id.replace('.', ' '),
        operations=owned, actor=actor, request_id=request_id, dry_run=True).data
    owned, policy, gates = _execution_inputs(model, command_id, owned,
        request['actor'], planned_at, gates)
    checked = prepare_authoring_target(model, owned, policy=policy, gates=gates,
        actor=request['actor'], planned_at=planned_at, change_plan_id=change_plan_id,
        request_id=request['request_id'], scope_descriptor=_SCOPE,
        metadata_policy_version='change-metadata-v1', strict=strict)
    result = ChangeExecutionResult._create(checked, dry_run=True, fail_on_change=fail_on_change).data
    return {**result, 'command_id': command_id,
        'audit': _audit(checked.plan, command_id, dry_run=True, write_state='not_committed')}
