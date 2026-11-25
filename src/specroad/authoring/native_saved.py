"""Apply exactly a saved ordinary Change Plan with native discovery and gates."""
from uuid import uuid4
from ..changes import ChangePlan, ChangeOperation, TargetPolicy, prepare_authoring_request
from ..changes.request_ids import AuthoringError
from ..changes.target import assess_change_target
from ..changes._saved_plan_fold import fold_saved_plan
from ..changes._target_materialization import materialize_target
from ..changes.execution_values import ChangeExecutionResult
from ..model.canonical import canonical_json_bytes as jcs
from ..validation import ModelDocument
from .project_sources import AuthoringSources
from .native_qualification import publication_gates
from .native_generic import _approval
from .native_attempt import audited
from .plans import _audit
from .execution import _replay, _apply_saved_plan


@audited
def apply_saved(root, intent, *, actor, request_id=None, dry_run=False,
                authority=None, services=None, expected_model_root=None, force=False, force_reason=None, _attempt=None):
    plan = ChangePlan(intent['plan_bytes']); data = plan.data; _attempt['plan'] = plan
    if actor != data['actor'] or request_id != data['request_id']:
        raise AuthoringError('saved_authoring_identity_mismatch', exit_code=6)
    if expected_model_root is not None and expected_model_root != data['base']['model_root_sha256']:
        raise AuthoringError('target_base_root_mismatch', exit_code=6)
    if force or 'force' in data:
        from ..changes.force_write import apply_force_plan, bind_force_plan
        if force and 'force' not in data:
            from ..storage.project import ProjectSource
            project_id = ProjectSource(root).configuration.project_id
            from ..force_operations import current
            call = current()
            selected = None if call is None or not call.owners else {
                'owners': [{'path': p, 'sha256': h} for p, h in call.owners]}
            plan = bind_force_plan(plan, project_id=project_id, force=force, reason=force_reason,
                                   operational_binding=selected)
            _attempt['plan'] = plan
        return apply_force_plan(root, plan, actor=actor, request_id=request_id, force=force,
            force_reason=force_reason, dry_run=dry_run, authority=authority, services=services, _attempt=_attempt)
    operations = data['operations']
    request = prepare_authoring_request(command_id='change apply', actor=actor,
        request_id=request_id, operations=operations, dry_run=dry_run)
    if not dry_run:
        from ..changes import PublicationAuthority
        if type(authority) is not PublicationAuthority:
            raise AuthoringError('authoring_host_authority_required', exit_code=7)
        from ..storage.project import ProjectSource
        replay = _replay(ProjectSource(root), request, 'change.apply')
        if replay is not None:
            if replay['plan_sha256'] != plan.sha256:
                raise AuthoringError('request_plan_conflict', exit_code=6)
            return replay
    sources = AuthoringSources(root); model = sources.model
    scope = data['base']['scope_descriptor']
    base = model.manifest(model.artifacts, scope).sha256
    if base != data['base']['model_root_sha256']:
        raise AuthoringError('target_base_root_mismatch', exit_code=6)
    from ..qualification.project import validate_project
    validate_project({**sources.snapshot.raw, **sources.receipts.payloads}, services=services)
    folded, normalize, _ = fold_saved_plan(plan, model, observed_base_root=base, observed_scope=scope)
    from ..model.paths import artifact_path
    candidates = tuple(ModelDocument(artifact_path(v['artifact']['artifact_type'],v['artifact']['id'],model.configuration.id_prefix), jcs(v['artifact']))
        for v in data['result_artifacts'] if v['artifact']['artifact_type'] not in ('implementation_plan','plan_entry'))
    from ..changes.baselines import baseline_mode, object_documents
    resources = object_documents(operations[0]) if baseline_mode(operations) else ()
    target = (folded.target_model if hasattr(folded, 'target_model') else
              materialize_target(model, candidates + resources))
    if normalize:
        from ..changes._normalization_target import normalization_documents
        normalized, normalized_resources, _ = normalization_documents(model, operations)
        target = materialize_target(model, normalized + normalized_resources)
    if any(op['op'] == 'plan_edit' for op in operations):
        from .native_plan import _check_command
        _check_command(model, target, operations[0])
    txid = 'saved-' + str(uuid4())
    gates = publication_gates(sources, target, services=services,
        transaction_id=None if dry_run else txid, request_id=None if dry_run else request_id)
    if len(operations) == 1:
        operation, extra = _approval(model, operations[0], actor, data['planned_at'], services,
            tuple((p,sources.snapshot.raw[p]) for p in sources.packages))
        if operation != operations[0]:
            raise AuthoringError('saved_approval_binding_mismatch', exit_code=6)
        gates += extra
    if any(op['op'] == 'relation_review_record' for op in operations):
        # Only the dedicated human review command may plan this coupled write.
        raise AuthoringError('review_outcome_requires_specialized_service', exit_code=7)
    from ..changes.evidence import evidence_mode, prepare_evidence_gates
    from ..changes.evidence_import import import_mode, prepare_import_gates
    from ..changes.baselines import prepare_baseline_gates
    if import_mode(operations):
        gates += prepare_import_gates(model, operations, actor=actor, planned_at=data['planned_at'], gates=gates)
    elif evidence_mode(operations):
        gates += prepare_evidence_gates(model, ChangeOperation(operations[0]), actor=actor, planned_at=data['planned_at'], gates=gates)
    elif baseline_mode(operations):
        gates += prepare_baseline_gates(model, ChangeOperation(operations[0]), actor=actor, planned_at=data['planned_at'], gates=gates)
    gates = tuple({g.gate_id:g for g in gates}.values())
    policy = TargetPolicy('change.apply', 'native-saved-authoring-v1', ())
    checked = assess_change_target(plan, model, policy=policy, gates=gates)
    checked.require_valid(); sources.verify_current()
    if dry_run:
        return {**ChangeExecutionResult._create(checked,dry_run=True,fail_on_change=False).data,
            'audit': _audit(plan, 'change.apply',dry_run=True,write_state='not_committed')}
    _attempt['publication_started'] = True
    return _apply_saved_plan(plan, model, command_id='change.apply', transaction_id=txid,
        authority=authority,gates=gates,bound_policy=policy,
        package_files=tuple(ModelDocument(p,sources.snapshot.raw[p]) for p in sources.packages))
