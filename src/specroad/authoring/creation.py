"""Native draft creation against explicitly supplied, trusted project inputs.

This embedding service is not a registered CLI or a historical-ID discovery
service. The host supplies a complete model/inventory and publication authority.
Actual artifact allocation happens under the native writer lock. The common
target gates, journal, receipt and cleanup primitives own the write protocol.
"""
from ..changes import (AuthoringError, TargetModel, TargetPolicy, PublicationAuthority,
    prepare_authoring_request, prepare_change_target, prepare_publication_check,
    project_lock, begin_building_journal, stage_building_journal,
    publish_prepared_journal, finalize_committing_journal, cleanup_completed_transaction,
    read_transaction_completion, read_committing_journal, resolve_normative_request)
from ..changes._journal_codec import _transaction
from ..changes._lock_files import LockFiles
from ..changes._publication_observation import _root
from ..changes.receipt_read import _read_confirmed_request, _CompletionProof
from ..model.audit import new_artifact_audit, actor as parse_actor
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..model.draft_factory import prepare_draft_fields
from ..model.domain_schemas import DOMAIN_TYPES
from ..model.errors import ModelError
from ..model.identities import IdentityInventory, allocate_artifact_identity
from ..model.identity_values import artifact_identity
from ..model.paths import artifact_path
from ..storage.domain_artifact import DomainArtifact
from ..storage.project import ProjectSource
from ..storage.record_artifact import RecordArtifact
from .inputs import ArtifactCreateInput, normalize_artifact_create_input

_POLICY = TargetPolicy('artifact.create', '1', ())
_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


def _draft(prepared, identity, actor, planned_at, configuration):
    kind = prepared.data['artifact_type']
    actor, planned_at = parse_actor(actor), UtcTimestamp(planned_at)
    value = prepare_draft_fields(kind, prepared.fields, identity=identity, actor=actor,
        planned_at=planned_at, configuration=configuration)
    path = artifact_path(kind, identity.id, configuration.id_prefix)
    reader = DomainArtifact if kind in DOMAIN_TYPES else RecordArtifact
    reader(canonical_json_bytes(value), expected_type=kind, path=path)
    return value


def _result(artifact, completion, *, replayed):
    identity = artifact_identity(artifact)
    return {'format_version': '1.0.0', 'command_id': 'artifact.create',
        'artifact_id': identity.id, 'artifact_type': identity.artifact_type,
        'path': artifact_path(identity.artifact_type, identity.id, identity.id_prefix),
        'revision': artifact['revision'], 'maturity': artifact['maturity'],
        'write_state': 'committed', 'replayed': replayed, 'completion': completion.data}


def _replay(source, prepared, actor, request_id):
    if request_id is None:
        return None
    receipt = _read_confirmed_request(source, request_id)
    if receipt is None:
        return None
    # The request hint alone cannot provide an old artifact or write authority.
    # Recheck its full native committed proof before using the original operation.
    transaction = receipt.data['transaction_id']
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, transaction)
        value = proof.journal.data
        if value['receipts']['request'] != {'path': receipt.path, 'sha256': receipt.sha256}:
            raise AuthoringError('request_receipt_changed', exit_code=6)
        operations = value['authoring_binding']['operations']
        if (len(operations) != 1 or operations[0]['op'] != 'create'
                or operations[0]['artifact']['artifact_type'] != prepared.data['artifact_type']):
            raise AuthoringError('request_operations_conflict', pointer='/request_id', exit_code=6)
        original = operations[0]['artifact']
        candidate = _draft(prepared, artifact_identity(original), value['actor'],
                           value['planned_at'], source.configuration)
        request = prepare_authoring_request(command_id='artifact create', actor=actor,
            operations=[{'op': 'create', 'artifact': candidate, 'result_id': candidate['id']}],
            request_id=request_id)
        resolution = resolve_normative_request(source, request).data
        if resolution['action'] != 'replay' or resolution['receipt'] != {
                'path': receipt.path, 'sha256': receipt.sha256}:
            raise AuthoringError('request_receipt_changed', exit_code=6)
        proof.check()
        completion = read_transaction_completion(source, transaction)
        proof.check()
        return _result(original, completion, replayed=True)


