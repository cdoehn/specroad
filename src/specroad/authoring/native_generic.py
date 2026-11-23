"""Production discovery and raw-input adapter for the existing authoring core."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from copy import deepcopy
from ..changes import (PublicationAuthority, ChangePlan, ChangeOperation,
    prepare_authoring_request, prepare_publication_check, project_lock, recheck_publication)
from ..changes.target_model import _default_scope
from ..changes.target import prepare_change_target
from ..changes.request_ids import AuthoringError
from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..validation import ModelDocument
from .project_sources import AuthoringSources
from .native_qualification import publication_gates
from .native_intents import compile_intent, COMMANDS
from .plans import _execution_policy, _audit
from .execution import _result


def _replay(root, intent, actor, request_id, *, as_proposal, proposal_fields, expected_model_root=None):
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
        old = proof.journal.data
        ops = old['authoring_binding']['operations']
        record = None
        original = ops
        if as_proposal and len(ops) == 1 and ops[0]['op'] == 'proposal_create':
            record = ops[0]['record']
            inner = ChangePlan(jcs(record['change_plan']))
            from .native_proposal import proposal_metadata
            proposal_metadata(proposal_fields, None, inner, recorded=record)
            ops = inner.data['operations']
        if not ops or (as_proposal and record is None):
            raise AuthoringError('request_operations_conflict', exit_code=6)
        try:
            compile_intent(intent, SimpleNamespace(source=source), old['actor'], old['planned_at'], recorded=ops)
        except (KeyError, TypeError, ModelError) as error:
            raise AuthoringError('request_operations_conflict', exit_code=6) from error
        request = prepare_authoring_request(command_id='proposal create' if as_proposal else intent['command_id'].replace('.', ' '),
            actor=actor, request_id=request_id, operations=original)
        proof.check()
    result = saved_replay(source, request, 'proposal.create' if as_proposal else intent['command_id'])
    result = _created_paths(result, source.configuration.id_prefix)
    return {**result, 'proposal': record, 'publication_kind': 'proposal_draft',
        'review_validity': {'current_approval': False, 'human_decision_required': True}} if as_proposal else result


def _fold(model, operations, actor, time):
    from ..changes.requirement_approval import approval_mode, prepare_requirement_candidates
    from ..changes.baselines import baseline_mode, prepare_baseline_candidates, object_documents
    from ..changes.evidence import evidence_mode, prepare_evidence_candidates
    from ..changes.evidence_import import import_mode, prepare_import_candidates
    from ..changes.reviews import review_mode, prepare_review_candidates
    options = dict(metadata_policy_version='change-metadata-v1', actor=actor, planned_at=time)
    resources = ()
    from ..changes.standard_approval import mode as standard_mode, prepare as prepare_standard
    if standard_mode(operations):
        folded = prepare_standard(model, operations, **options)
    elif approval_mode(operations):
        folded = prepare_requirement_candidates(model, operations, **options)
    elif baseline_mode(operations):
        folded = prepare_baseline_candidates(model, operations, **options)
        resources = object_documents(operations[0])
    elif import_mode(operations):
        folded = prepare_import_candidates(model, operations, **options)
    elif evidence_mode(operations):
        folded = prepare_evidence_candidates(model, operations, **options)
    else:
        from ..changes.lifecycle import prepare_change_lifecycle
        fn = prepare_review_candidates if review_mode(operations) else prepare_change_lifecycle
        folded = fn(model.artifacts, operations, **options, source_files=model.source_files,
            **model.reservations, **({'profile':model.profile} if review_mode(operations) else {}))
    from ..changes._target_materialization import materialize_target
    from ..model.paths import artifact_path
    originals = {v['id']: v for v in model.artifacts}
    return materialize_target(model, tuple(ModelDocument(artifact_path(v['artifact_type'], v['id'],
        model.configuration.id_prefix), jcs(v)) for v in folded.artifacts
        if v['artifact_type'] not in ('implementation_plan', 'plan_entry') and v != originals.get(v['id'])) + resources)


def _approval(model, op, actor, time, services, packages=()):
    from ..qualification.services import native_services, RequirementReviewInputs
    from ..changes.requirement_approval import (bind_requirement_approval, requirement_approval_gates,
        ApprovalPrerequisiteProvider)
    from ..changes.lifecycle_values import LifecycleError
    services = native_services(services)
    if op['op'] != 'transition' or op['to'] != 'approved':
        return op, ()
    value = next(v for v in model.artifacts if v['id'] == op['target'])
    if value['artifact_type'] != 'requirement':
        from ..changes.standard_approval import bind, gate
        op = bind(model, op)
        return op, (gate(model, op, actor=actor, planned_at=time, services=services, packages=packages),)
    if services.requirement_review is None:
        raise LifecycleError('approval_native_review_inputs_required')
    inputs = services.requirement_review(model.snapshot(), op['target'])
    if type(inputs) is not RequirementReviewInputs or inputs.context.data['mode'] != 'transition':
        raise LifecycleError('approval_transition_context_required')
    operation = bind_requirement_approval(ChangeOperation(op), inputs.context, inputs.review)
    def fresh(context):
        latest = services.requirement_review(model.snapshot(), op['target'])
        if (type(latest) is not RequirementReviewInputs or latest.context.input_sha256 != context.input_sha256
                or latest.review.sha256 != inputs.review.sha256 or latest.verifier != inputs.verifier):
            raise LifecycleError('approval_current_inputs_changed')
        return latest.prerequisites
    gates = requirement_approval_gates(model, operation, actor=actor, planned_at=time,
        context=inputs.context, review=inputs.review, verifier=inputs.verifier,
        prerequisite_provider=ApprovalPrerequisiteProvider('native-authoring', '1', fresh))
    return operation.data, gates


from .native_attempt import audited


@audited
def author_generic(root, intent, *, actor, request_id=None, dry_run=False,
                   expected_model_root=None, authority=None, services=None,
                   as_proposal=False, proposal_fields=None, _attempt=None):
    if type(intent) is not dict or intent.get('command_id') not in COMMANDS:
        raise AuthoringError('invalid_authoring_intent')
    if type(dry_run) is not bool or type(as_proposal) is not bool:
        raise AuthoringError('explicit_boolean_options_required')
    intent = deepcopy(intent); command = intent['command_id']
    request = prepare_authoring_request(command_id=command.replace('.', ' '), actor=actor,
        operations=[], request_id=request_id, dry_run=dry_run, as_proposal=as_proposal).data
    actor, request_id = request['actor'], request['request_id']
    # 10.8.1 excludes baseline targets from every embedded Proposal plan.
    # Refuse before identity allocation, lock acquisition or publication.
    if as_proposal and command == 'baseline.create':
        from ..proposals.errors import ProposalError
        raise ProposalError('proposal_control_target_forbidden')
    if not dry_run and type(authority) is not PublicationAuthority:
        raise AuthoringError('authoring_host_authority_required', exit_code=7)
    if not as_proposal and proposal_fields is not None:
        raise AuthoringError('proposal_option_requires_redirect')
    if not dry_run:
        replay = _replay(root, intent, actor, request_id, as_proposal=as_proposal, proposal_fields=proposal_fields, expected_model_root=expected_model_root)
        if replay is not None:
            return replay
    sources = AuthoringSources(root); model = sources.model
    if expected_model_root is not None and model.manifest(model.artifacts, _default_scope()).sha256 != expected_model_root:
        raise AuthoringError('target_base_root_mismatch', exit_code=6)
    from ..qualification.project import validate_project
    validate_project({**sources.snapshot.raw, **sources.receipts.payloads}, services=services)
    time = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    txid, planid = 'author-' + str(uuid4()), 'author-' + str(uuid4())
    policy = _execution_policy(command)
    if command == 'relation.review' and {'source','relation_id','decision','reason'} <= intent.keys():
        from ..changes.reviews import review_time
        from .negative_reviews import _preflight_context
        time = review_time(model.artifacts, _preflight_context(model, intent), time)
    if command == 'evidence.record':
        record = intent.get('record')
        if type(record) is not dict or type(record.get('created_at')) is not str:
            raise AuthoringError('explicit_recorded_evidence_required')
        time = record['created_at']
    packages = tuple(ModelDocument(p, sources.snapshot.raw[p]) for p in sources.packages)
    def prepare():
        sources.verify_current()
        ops = compile_intent(intent, sources, actor, time)
        approval_gates = ()
        if len(ops) == 1:
            op, approval_gates = _approval(model, ops[0], actor, time, services,
                tuple((p,sources.snapshot.raw[p]) for p in sources.packages))
            ops = [op]
        target = _fold(model, ops, actor, time)
        native = publication_gates(sources, target, services=services,
            transaction_id=None if dry_run else txid, request_id=None if dry_run else request_id)
        gates = native + tuple(g for g in approval_gates if g.gate_id not in {a.gate_id for a in native})
        from .plans import _execution_inputs
        _, selected_policy, special = _execution_inputs(model, command, ops, actor, time, gates)
        gates = tuple({g.gate_id:g for g in (*special, *gates)}.values())
        checked = prepare_change_target(model, ops, policy=selected_policy, gates=gates,
            actor=actor, planned_at=time, change_plan_id=planid, request_id=request_id,
            scope_descriptor=_default_scope(), metadata_policy_version='change-metadata-v1')
        _attempt['plan'] = checked.plan
        checked.require_valid(); sources.verify_current()
        return checked, gates, native + approval_gates
    if dry_run:
        checked, gates, original_gates = prepare()
        from ..changes.execution_values import ChangeExecutionResult
        outcome = ChangeExecutionResult._create(checked, dry_run=True, fail_on_change=False).data
        if as_proposal:
            from .proposals import prepare_authoring_proposal
            from .native_proposal import proposal_metadata
            proposal = prepare_authoring_proposal(checked.plan, model, command_id=command,
                gates=original_gates, proposal_fields=proposal_metadata(proposal_fields, sources, checked.plan))
            outcome = {**outcome, 'proposal': proposal.data, 'publication_kind': 'proposal_draft'}
        sources.verify_current()
        return _created_paths({**outcome, 'audit': _audit(checked.plan, command, dry_run=True, write_state='not_committed')}, model.configuration.id_prefix)
    with project_lock(root, kind='writer', command='change apply', project_id=model.binding.project_id,
                      request_id=request_id, transaction_id=txid) as held:
        replay = _replay(root, intent, actor, request_id, as_proposal=as_proposal, proposal_fields=proposal_fields, expected_model_root=expected_model_root)
        if replay is not None:
            return replay
        checked, gates, original_gates = prepare()
        if as_proposal:
            from .native_proposal import proposal_metadata
            proposal_fields = proposal_metadata(proposal_fields, sources, checked.plan)
        else:
            preflight = prepare_publication_check(checked.plan, model, policy=policy, gates=gates,
                                                  package_files=packages)
            if not preflight.request.data['changed_paths']:
                recheck_publication(preflight, preflight.request, held_lock=held,
                    transaction_id=txid, authority=authority, gates=gates)
                completion = None
            else:
                from ..changes.guarded_write import publish_guarded_change
                _attempt['publication_started'] = True
                completion = publish_guarded_change(preflight, held_lock=held, authority=authority, gates=gates)
            return _created_paths(_result(_audit(checked.plan, command, dry_run=False,
                write_state='committed' if completion is not None else 'not_committed'), completion), model.configuration.id_prefix)
    from .proposals import publish_authoring_proposal
    _attempt['publication_started'] = True
    return publish_authoring_proposal(checked.plan, model, command_id=command,
        proposal_fields=proposal_fields, transaction_id=txid, authority=authority,
        gates=original_gates, services=services, package_files=packages,
        source_guard=lambda: sources.verify_history(transaction_id=txid,request_id=request_id))


def _created_paths(result, prefix):
    from ..model.paths import artifact_path
    rows=[]
    for op in result.get('audit',{}).get('operations',[]):
        field={'create':'artifact','evidence_record':'evidence','baseline_create':'record',
               'relation_review_record':'record','proposal_create':'record'}.get(op['op'])
        if field is not None:
            record=op[field]
            rows.append({'artifact_id':record['id'],'path':artifact_path(record['artifact_type'],record['id'],prefix)})
    return {**result,'created_artifacts':rows}
