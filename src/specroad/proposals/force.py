"""Explicit Proposal Force effects, retaining original checks and history.

A refused native review does not become a fabricated review row. Its explicit
requested label and decision are retained in the bound native-intent receipt;
existing review/control originals are preserved byte for byte as values.
"""
from copy import deepcopy
from ..model.canonical import canonical_json_bytes as jcs
from ..changes.write_guard_values import require
from ..changes.metadata_update import updated_audit_fields
from ..authoring.force_compile import _observe, _guard

from ..model.native_force_command_ids import PROPOSAL_COMMANDS as COMMANDS


def author(root, operand, *, command, expected_revision, actor, request_id=None,
           decision=None, comment=None, dry_run=False, authority=None, services=None,
           force=True, force_reason=None, cwd=None, checked_work=None, execution_binding=None):
    from ..authoring.force_native import author_force
    require(command in COMMANDS, 'force_proposal_command_required', exit_code=2)
    # Operand remains the exact native request. Resolution to one managed
    # original happens only on first execution, after historical replay.
    from pathlib import Path
    intent = dict(command_id=command, operand=operand, expected_revision=expected_revision)
    if '/' in operand or '\\' in operand or '-PROP-' not in operand:
        intent['working_directory'] = str(Path.cwd() if cwd is None else Path(cwd).absolute())
    if command == 'proposal.review': intent.update(decision=decision, comment=comment)
    if checked_work is not None: intent['checked_work'] = str(checked_work)
    return author_force(root, intent, actor=actor, request_id=request_id, dry_run=dry_run,
        authority=authority, services=services, force=force, force_reason=force_reason,
        execution_binding=execution_binding)


def _locate(sources, operand, cwd=None):
    if operand in sources.records:
        return sources.artifact(operand)
    # Explicit managed paths are accepted; no guessed or external replacement.
    from pathlib import Path
    path = Path(operand)
    if not path.is_absolute() and cwd is not None:
        path = Path(cwd) / path
    if path.is_absolute():
        try: operand = path.relative_to(sources.root).as_posix()
        except ValueError: require(False, 'force_proposal_managed_original_required', exit_code=7)
    matches = [(p, v) for rows in sources.records.values() for p, v in rows if p == operand]
    require(len(matches) == 1, 'force_proposal_original_missing_or_ambiguous', exit_code=3)
    return matches[0]


def _native(sources, path, value, intent, actor, time, services):
    """Execute the existing evidence producers/reducers, without publication."""
    from .values import ProposalOriginal
    from ..qualification.services import native_services
    from ..changes.target_model import _default_scope
    from ..changes import prepare_change_target, TargetPolicy
    from ..changes._target_materialization import materialize_target
    from ..validation import ModelDocument
    model = sources.model
    require(model is not None, 'proposal_native_model_unavailable')
    services = native_services(services)
    original = ProposalOriginal(sources.before[path], path=path)
    snapshot = sources.native.snapshot
    command = intent['command_id']
    require(original.data['revision'] == intent['expected_revision'], 'proposal_revision_conflict', exit_code=6)
    common = dict(metadata_policy_version='change-metadata-v1', actor=actor, planned_at=time)
    if command == 'proposal.apply':
        from ._apply_control import assessment, operation, prepare_apply_candidates, GATE
        from ._apply_checks import gates as apply_gates
        if 'checked_work' in intent:
            from ._work_handoff import check_work_handoff
            check_work_handoff(intent['checked_work'], snapshot, original, services)
        proof = assessment(snapshot, original, services)
        ops = [*original.data['change_plan']['operations'], operation(original, proof)]
        preconditions = original.data['change_plan']['preconditions']
        folded = prepare_apply_candidates(model, ops, preconditions=preconditions, **common)
        target = folded.target_model
        after = ProposalOriginal(target.source_files[path], path=path)
        gates = apply_gates(snapshot, original, target, after, ops[-1], services)
    else:
        preconditions = ()
        if command == 'proposal.review.start':
            from ._review_checks import _fresh_reports, _gates
            from ._review_control import _operation, prepare_control_candidates, GATE
            validation, check = _fresh_reports(snapshot, original, services)
            op = _operation(original, validation, check)
            folded = prepare_control_candidates(model, [op], **common)
        else:
            from ._decision_evidence import assessment, assessment_version, decision_state, operation
            from ._decision_control import prepare_review_candidates, GATE
            from ._decision_checks import gates as _gates
            decision_state(value['proposal_status'], intent['decision'])
            proof = assessment(snapshot, original, services, version=assessment_version(original, intent['decision']))
            op = operation(original, proof, intent['decision'], intent['comment'], actor)
            folded = prepare_review_candidates(model, [op], **common)
        ops = [op]
        after = ProposalOriginal(jcs(folded.candidates[0].data), path=path)
        target = materialize_target(model, (ModelDocument(path, after.source_bytes),))
        gates = _gates(snapshot, original, after, op, actor, time, services)
    checked = prepare_change_target(model, ops, change_plan_id='force-observation', request_id=None,
        scope_descriptor=_default_scope(), policy=TargetPolicy(command, '1', (GATE,)),
        gates=gates, preconditions=preconditions, **common)
    checked.require_valid()
    return {**sources.before, **target.source_files}


