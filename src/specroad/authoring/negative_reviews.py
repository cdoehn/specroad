"""Human review outcomes and coupled withdrawals through native publication.

The host supplies complete project inputs, authentic history and authority.
Computed Requirement withdrawals and subsequent confirmations preserve all
unrelated write gates. The first-confirmation API retains its earlier scope.
"""
from ..changes import (AuthoringError, ChangeOperation, TargetModel, TargetPolicy,
    PublicationAuthority, prepare_authoring_request,     prepare_publication_check, project_lock, begin_building_journal,
    stage_building_journal, publish_prepared_journal, read_committing_journal,
    finalize_committing_journal, cleanup_completed_transaction,
    read_transaction_completion, resolve_normative_request)
from ..changes._common import _text, _reference
from ..changes._fold_inputs import _inventory, _relation_inventory, _check_expected
from .plans import prepare_authoring_target as prepare_change_target
from ..changes._journal_codec import _transaction
from ..changes._lock_files import LockFiles
from ..changes._publication_observation import _root
from ..changes._schema_fields import expected
from ..changes.receipt_read import _read_confirmed_request, _CompletionProof
from ..changes.reviews import review_context, review_time, prepare_review_record
from ..changes.negative_reviews import (prepare_negative_review_record,
    required_review_withdrawals, prepare_review_outcome_gates)
from ..diagnostics import Diagnostic, code_metadata
from ..model._schema import validate_builtin
from ..model.audit_values import UtcTimestamp
from ..model.errors import ModelError
from ..model.identities import IdentityInventory, allocate_artifact_identity
from ..model.paths import artifact_path
from ..model.relation_values import RelationIdentity
from ..storage.project import ProjectSource

_UNSPECIFIED = object()
_POLICY = TargetPolicy('relation.review', 'review-outcome-v1', ('extension:review-withdrawal',))
_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


def _intent(source_id, relation_id, decision, reason, comment, guards):
    _reference(source_id, '/source')
    RelationIdentity(relation_id, 'random128-v1')
    validate_builtin(guards, expected({}, []))
    if type(decision) is not str or decision not in ('confirmed', 'rejected'):
        raise AuthoringError('review_decision_invalid', exit_code=3)
    _text(reason, '/reason')
    value = {'source': source_id, 'relation_id': relation_id, 'decision': decision,
             'reason': reason, **guards}
    if comment is not None:
        _text(comment, '/comment')
        value['comment'] = comment
    return value


def _operation(intent, record, withdrawals):
    # On replay, immutable observations and original actor/time come from the
    # verified committed proof. Only the caller's explicit intent is reapplied.
    value = {k: v for k, v in record.items() if k != 'comment'}
    value.update({k: intent[k] for k in ('relation_id', 'decision', 'reason')})
    if 'comment' in intent:
        value['comment'] = intent['comment']
    return ChangeOperation({'op': 'relation_review_record', 'source': intent['source'],
        'target': record['target_id'], 'record': value, 'approval_withdrawals': withdrawals,
        **{k: intent[k] for k in ('expected_revision', 'expected_sha256') if k in intent}})


def _result(operation, completion, *, plan_sha256, target_root, replayed=False):
    record = operation.data['record']
    negative = record['decision'] == 'rejected'
    diagnostic = Diagnostic('SRV027', 'error', 'review_outcome', code_metadata('SRV027')['meaning'],
        rule_id='core:relation-review-status', artifact_id=record['source_id'],
        rationale='current_review_rejected',
        related_ids=(record['relation_id'], record['target_id'], record['id']))
    withdrawals = [{'artifact_id': item['target'], 'base_revision': item['expected_revision'],
        'target_revision': item['expected_revision'] + 1, 'from': 'approved', 'to': 'proposed',
        'relation_id': record['relation_id'], 'review_id': record['id'], 'reason': item['reason']}
        for item in operation.data['approval_withdrawals']]
    return {'format_version': '1.0.0', 'command_id': 'relation.review',
        'review_id': record['id'], 'relation_id': record['relation_id'],
        'source_id': record['source_id'], 'target_id': record['target_id'],
        'decision': record['decision'], 'review_state': record['review_state'],
        'maturity': record['maturity'], 'revision': record['revision'],
        'path': artifact_path('relation_review', record['id'], record['id'].split('-')[0]),
        'write_state': 'committed', 'replayed': replayed, 'completion': completion.data,
        'plan_sha256': plan_sha256, 'target_model_root_sha256': target_root,
        'approval_withdrawals': withdrawals, 'relation_status': 'invalid' if negative else 'current',
        'assessment_status': 'failed' if negative else 'passed',
        'assessment_scope': 'recorded_review_outcome_only',
        'diagnostics': [diagnostic.as_dict()] if negative else [], 'approval_granted': False}


def _preflight_context(model, intent):
    """Reject an inconsistent supplied graph/guard before locking or allocation.

    The immutable observation is still checked against the bound model by the
    target planner and against actual files at every publication boundary.
    This early check is neither a live snapshot nor a write capability.
    """
    state, _, _ = _inventory(model.artifacts, [*model.reserved_artifact_ids,
        *model.reservations['previously_approved_ids']])
    _relation_inventory(state, model.reserved_relation_ids)
    context = review_context(list(state.values()), intent['source'], intent['relation_id'])
    _check_expected(state[intent['source']], intent)
    return context


