"""Typed standard lifecycle writes with native guards, audit and recovery.

The host supplies the complete model, authority and audit/transaction inputs.
This embedding service neither registers a CLI nor authenticates stored history.
Keep the original normalized operation for retries, including its from/guards.
"""
from ..changes import (AuthoringError, ChangeOperation, TargetModel,
    TargetPolicy, PublicationAuthority, prepare_authoring_request,
    prepare_publication_check, recheck_publication,
    project_lock, begin_building_journal, stage_building_journal,
    publish_prepared_journal, read_committing_journal, finalize_committing_journal,
    cleanup_completed_transaction, read_transaction_completion, resolve_normative_request)
from .plans import prepare_authoring_target as prepare_change_target
from ..changes._journal_codec import _transaction
from ..changes._publication_observation import _root
from ..changes.lifecycle_inputs import (
    _UNSPECIFIED, normalize_transition_input, normalize_retire_input)
from ..changes.lifecycle_gate import _prepare_lifecycle_gate
from ..model.audit_values import UtcTimestamp
from ..model.errors import ModelError
from ..storage.project import ProjectSource
from ..validation import ModelGate

_POLICY = TargetPolicy('lifecycle.transition', '1', ())
_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


def _result(operation, completion, *, replayed=False):
    return {'format_version': '1.0.0', 'command_id': 'lifecycle.transition',
        'artifact_id': operation.data['target'], 'operation': operation.op,
        'no_change': completion is None,
        'write_state': 'not_committed' if completion is None else 'committed',
        'replayed': replayed, 'completion': None if completion is None else completion.data}


def _replay(source, request, operation):
    resolution = resolve_normative_request(source, request).data
    if resolution['action'] != 'replay':
        return None
    completion = read_transaction_completion(source, resolution['original_request']['transaction_id'])
    if completion.data['receipts']['request'] != resolution['receipt']:
        raise AuthoringError('request_receipt_changed', exit_code=6)
    return _result(operation, completion, replayed=True)


def transition_artifact(model, operation, **options):
    """Publish one explicit native transition after complete target checks."""
    return _execute(model, operation, expected_kind='transition', **options)


def retire_artifact(model, operation, **options):
    """Publish guarded retirement, or freshly authorize a guarded no-op."""
    return _execute(model, operation, expected_kind='retire', **options)


def _execute(model, operation, *, expected_kind, actor, planned_at, change_plan_id,
        transaction_id, authority, request_id=None, gates=(), strict=False, package_files=()):
    if (type(model) is not TargetModel or type(operation) is not ChangeOperation
            or type(authority) is not PublicationAuthority):
        raise AuthoringError('typed_lifecycle_inputs_required')
    operation = ChangeOperation(operation.data)
    if operation.op != expected_kind:
        raise AuthoringError('lifecycle_operation_required', pointer='/op')
    if type(gates) not in (list, tuple) or type(strict) is not bool:
        raise AuthoringError('explicit_lifecycle_options_required')
    # Keep the host's original gate selection across external source callbacks.
    gates = tuple(gates)
    if type(change_plan_id) is not str or not change_plan_id.strip() or '\0' in change_plan_id:
        raise AuthoringError('change_plan_identity_required')
    _transaction(transaction_id)
    request = prepare_authoring_request(command_id='lifecycle transition', actor=actor,
        operations=[operation.data], request_id=request_id)
    actor, request_id = request.data['actor'], request.data['request_id']
    try:
        UtcTimestamp(planned_at)
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    source = ProjectSource(model.binding.source_root, expected_project_id=model.binding.project_id)
    if source.boundary._root_identity != model.binding.root_identity:
        raise AuthoringError('lifecycle_project_changed', exit_code=6)
    replay = _replay(source, request, operation)
    if replay is not None:
        return replay
    model = model.snapshot()
    if not any(type(gate) is ModelGate and gate.gate_id == 'lifecycle' for gate in gates):
        gates = (*gates, _prepare_lifecycle_gate(model, operation, actor=actor, planned_at=planned_at))
    with project_lock(source.boundary.root, kind='writer', command='change apply',
            project_id=model.configuration.project_id, request_id=request_id,
            transaction_id=transaction_id) as held:
        replay = _replay(source, request, operation)
        if replay is not None:
            return replay
        current = _root(model)
        held.require_publication(current, command='change apply', request_id=request_id,
                                 transaction_id=transaction_id)
        checked = prepare_change_target(model, [operation.data], change_plan_id=change_plan_id,
            request_id=request_id, actor=actor, planned_at=planned_at, scope_descriptor=_SCOPE,
            metadata_policy_version='change-metadata-v1', policy=_POLICY, gates=gates, strict=strict)
        checked.require_valid()
        preflight = prepare_publication_check(checked.plan, model, policy=_POLICY,
            gates=gates, strict=strict, package_files=package_files)
        if not preflight.request.documents:
            recheck_publication(preflight, preflight.request, held_lock=held,
                transaction_id=transaction_id, authority=authority, gates=gates)
            return _result(operation, None)
        journal = begin_building_journal(preflight, held_lock=held,
            transaction_id=transaction_id, authority=authority, gates=gates)
        journal = stage_building_journal(preflight, journal, held_lock=held,
            authority=authority, gates=gates)
        publication = publish_prepared_journal(preflight, journal, held_lock=held,
            authority=authority, gates=gates)
        committing = read_committing_journal(current, transaction_id,
            expected_sha256=publication.data['journal_sha256'], preflight=preflight)
        finalize_committing_journal(preflight, committing, held_lock=held,
            authority=authority, gates=gates)
        completion = cleanup_completed_transaction(preflight, transaction_id,
            held_lock=held, authority=authority)
        return _result(operation, completion)
