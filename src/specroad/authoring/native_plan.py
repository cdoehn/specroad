"""Native Markdown authoring, one source inventory and the common writer.

Actor declarations are audit data. Actual writes require the host's typed
PublicationAuthority; passively stored options cannot manufacture one.
"""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.identities import allocate_artifact_identity
from ..model.relation_identity import allocate_relation_identity
from ..changes import (PublicationAuthority, prepare_authoring_request, project_lock,
    prepare_publication_check, recheck_publication)
from ..changes.target_model import _default_scope
from ..changes.plan_source_operation import prepare_operation, preconditions
from ..changes.plan_candidates import prepare as candidates
from ..changes.guarded_write import publish_guarded_change
from ..changes.target import prepare_change_target
from ..changes.request_ids import AuthoringError
from ..validation import ModelDocument
from .project_sources import AuthoringSources
from .native_qualification import publication_gates
from .plans import _execution_policy, _audit
from .execution import _result
from .plan_operations import commit_message


def _prepared(sources, intent, actor, time):
    intent = deepcopy(intent)
    command = intent['command_id']
    if set(intent) & {'new_id', 'parent_relation_id'}:
        raise AuthoringError('plan_creation_ids_are_native', exit_code=2)
    if command in ('plan.create', 'plan.entry.add'):
        kind = 'implementation_plan' if command == 'plan.create' else 'plan_entry'
        intent['new_id'] = allocate_artifact_identity(kind, sources.identities).identity.id
        if command == 'plan.entry.add':
            intent['parent_relation_id'] = allocate_relation_identity(sources.relations).identity.id
    op = prepare_operation(sources.model, intent, actor=actor, planned_at=time)
    folded = candidates(sources.model, [op], metadata_policy_version='change-metadata-v1',
                        actor=actor, planned_at=time, preconditions=preconditions(op))
    _check_command(sources.model, folded.target_model, op)
    return op, folded.target_model


from ._plan_checks import _check_command


def _replay(root, intent, actor, request_id, *, as_proposal=False, proposal_fields=None, expected_model_root=None):
    if request_id is None:
        return None
    from ..storage.project import ProjectSource
    from ..changes.receipt_read import _read_confirmed_request, _CompletionProof
    from ..changes._lock_files import LockFiles
    from .execution import _replay as saved_replay
    source = ProjectSource(root)
    receipt = _read_confirmed_request(source, request_id)
    if receipt is None:
        return None
    with LockFiles(root) as files:
        proof = _CompletionProof(files, source, receipt.data['transaction_id'])
        if expected_model_root is not None and proof.journal.data['base_model_root_sha256'] != expected_model_root:
            raise AuthoringError('request_base_root_conflict', exit_code=6)
        ops = proof.journal.data['authoring_binding']['operations']
        record = None
        original_ops = ops
        if as_proposal and len(ops) == 1 and ops[0]['op'] == 'proposal_create':
            record = ops[0]['record']
            from ..changes import ChangePlan
            inner = ChangePlan(canonical_json_bytes(record['change_plan']))
            from .native_proposal import proposal_metadata
            proposal_metadata(proposal_fields, None, inner, recorded=record)
            ops = inner.data['operations']
        if (as_proposal and record is None) or len(ops) != 1 or ops[0]['op'] != 'plan_edit':
            raise AuthoringError('request_operations_conflict', exit_code=6)
        recorded = {k: v for k, v in ops[0]['intent'].items() if k not in ('new_id', 'parent_relation_id')}
        if canonical_json_bytes(recorded) != canonical_json_bytes(intent):
            raise AuthoringError('request_operations_conflict', exit_code=6)
        request = prepare_authoring_request(command_id='proposal create' if as_proposal else intent['command_id'].replace('.', ' '),
            actor=actor, operations=original_ops, request_id=request_id)
        proof.check()
    result = saved_replay(source, request, 'proposal.create' if as_proposal else intent['command_id'])
    return {**result, 'proposal': record, 'publication_kind': 'proposal_draft',
        'review_validity': {'current_approval': False, 'human_decision_required': True}} if as_proposal else result


from .native_attempt import audited