def _replay(source, intent, actor, request_id):
    if request_id is None:
        return None
    receipt = _read_confirmed_request(source, request_id)
    if receipt is None:
        return None
    transaction = receipt.data['transaction_id']
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, transaction)
        value = proof.journal.data
        if value['receipts']['request'] != {'path': receipt.path, 'sha256': receipt.sha256}:
            raise AuthoringError('request_receipt_changed', exit_code=6)
        operations = value['authoring_binding']['operations']
        if (len(operations) != 1 or operations[0]['op'] != 'relation_review_record'
                or 'target_id' not in operations[0]['record']
                or operations[0]['record']['decision'] not in ('confirmed', 'rejected')):
            raise AuthoringError('request_operations_conflict', pointer='/request_id', exit_code=6)
        operation = _operation(intent, operations[0]['record'], operations[0]['approval_withdrawals'])
        request = prepare_authoring_request(command_id='relation review', actor=actor,
            operations=[operation.data], request_id=request_id)
        resolution = resolve_normative_request(source, request).data
        if resolution['action'] != 'replay' or resolution['receipt'] != {
                'path': receipt.path, 'sha256': receipt.sha256}:
            raise AuthoringError('request_receipt_changed', exit_code=6)
        proof.check()
        completion = read_transaction_completion(source, transaction)
        proof.check()
        return _result(operation, completion, replayed=True, plan_sha256=value['plan_sha256'],
            target_root=value['target_model_root_sha256'])


def record_coupled_relation_review(model, source_id, relation_id, *, reason, decision,
        inventory, actor, planned_at, change_plan_id, transaction_id, authority,
        expected_revision=_UNSPECIFIED, expected_sha256=_UNSPECIFIED, comment=None,
        request_id=None, gates=(), strict=False, package_files=()):
    """Publish a review and every required supported withdrawal atomically.

    Explicit source guards, composed profile and exact saved-plan recomputation
    are mandatory. Publication is never retried; native recovery evidence stays.
    The result reports this recorded outcome, not complete CLI validation.
    """
    if (type(model) is not TargetModel or type(inventory) is not IdentityInventory
            or type(authority) is not PublicationAuthority):
        raise AuthoringError('typed_review_inputs_required')
    if type(gates) not in (list, tuple) or type(strict) is not bool:
        raise AuthoringError('explicit_review_options_required')
    gates = tuple(gates)
    _text(change_plan_id, '/change_plan_id')
    _transaction(transaction_id)
    request = prepare_authoring_request(command_id='relation review', actor=actor,
        operations=[], request_id=request_id)
    actor, request_id = request.data['actor'], request.data['request_id']
    try:
        guards = {}
        if expected_revision is not _UNSPECIFIED: guards['expected_revision'] = expected_revision
        if expected_sha256 is not _UNSPECIFIED: guards['expected_sha256'] = expected_sha256
        intent = _intent(source_id, relation_id, decision, reason, comment, guards)
        UtcTimestamp(planned_at)
        inventory = IdentityInventory(inventory.id_prefix, inventory.current_ids,
            inventory.archived_ids, inventory.reserved_ids)
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    source = ProjectSource(model.binding.source_root, expected_project_id=model.binding.project_id)
    if source.boundary._root_identity != model.binding.root_identity:
        raise AuthoringError('review_project_changed', exit_code=6)
    replay = _replay(source, intent, actor, request_id)
    if replay is not None:
        return replay
    model = model.snapshot()
    if (inventory.id_prefix != model.configuration.id_prefix
            or inventory.current_ids != {a['id'] for a in model.artifacts}
            or not set(model.reserved_artifact_ids) <= inventory.reserved_ids | inventory.archived_ids
            or not set(model.reservations['previously_approved_ids']) <=
                inventory.current_ids | inventory.archived_ids | inventory.reserved_ids):
        raise AuthoringError('review_identity_inventory_mismatch', exit_code=6)
    context = _preflight_context(model, intent)
    withdrawals = (required_review_withdrawals(model.artifacts, source_id, relation_id, profile=model.profile)
                   if decision == 'rejected' else [])
    planned_at = review_time(model.artifacts, context, planned_at)
    with project_lock(source.boundary.root, kind='writer', command='change apply',
            project_id=model.configuration.project_id, request_id=request_id,
            transaction_id=transaction_id) as held:
        replay = _replay(source, intent, actor, request_id)
        if replay is not None:
            return replay
        current = _root(model)
        held.require_publication(current, command='change apply', request_id=request_id,
                                 transaction_id=transaction_id)
        try:
            identity = allocate_artifact_identity('relation_review', inventory).identity
        except ModelError as error:
            raise AuthoringError(error.reason, pointer=error.pointer, exit_code=5) from error
        prepare = prepare_negative_review_record if decision == 'rejected' else prepare_review_record
        record = prepare(context, identity, actor=actor, planned_at=planned_at,
            reason=reason, comment=comment, **({'decision': decision} if decision == 'confirmed' else {}))
        operation = _operation(intent, record, withdrawals)
        gates += prepare_review_outcome_gates(model, operation, actor=actor, planned_at=planned_at)
        checked = prepare_change_target(model, [operation.data], change_plan_id=change_plan_id,
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
        return _result(operation, completion, plan_sha256=checked.plan.sha256,
            target_root=checked.data['binding']['target_model_root'])


def record_negative_relation_review(model, source_id, relation_id, *, decision='rejected', **options):
    """The original API remains explicitly restricted to a negative decision."""
    if type(decision) is not str or decision != 'rejected':
        raise AuthoringError('negative_review_decision_required', exit_code=3)
    return record_coupled_relation_review(model, source_id, relation_id, decision=decision, **options)
