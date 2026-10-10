"""Artifact updates through the common planner and native publication protocol.

The host supplies the complete TargetModel, authority, actor, time and IDs.
This embedding service does not register a CLI or discover a production model.
Retain the original normalized operation for retries; recompiling field options
against a later artifact is a different request, not historical intent.
"""
from ..changes import (AuthoringError, ChangeOperation, ChangePlanError, TargetModel,
    TargetPolicy, PublicationAuthority, prepare_authoring_request,
    prepare_change_target, prepare_publication_check, recheck_publication,
    project_lock, begin_building_journal, stage_building_journal,
    publish_prepared_journal, read_committing_journal, finalize_committing_journal,
    cleanup_completed_transaction, read_transaction_completion, resolve_normative_request)
from ..changes._journal_codec import _transaction
from ..changes._publication_observation import _root
from ..changes.field_patches import compile_field_patch
from ..changes.json_patch import JsonPatch
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from .inputs import _read_input

_UNSPECIFIED = object()
_POLICY = TargetPolicy('artifact.update', '1', ())
_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


def normalize_artifact_update_input(artifact, *, patch=_UNSPECIFIED, options=_UNSPECIFIED,
        expected_revision=_UNSPECIFIED, expected_sha256=_UNSPECIFIED):
    """Own RFC-6902 values or ordered set/unset pairs with explicit guards.

    Presence and shape are checked here; the full planner checks the actual
    target and both supplied guards. None is not an omitted precondition.
    No revision, identity, time, lifecycle decision or live authority is inferred.
    """
    if (patch is _UNSPECIFIED) == (options is _UNSPECIFIED):
        raise AuthoringError('exactly_one_update_input_required')
    try:
        base = parse_json_object(canonical_json_bytes(artifact))
        value = {'op': 'update', 'target': artifact_identity(base).id, 'patch': []}
        if expected_revision is not _UNSPECIFIED:
            value['expected_revision'] = expected_revision
        if expected_sha256 is not _UNSPECIFIED:
            value['expected_sha256'] = expected_sha256
        ChangeOperation(value)  # Never infer a missing guard from the model.
        value['patch'] = (JsonPatch(patch) if options is _UNSPECIFIED
                          else compile_field_patch(base, options)).data
        return ChangeOperation(value)
    except ChangePlanError:
        raise
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error


def read_artifact_update_input(artifact, *, input, cwd=None, stdin=None,
        expected_revision=_UNSPECIFIED, expected_sha256=_UNSPECIFIED):
    """Read one explicit RFC-6902 array from a stable file or binary stdin '-'."""
    guards = dict(expected_revision=expected_revision, expected_sha256=expected_sha256)
    normalize_artifact_update_input(artifact, patch=[], **guards)
    try:
        patch = JsonPatch.from_bytes(_read_input(input, cwd, stdin))
        return normalize_artifact_update_input(artifact, patch=patch.data, **guards)
    except ChangePlanError:
        raise
    except SafetyViolation as error:
        raise AuthoringError('unsafe_authoring_input', exit_code=7) from error
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    except OSError as error:
        raise AuthoringError('authoring_input_io', exit_code=5) from error


def _result(operation, completion, *, replayed=False):
    return {'format_version': '1.0.0', 'command_id': 'artifact.update',
        'artifact_id': operation.data['target'], 'no_change': completion is None,
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


def update_artifact(model, operation, *, actor, planned_at, change_plan_id,
        transaction_id, authority, request_id=None, gates=(), strict=False, package_files=()):
    """Publish one update after complete native target validation and live checks.

    Missing semantic gates fail closed. A no-op is freshly checked under the
    native lock and authority but creates no journal, receipt or artifact bytes.
    Publication failures retain native recovery state and are never retried here.
    A replay returns historical completion, not a newly verified current target.
    """
    if (type(model) is not TargetModel or type(operation) is not ChangeOperation
            or type(authority) is not PublicationAuthority):
        raise AuthoringError('typed_update_inputs_required')
    operation = ChangeOperation(operation.data)
    if operation.op != 'update':
        raise AuthoringError('update_operation_required', pointer='/op')
    if type(gates) not in (list, tuple) or type(strict) is not bool:
        raise AuthoringError('explicit_update_options_required')
    if type(change_plan_id) is not str or not change_plan_id.strip() or '\0' in change_plan_id:
        raise AuthoringError('change_plan_identity_required')
    _transaction(transaction_id)
    request = prepare_authoring_request(command_id='artifact update', actor=actor,
        operations=[operation.data], request_id=request_id)
    actor, request_id = request.data['actor'], request.data['request_id']
    try:
        UtcTimestamp(planned_at)
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    source = ProjectSource(model.binding.source_root, expected_project_id=model.binding.project_id)
    if source.boundary._root_identity != model.binding.root_identity:
        raise AuthoringError('update_project_changed', exit_code=6)
    replay = _replay(source, request, operation)
    if replay is not None:
        return replay
    model = model.snapshot()
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
