"""Typed standard lifecycle writes with native guards, audit and recovery.

The host supplies the complete model, authority and audit/transaction inputs.
This embedding service neither registers a CLI nor authenticates stored history.
Keep the original normalized operation for retries, including its from/guards.
"""
from ..changes import (AuthoringError, ChangeOperation, ChangePlanError, TargetModel,
    TargetPolicy, PublicationAuthority, prepare_authoring_request,
    prepare_change_target, prepare_publication_check, recheck_publication,
    project_lock, begin_building_journal, stage_building_journal,
    publish_prepared_journal, read_committing_journal, finalize_committing_journal,
    cleanup_completed_transaction, read_transaction_completion, resolve_normative_request)
from ..changes._common import _text
from ..changes._journal_codec import _transaction
from ..changes._metadata_policy import bind_policy
from ..changes._publication_observation import _root
from ..changes.lifecycle import prepare_change_lifecycle
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from ..validation import ModelGate

_UNSPECIFIED = object()
_POLICY = TargetPolicy('lifecycle.transition', '1', ())
_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


def normalize_transition_input(artifact, *, to, reason=_UNSPECIFIED):
    """Own the original target/from and an explicit requested maturity."""
    try:
        base = parse_json_object(canonical_json_bytes(artifact))
        metadata = {}
        if reason is not _UNSPECIFIED:
            _text(reason, '/metadata/reason')
            metadata['reason'] = reason
        return ChangeOperation({'op': 'transition', 'target': artifact_identity(base).id,
            'from': base.get('maturity'), 'to': to, 'metadata': metadata})
    except ChangePlanError:
        raise
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error


def normalize_retire_input(artifact, *, reason, expected_revision=_UNSPECIFIED,
                           expected_sha256=_UNSPECIFIED):
    """Require explicit revision/hash guards; None is not an omitted guard."""
    try:
        base = parse_json_object(canonical_json_bytes(artifact))
        value = {'op': 'retire', 'target': artifact_identity(base).id, 'reason': reason}
        if expected_revision is not _UNSPECIFIED:
            value['expected_revision'] = expected_revision
        if expected_sha256 is not _UNSPECIFIED:
            value['expected_sha256'] = expected_sha256
        return ChangeOperation(value)
    except ChangePlanError:
        raise
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error


def _prepare_lifecycle_gate(model, operation, *, actor, planned_at):
    """Recompute this operation's entire target on every semantic check.

    Only the requested standard subject is certified. Other non-draft subjects,
    specialist records and approval history still need their actual services.
    The native lifecycle fold retains all transition and approval refusals.
    """
    owned = model.snapshot()
    operation = ChangeOperation(operation.data)
    metadata = bind_policy('change-metadata-v1', actor, planned_at)
    identity = operation.data['target']
    maturity = 'retired' if operation.op == 'retire' else operation.data['to']
    resources = canonical_json_sha256({'model_sources_sha256': owned._sources_sha256,
        'operation': operation.data, 'metadata': metadata})

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    def check(context):
        if context.subjects != (identity,) or context.artifact(identity)['maturity'] != maturity:
            return context.result([{'reason': 'lifecycle_subject_not_supported', 'severity': 'error'}])
        folded = prepare_change_lifecycle(owned.artifacts, [operation.data],
            **metadata, source_files=owned.source_files, **owned.reservations)
        expected = {a['id']: a for a in folded.artifacts}
        actual = {key: context.artifact(key) for key in context.all_ids}
        if canonical_json_sha256(expected) != canonical_json_sha256(actual):
            return context.result([{'reason': 'lifecycle_target_mismatch',
                                    'severity': 'error', 'artifact_id': identity}])
        return context.result()

    return ModelGate('lifecycle', 'bound-authoring-lifecycle-v1', dependencies, check, resources)


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
