"""Native relation authoring against explicit complete project inputs.

The host supplies model/history inventories, actor, time, IDs and authority.
This embedding service does not discover a model or register a CLI. Relation
operations remain typed operations of the common planner, never array patches.
"""
from ..changes import (AuthoringError, ChangeOperation, ChangePlanError, TargetModel,
    TargetPolicy, PublicationAuthority, prepare_authoring_request,
    prepare_change_target, prepare_publication_check, project_lock,
    begin_building_journal, stage_building_journal, publish_prepared_journal,
    read_committing_journal, finalize_committing_journal, cleanup_completed_transaction,
    read_transaction_completion, resolve_normative_request)
from ..changes._common import _reference
from ..changes._journal_codec import _transaction
from ..changes._lock_files import LockFiles
from ..changes._publication_observation import _root
from ..changes.receipt_read import _read_confirmed_request, _CompletionProof
from ..graph.relation_types import require_relation_type
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.relation_identity import (RelationInventory, allocate_relation_identity,
    relation_identity)
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource

_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


def add_relation(model, source_id, relation_type, target_id, *, inventory,
                 rationale=None, position=None, **options):
    """Allocate and publish one relation under the native writer lock.

    The explicit inventory includes current, archived and reserved relation IDs.
    Retrying with the same Request-ID reconstructs the original operation from
    its verified committed proof before any new allocation or publication.
    """
    try:
        _reference(source_id, '/source')
        _reference(target_id, '/target')
        require_relation_type(relation_type)
        fields = {'type': relation_type, 'target': target_id,
                  'external_identities': [], 'extensions': {}}
        if rationale is not None:
            fields['rationale'] = rationale
        if position is not None:
            fields['position'] = position
        intent = parse_json_object(canonical_json_bytes({'source': source_id, 'fields': fields}))
    except ChangePlanError:
        raise
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    return _execute(model, 'relation add', intent, inventory=inventory, **options)


def remove_relation(model, source_id, relation_id, *, expected_sha256, reason, **options):
    """Remove exactly one relation, retaining its original explicit hash on retry.

    The hash binds the complete relation value, not the source artifact. The
    original ID, hash and reason must be retained after successful removal.
    """
    operation = ChangeOperation({'op': 'relation_remove', 'source': source_id,
        'relation_id': relation_id, 'expected_sha256': expected_sha256, 'reason': reason})
    return _execute(model, 'relation remove', operation, **options)


def _addition(intent, identity, actor, planned_at):
    return ChangeOperation({'op': 'relation_add', 'source': intent['source'],
        'relation': {**intent['fields'], **identity.as_fields(),
                     'created_at': planned_at, 'created_by': actor}})


def _result(operation, completion, *, replayed=False):
    value = operation.data
    return {'format_version': '1.0.0', 'command_id': value['op'].replace('_', '.'),
        'source_id': value['source'], 'relation_id': (value['relation']['relation_id']
            if value['op'] == 'relation_add' else value['relation_id']),
        'write_state': 'committed', 'replayed': replayed, 'completion': completion.data}


def _replay(source, command, intent, actor, request_id):
    if request_id is None:
        return None
    receipt = _read_confirmed_request(source, request_id)
    if receipt is None:
        return None
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, receipt.data['transaction_id'])
        value = proof.journal.data
        if value['receipts']['request'] != {'path': receipt.path, 'sha256': receipt.sha256}:
            raise AuthoringError('request_receipt_changed', exit_code=6)
        operations = value['authoring_binding']['operations']
        if len(operations) != 1 or operations[0]['op'] != command.replace(' ', '_'):
            raise AuthoringError('request_operations_conflict', pointer='/request_id', exit_code=6)
        operation = (_addition(intent, relation_identity(operations[0]['relation']),
            value['actor'], value['planned_at']) if command == 'relation add' else intent)
        request = prepare_authoring_request(command_id=command, actor=actor,
            operations=[operation.data], request_id=request_id)
        resolution = resolve_normative_request(source, request).data
        if resolution['action'] != 'replay' or resolution['receipt'] != {
                'path': receipt.path, 'sha256': receipt.sha256}:
            raise AuthoringError('request_receipt_changed', exit_code=6)
        proof.check()
        completion = read_transaction_completion(source, receipt.data['transaction_id'])
        proof.check()
        return _result(operation, completion, replayed=True)


def _execute(model, command, intent, *, inventory=None, actor, planned_at, change_plan_id,
             transaction_id, authority, request_id=None, gates=(), strict=False, package_files=()):
    """Use the native full-target and publication protocol for both operations.

    Missing lifecycle or specialist services fail closed. This adapter does not
    attest historical completeness, retry publication or roll back a partial
    write; native journals and actual write-state diagnostics remain intact.
    """
    adding = command == 'relation add'
    if (type(model) is not TargetModel or type(authority) is not PublicationAuthority
            or (adding and type(inventory) is not RelationInventory)):
        raise AuthoringError('typed_relation_inputs_required')
    if type(gates) not in (list, tuple) or type(strict) is not bool:
        raise AuthoringError('explicit_relation_options_required')
    if type(change_plan_id) is not str or not change_plan_id.strip() or '\0' in change_plan_id:
        raise AuthoringError('change_plan_identity_required')
    _transaction(transaction_id)
    request = prepare_authoring_request(command_id=command, actor=actor,
        operations=[] if adding else [intent.data], request_id=request_id)
    actor, request_id = request.data['actor'], request.data['request_id']
    try:
        UtcTimestamp(planned_at)
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    source = ProjectSource(model.binding.source_root, expected_project_id=model.binding.project_id)
    if source.boundary._root_identity != model.binding.root_identity:
        raise AuthoringError('relation_project_changed', exit_code=6)
    replay = _replay(source, command, intent, actor, request_id)
    if replay is not None:
        return replay
    model = model.snapshot()
    if adding and (inventory.current_ids != {r['relation_id'] for a in model.artifacts
            for r in a['relations']} or not set(model.reserved_relation_ids) <=
            inventory.archived_ids | inventory.reserved_ids):
        raise AuthoringError('relation_identity_inventory_mismatch', exit_code=6)
    policy = TargetPolicy(command.replace(' ', '.'), '1', ())
    with project_lock(source.boundary.root, kind='writer', command='change apply',
            project_id=model.configuration.project_id, request_id=request_id,
            transaction_id=transaction_id) as held:
        replay = _replay(source, command, intent, actor, request_id)
        if replay is not None:
            return replay
        current = _root(model)
        held.require_publication(current, command='change apply', request_id=request_id,
                                 transaction_id=transaction_id)
        if adding:
            try:
                identity = allocate_relation_identity(inventory).identity
            except ModelError as error:
                raise AuthoringError(error.reason, pointer=error.pointer, exit_code=5) from error
            operation = _addition(intent, identity, actor, planned_at)
        else:
            operation = intent
        checked = prepare_change_target(model, [operation.data], change_plan_id=change_plan_id,
            request_id=request_id, actor=actor, planned_at=planned_at, scope_descriptor=_SCOPE,
            metadata_policy_version='change-metadata-v1', policy=policy, gates=gates, strict=strict)
        checked.require_valid()
        preflight = prepare_publication_check(checked.plan, model, policy=policy,
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
        return _result(operation, completion)