def compile_target(sources, intent, actor, time, decisions, *, services=None):
    command = intent['command_id']
    allowed = {'command_id', 'operand', 'expected_revision', 'working_directory'}
    allowed |= {'decision', 'comment'} if command == 'proposal.review' else {'checked_work'} if command == 'proposal.apply' else set()
    require(not intent.keys() - allowed, 'invalid_authoring_intent', exit_code=2)
    require(type(intent.get('expected_revision')) is int and intent['expected_revision'] > 0,
        'proposal_expected_revision_required', exit_code=2)
    path, before = _locate(sources, intent['operand'], intent.get('working_directory'))
    require(before.get('artifact_type') == 'proposal', 'force_proposal_original_required', exit_code=2)
    _guard(decisions, before, dict(op='proposal_control', expected_revision=intent['expected_revision']), command)
    qualified = _observe(decisions, lambda: _native(sources, path, before, intent, actor, time, services), intent)
    if qualified is not None: return qualified
    target = dict(sources.before); after = deepcopy(before)
    if command == 'proposal.apply':
        from ..changes import ChangePlan
        from ..changes.force_projection import recorded_target
        inner = ChangePlan(jcs(before['change_plan']))
        if inner.data.get('format_version') in ('1.3.0', '1.4.0'):
            from ..changes.resource_replace import check_plan
            if check_plan(inner.data):
                from ..changes.force_write import _target
                target = _target(sources.root, inner, target, decisions, services)
            else: target = recorded_target(inner, target, decisions)
        else: target = recorded_target(inner, target, decisions)
        # A target cannot silently rewrite the controller it is applying.
        require(target.get(path) == sources.before[path], 'force_proposal_inner_control_ambiguous', exit_code=2)
        status = 'applied'
    elif command == 'proposal.review.start':
        status = 'in_review'
    else:
        require(intent.get('decision') in ('approved', 'rejected', 'withdrawn'), 'proposal_review_decision_invalid', exit_code=2)
        require(intent.get('comment') is None or type(intent['comment']) is str, 'proposal_review_comment_invalid', exit_code=2)
        status = 'in_review' if intent['decision'] == 'withdrawn' else intent['decision']
        decisions.decide(actor['actor_type'] == 'human', gate_id='review:explicit_human_decision',
            diagnostic_code='CORE_SECURITY', subject=before['id'], operation=command,
            observed_binding=actor, requested_binding=intent['decision'], effect='record_requested_label_without_human_approval')
    after.update(proposal_status=status, maturity=status)
    after.update(updated_audit_fields(before, actor=actor, planned_at=time))
    target[path] = jcs(after)
    return target
