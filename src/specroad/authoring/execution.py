"""Execute an explicit authoring plan through native publication and replay.

No allocation or implicit replanning. Supplied gates are trusted host services;
the stored command and plan cannot register executable code or grant authority.
"""
from ..changes import (ChangePlan, TargetModel, PublicationAuthority,
    prepare_authoring_request, assess_change_target, prepare_publication_check,
    recheck_publication, project_lock, begin_building_journal, stage_building_journal,
    publish_prepared_journal, read_committing_journal, finalize_committing_journal,
    cleanup_completed_transaction, read_transaction_completion, resolve_normative_request)
from ..changes._journal_codec import _transaction
from ..changes._lock_files import LockFiles
from ..changes._publication_observation import _root
from ..changes.receipt_read import _CompletionProof
from ..changes.request_ids import AuthoringError
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.project import ProjectSource
from .plans import _operations, _execution_inputs, _audit, _OPERATIONS


def _result(audit, completion, *, replayed=False):
    return {'format_version': 'authoring-execution-v1',
        'command_id': audit['command_id'], 'dry_run': False,
        'exit_code': 0, 'write_state': audit['write_state'],
        'replayed': replayed, 'no_change': completion is None,
        'plan_sha256': audit['plan_sha256'],
        'target_model_root_sha256': audit['target_model_root_sha256'],
        'audit': audit, 'completion': None if completion is None else completion.data,
        'approval_granted': False}


def _replay(source, request, command_id):
    resolution = resolve_normative_request(source, request).data
    if resolution['action'] != 'replay':
        return None
    transaction = resolution['original_request']['transaction_id']
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, transaction)
        value = proof.journal.data
        if value['receipts']['request'] != resolution['receipt']:
            raise AuthoringError('request_receipt_changed', exit_code=6)
        # Report historical audit facts, never the retry's actor/time/new plan.
        audit = {'format_version': 'authoring-audit-v1', 'command_id': command_id,
            'command_class': 'normative_write', 'dry_run': False,
            'write_state': 'committed', 'replayed': True,
            **{key: value[key] for key in ('change_plan_id', 'plan_sha256', 'request_id',
                'actor', 'planned_at', 'base_model_root_sha256', 'target_model_root_sha256')},
            'operations': value['authoring_binding']['operations'],
            'created_ids': resolution['created_ids'], 'approval_granted': False}
        completion = read_transaction_completion(source, transaction)
        proof.check()
        return _result(audit, completion, replayed=True)


def apply_authoring_plan(plan, model, *, command_id, transaction_id, authority,
        gates=(), strict=False, package_files=()):
    """Recheck and publish exactly the saved plan under the native writer lock.

    A confirmed retry is resolved before current-target evaluation. A no-op
    still requires fresh native authorization but creates no receipt or journal.
    Failures retain the existing protocol's real recovery state and exceptions.
    """
    if (type(plan) is not ChangePlan or type(model) is not TargetModel
            or type(authority) is not PublicationAuthority):
        raise AuthoringError('typed_authoring_execution_inputs_required')
    if type(strict) is not bool or type(gates) not in (list, tuple):
        raise AuthoringError('explicit_authoring_execution_options_required')
    # Own the host's gate selection before any external source/receipt read.
    # A callback changing its original list cannot remove a required refusal.
    gates = tuple(gates)
    plan = ChangePlan(plan.source_bytes)
    value = plan.data
    operations = _operations(command_id, value['operations'])
    request = prepare_authoring_request(command_id=command_id.replace('.', ' '),
        operations=operations, actor=value['actor'], request_id=value['request_id'])
    _transaction(transaction_id)
    source = ProjectSource(model.binding.source_root, expected_project_id=model.binding.project_id)
    if source.boundary._root_identity != model.binding.root_identity:
        raise AuthoringError('authoring_project_changed', exit_code=6)
    replay = _replay(source, request, command_id)
    if replay is not None:
        return replay
    model = model.snapshot()
    _, policy, gates = _execution_inputs(model, command_id, operations,
        value['actor'], value['planned_at'], gates)
    with project_lock(source.boundary.root, kind='writer', command='change apply',
            project_id=model.configuration.project_id, request_id=value['request_id'],
            transaction_id=transaction_id) as held:
        replay = _replay(source, request, command_id)
        if replay is not None:
            return replay
        current = _root(model)
        held.require_publication(current, command='change apply', request_id=value['request_id'],
                                 transaction_id=transaction_id)
        checked = assess_change_target(plan, model, policy=policy, gates=gates, strict=strict)
        checked.require_valid()
        preflight = prepare_publication_check(plan, model, policy=policy,
            gates=gates, strict=strict, package_files=package_files)
        if not preflight.request.documents:
            recheck_publication(preflight, preflight.request, held_lock=held,
                transaction_id=transaction_id, authority=authority, gates=gates)
            return _result(_audit(plan, command_id, dry_run=False, write_state='not_committed'), None)
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
        return _result(_audit(plan, command_id, dry_run=False, write_state='committed'), completion)