def create_artifact(model, prepared, *, inventory, actor, planned_at, change_plan_id,
                    transaction_id, authority, request_id=None, gates=(), strict=False,
                    package_files=()):
    """Create one regular draft using the actual native transaction protocol.

    The embedding host must supply the complete current model and historical
    identity inventory. Matching values do not attest historical completeness or
    authenticate an actor. Missing full-target gates fail closed. Failures retain
    existing native recovery evidence; this adapter never retries publication.
    Explicit plan/transaction IDs and time come from the trusted host. Only the
    artifact ID is allocated here, while the real exclusive writer lock is held.
    """
    if (type(model) is not TargetModel or type(prepared) is not ArtifactCreateInput
            or type(inventory) is not IdentityInventory or type(authority) is not PublicationAuthority):
        raise AuthoringError('typed_creation_inputs_required')
    if type(gates) not in (list, tuple) or type(strict) is not bool:
        raise AuthoringError('explicit_creation_options_required')
    if type(change_plan_id) is not str or not change_plan_id.strip() or '\0' in change_plan_id:
        raise AuthoringError('change_plan_identity_required')
    _transaction(transaction_id)
    request = prepare_authoring_request(command_id='artifact create', actor=actor,
        operations=[], request_id=request_id)
    actor, request_id = request.data['actor'], request.data['request_id']
    try:
        data = prepared.data
        owned = normalize_artifact_create_input(data['artifact_type'], data['fields'])
        if owned.source_bytes != prepared.source_bytes:
            raise AuthoringError('creation_input_binding_changed', exit_code=3)
        new_artifact_audit(actor=parse_actor(actor), planned_at=UtcTimestamp(planned_at))
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    source = ProjectSource(model.binding.source_root, expected_project_id=model.binding.project_id)
    if source.boundary._root_identity != model.binding.root_identity:
        raise AuthoringError('creation_project_changed', exit_code=6)
    replay = _replay(source, owned, actor, request_id)
    if replay is not None:
        return replay
    model = model.snapshot()
    if (inventory.id_prefix != model.configuration.id_prefix
            or inventory.current_ids != {a['id'] for a in model.artifacts}
            or not set(model.reserved_artifact_ids) <= inventory.reserved_ids | inventory.archived_ids):
        raise AuthoringError('creation_identity_inventory_mismatch', exit_code=6)
    with project_lock(source.boundary.root, kind='writer', command='change apply',
            project_id=model.configuration.project_id, request_id=request_id,
            transaction_id=transaction_id) as held:
        replay = _replay(source, owned, actor, request_id)
        if replay is not None:
            return replay
        current = _root(model)
        held.require_publication(current, command='change apply', request_id=request_id,
                                 transaction_id=transaction_id)
        try:
            identity = allocate_artifact_identity(owned.data['artifact_type'], inventory).identity
        except ModelError as error:
            # Inputs and inventory are already checked. Failure of the native
            # entropy provider is operational, before any journal/publication.
            raise AuthoringError(error.reason, pointer=error.pointer, exit_code=5) from error
        try:
            artifact = _draft(owned, identity, actor, planned_at, model.configuration)
        except ModelError as error:
            raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
        operation = {'op': 'create', 'artifact': artifact, 'result_id': identity.id}
        checked = prepare_change_target(model, [operation], change_plan_id=change_plan_id,
            request_id=request_id, actor=actor, planned_at=planned_at, scope_descriptor=_SCOPE,
            metadata_policy_version='change-metadata-v1', policy=_POLICY, gates=gates, strict=strict)
        checked.require_valid()
        preflight = prepare_publication_check(checked.plan, model, policy=_POLICY,
            gates=gates, strict=strict, package_files=package_files)
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
        return _result(artifact, completion, replayed=False)
