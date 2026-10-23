"""Apply explicit, loss-free artifact candidates through the ordinary writer.

The embedding host supplies parsed candidates and current bytes, a complete
native model, policy/gates and separate publication authority. No source parser,
path discovery, allocation, loss consent or alternative file writer is implied.
"""
from ..authoring.execution import _apply_saved_plan
from ..changes import PublicationAuthority, TargetModel, TargetPolicy
from ..model.errors import ModelError
from ..security import SafetyViolation
from .identities import ImportIdentityError
from .planning import assess_import_plan, prepare_import_plan


def apply_import_plan(model, candidates, *, input_format, input_bytes,
        mapping_resources, mapping_key, mapping_sha256, strategy,
        change_plan_id, request_id, actor, planned_at, scope_descriptor,
        metadata_policy_version, policy, transaction_id, authority,
        plan_bytes=None, gates=(), strict=False):
    """Publish one freshly assessed complete target or replay its native request.

    Saved plan bytes are observations, not authority. When provided they must
    match a fresh assessment of every explicit input; otherwise the same planner
    creates the plan in this call. Invalid targets, conflicts and unaccepted
    losses fail before entering the writer. Only existing bound attachments are
    supported by this artifact-candidate profile.

    The returned submitted_import_plan is a passive description of this call.
    The separate execution is the writer's actual result and durable receipt;
    on replay it describes the original transaction, not today's project state.
    Failures propagate with the native recovery state intact, without retries.
    """
    fields = dict(input_format=input_format, input_bytes=input_bytes,
        mapping_resources=mapping_resources, mapping_key=mapping_key,
        mapping_sha256=mapping_sha256, strategy=strategy, change_plan_id=change_plan_id,
        request_id=request_id, actor=actor, planned_at=planned_at,
        scope_descriptor=scope_descriptor, metadata_policy_version=metadata_policy_version,
        policy=policy, authority=authority, plan_bytes=plan_bytes, gates=gates, strict=strict)
    model, gates, report = _prepare_execution(model, candidates, **fields)
    return _publish(report, model, policy, transaction_id, authority, gates, strict)


def _prepare_execution(model, candidates, *, policy, authority, plan_bytes,
        gates, strict, **fields):
    if (type(model) is not TargetModel or type(policy) is not TargetPolicy
            or type(authority) is not PublicationAuthority):
        raise ImportIdentityError('typed_import_execution_inputs_required')
    if type(gates) not in (list, tuple) or type(strict) is not bool:
        raise ImportIdentityError('explicit_import_execution_options_required')
    # Own inputs before trusted gates run; saved bytes never supply authority.
    model = model.snapshot()
    gates = tuple(gates)
    fields.update(policy=policy, gates=gates, strict=strict)
    if plan_bytes is None:
        report = prepare_import_plan(model, candidates, **fields)
    else:
        report = assess_import_plan(plan_bytes, model, candidates, **fields)
    return model, gates, report


def _publish(report, model, policy, transaction_id, authority, gates, strict):
    plan = report.require_valid().plan
    execution = _apply_saved_plan(plan, model, command_id='import.apply',
        transaction_id=transaction_id, authority=authority, gates=gates,
        strict=strict, bound_policy=policy)
    return {'format_version': 'artifact-import-execution-v1',
        'submitted_import_plan': report.data, 'submitted_import_plan_sha256': report.sha256,
        'execution': execution, 'input_parsed': False, 'approval_granted': False}


def execute_import_plan(model, candidates, *, policy, transaction_id, authority,
        plan_bytes=None, gates=(), strict=False, **planning_fields):
    """Report expected failures without fabricating publication or recovery.

    Accepts the same explicit planning inputs as apply_import_plan. A submitted
    report is included only after fresh assessment (including saved-plan checks).
    It remains passive even when it describes losses or an invalid whole target.
    Once the native writer is entered, only its diagnostic may prove write state;
    absent proof means unknown and requires recovery. No automatic retry, rollback
    or loss consent occurs. Unexpected programming errors still propagate.
    """
    report = None
    entered_writer = False
    try:
        model, gates, report = _prepare_execution(model, candidates, policy=policy,
            authority=authority, plan_bytes=plan_bytes, gates=gates, strict=strict,
            **planning_fields)
        report.require_valid()
        entered_writer = True
        result = _publish(report, model, policy, transaction_id, authority, gates, strict)
        return {**result, 'status': 'success', 'exit_code': result['execution']['exit_code']}
    except (ModelError, SafetyViolation, OSError) as error:
        if isinstance(error, ModelError):
            diagnostic = error.diagnostic()
            exit_code = getattr(error, 'exit_code', 3)
        elif isinstance(error, SafetyViolation):
            diagnostic = {'reason': 'unsafe_import_execution'}
            exit_code = 7
        else:
            # OS messages may contain submitted paths or source contents.
            diagnostic = {'reason': 'import_execution_io_failure'}
            exit_code = 5
        state = diagnostic.get('write_state', 'unknown') if entered_writer else 'not_committed'
        if state not in ('not_committed', 'committed', 'unknown'):
            state = 'unknown'
        return {'format_version': 'artifact-import-execution-v1',
            'status': 'failed', 'exit_code': exit_code,
            'submitted_import_plan': None if report is None else report.data,
            'submitted_import_plan_sha256': None if report is None else report.sha256,
            'execution': None, 'failure_phase': 'native_execution' if entered_writer else 'import_planning',
            'write_state': state, 'diagnostics': [diagnostic],
            'current_target_verified': False,
            'recovery_required': (diagnostic.get('recovery_required', state == 'unknown')
                                  if entered_writer else False),
            'retry_safe': False, 'automatic_retry': False, 'automatic_rollback': False,
            'input_parsed': False, 'approval_granted': False}