def execute_authoring_plan(plan, model, *, command_id, transaction_id, authority,
        gates=(), strict=False, package_files=()):
    """Return a machine-readable success or native refusal without hiding state.

    The raising API remains available. Expected model/security/I/O failures get
    an audit of the attempted plan; unexpected programming failures still raise.
    Missing publication evidence is unknown, never an invented successful
    rollback or a safe-retry promise. This adapter emits no output or files.
    """
    owned = None
    try:
        if type(plan) is ChangePlan:
            owned = ChangePlan(plan.source_bytes)
        result = apply_authoring_plan(owned if owned is not None else plan, model,
            command_id=command_id, transaction_id=transaction_id, authority=authority,
            gates=gates, strict=strict, package_files=package_files)
        return {**result, 'status': 'success'}
    except (ModelError, SafetyViolation, OSError) as error:
        if isinstance(error, ModelError):
            diagnostic = error.diagnostic()
            exit_code = getattr(error, 'exit_code', 3)
        elif isinstance(error, SafetyViolation):
            diagnostic = {'reason': 'unsafe_authoring_execution'}
            exit_code = 7
        else:
            # Do not expose OS messages containing submitted paths or data.
            diagnostic = {'reason': 'authoring_execution_io_failure'}
            exit_code = 5
        state = diagnostic.get('write_state', 'unknown')
        if state not in ('not_committed', 'unknown', 'committed'):
            state = 'unknown'
        command = command_id if type(command_id) is str and command_id in _OPERATIONS else None
        audit = ({} if owned is None else
            _audit(owned, command, dry_run=False, write_state=state))
        planned_ids = audit.pop('created_ids', None)
        # These roots describe the plan, not observed publication on a failure.
        expected_root = audit.pop('target_model_root_sha256', None)
        audit = {**audit, 'format_version': 'authoring-audit-v1',
            'command_class': 'normative_write', 'command_id': command,
            'audit_scope': 'failed_plan_attempt', 'dry_run': False,
            'write_state': state, 'replayed': False, 'outcome': 'failed',
            'planned_created_ids': planned_ids, 'expected_model_root_sha256': expected_root,
            'plan_integrity_checked': owned is not None, 'exit_code': exit_code,
            'diagnostic': diagnostic, 'approval_granted': False}
        return {'format_version': 'authoring-execution-v1', 'command_id': command,
            'dry_run': False, 'status': 'failed', 'exit_code': exit_code,
            'write_state': state, 'replayed': False, 'no_change': None,
            'plan_sha256': None if owned is None else owned.sha256,
            'target_model_root_sha256': None, 'audit': audit, 'completion': None,
            'diagnostics': [diagnostic], 'current_target_verified': False,
            'recovery_required': diagnostic.get('recovery_required', state == 'unknown'),
            'retry_safe': False, 'automatic_retry': False, 'automatic_rollback': False,
            'approval_granted': False}