@audited
def author_plan(root, intent, *, actor, request_id=None, dry_run=False,
               expected_model_root=None, authority=None, services=None,
               as_proposal=False, proposal_fields=None, force=False, force_reason=None, _attempt=None):
    """Allocate, compile, qualify and publish; a dry run leaves every file alone."""
    from ..force import ForceRequest
    requested = ForceRequest(force, force_reason)
    if requested.requested:
        from .force_native import author_force
        return author_force(root, intent, actor=actor, request_id=request_id, dry_run=dry_run,
            expected_model_root=expected_model_root, authority=authority, services=services,
            as_proposal=as_proposal, proposal_fields=proposal_fields, force=True,
            force_reason=force_reason, _attempt=_attempt)
    if type(intent) is not dict or type(dry_run) is not bool or type(as_proposal) is not bool:
        raise AuthoringError('plan_authoring_inputs_required')
    intent = deepcopy(intent)
    command = intent.get('command_id')
    from ..model.plan_command_ids import COMMANDS
    if type(command) is not str or command not in COMMANDS:
        raise AuthoringError('plan_authoring_command_required')
    request = prepare_authoring_request(command_id=command.replace('.', ' '), actor=actor,
        operations=[], request_id=request_id, dry_run=dry_run, as_proposal=as_proposal)
    actor, request_id = request.data['actor'], request.data['request_id']
    if not dry_run and type(authority) is not PublicationAuthority:
        raise AuthoringError('authoring_host_authority_required', exit_code=7)
    if not as_proposal and proposal_fields is not None:
        raise AuthoringError('proposal_option_requires_redirect')
    if not dry_run:
        replay = _replay(root, intent, actor, request_id, as_proposal=as_proposal, proposal_fields=proposal_fields, expected_model_root=expected_model_root)
        if replay is not None:
            return replay
    sources = AuthoringSources(root)
    model = sources.model
    base = model.manifest(model.artifacts, _default_scope()).sha256
    if expected_model_root is not None and base != expected_model_root:
        raise AuthoringError('target_base_root_mismatch', exit_code=6)
    from ..qualification.project import validate_project
    validate_project({**sources.snapshot.raw, **sources.receipts.payloads}, services=services)
    transaction_id = 'plan-' + str(uuid4())
    time = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    plan_id = 'plan-' + str(uuid4())
    policy = _execution_policy(command)
    def compile_request():
        sources.verify_current()
        op, target = _prepared(sources, intent, actor, time)
        gates = publication_gates(sources, target, services=services,
            transaction_id=None if dry_run else transaction_id,
            request_id=None if dry_run else request_id)
        checked = prepare_change_target(model, [op], change_plan_id=plan_id,
            request_id=request_id, actor=actor, planned_at=time, scope_descriptor=_default_scope(),
            metadata_policy_version='change-metadata-v1', policy=policy, gates=gates,
            preconditions=preconditions(op))
        _attempt['plan'] = checked.plan
        checked.require_valid()
        sources.verify_current()
        return checked, gates, target
    if dry_run:
        checked, gates, target = compile_request()
        from ..changes.execution_values import ChangeExecutionResult
        result = ChangeExecutionResult._create(checked, dry_run=True, fail_on_change=False).data
        if as_proposal:
            from .proposals import prepare_authoring_proposal
            proposal = prepare_authoring_proposal(checked.plan, model, command_id=command,
                proposal_fields=__import__('specroad.authoring.native_proposal', fromlist=['proposal_metadata']).proposal_metadata(
                    proposal_fields, sources, checked.plan), gates=gates)
            result = {**result, 'proposal': proposal.data}
        sources.verify_current()
        return {**result, 'command_id': command, 'audit': _audit(checked.plan, command,
            dry_run=True, write_state='not_committed'), 'commit_messages': _messages(target, checked.plan)}
    if as_proposal:
        # The existing Proposal publisher owns its own exclusive writer lock.
        # Rechecks bind all sources again before that independent publication.
        with project_lock(root, kind='writer', command='change apply', project_id=model.binding.project_id,
                          request_id=request_id, transaction_id=transaction_id):
            replay = _replay(root,intent,actor,request_id,as_proposal=True,proposal_fields=proposal_fields,expected_model_root=expected_model_root)
            if replay is not None:
                return replay
            checked, gates, target = compile_request()
            from .native_proposal import proposal_metadata
            proposal_fields = proposal_metadata(proposal_fields, sources, checked.plan)
        from .proposals import publish_authoring_proposal
        _attempt['publication_started'] = True
        return publish_authoring_proposal(checked.plan, model, command_id=command,
            proposal_fields=proposal_fields, transaction_id=transaction_id, authority=authority,
            gates=gates, services=services,
            source_guard=lambda: sources.verify_history(transaction_id=transaction_id,request_id=request_id),
            package_files=tuple(ModelDocument(p, sources.snapshot.raw[p]) for p in sources.packages))
    with project_lock(root, kind='writer', command='change apply', project_id=model.binding.project_id,
                      request_id=request_id, transaction_id=transaction_id) as held:
        replay = _replay(root, intent, actor, request_id, expected_model_root=expected_model_root)
        if replay is not None:
            return replay
        checked, gates, target = compile_request()
        preflight = prepare_publication_check(checked.plan, model, policy=policy, gates=gates,
            package_files=tuple(ModelDocument(p, sources.snapshot.raw[p]) for p in sources.packages))
        if not preflight.request.data['changed_paths']:
            recheck_publication(preflight, preflight.request, held_lock=held,
                transaction_id=transaction_id, authority=authority, gates=gates)
            completion = None
        else:
            _attempt['publication_started'] = True
            completion = publish_guarded_change(preflight, held_lock=held, authority=authority, gates=gates)
        return {**_result(_audit(checked.plan, command, dry_run=False,
            write_state='committed' if completion is not None else 'not_committed'), completion),
            'commit_messages': _messages(target, checked.plan)}


def _messages(target, plan):
    changed = {row['artifact']['id'] for row in plan.data['result_artifacts']}
    return [{'entry_id': v['id'], 'message': commit_message(v)} for v in target.artifacts
            if v['id'] in changed and v.get('entry_kind') == 'commit']
