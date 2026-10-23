"""Apply explicit, loss-free artifact candidates through the ordinary writer.

The embedding host supplies parsed candidates and current bytes, a complete
native model, policy/gates and separate publication authority. No source parser,
path discovery, allocation, loss consent or alternative file writer is implied.
"""
from ..authoring.execution import _apply_saved_plan
from ..changes import PublicationAuthority, TargetModel, TargetPolicy
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
    if (type(model) is not TargetModel or type(policy) is not TargetPolicy
            or type(authority) is not PublicationAuthority):
        raise ImportIdentityError('typed_import_execution_inputs_required')
    if type(gates) not in (list, tuple) or type(strict) is not bool:
        raise ImportIdentityError('explicit_import_execution_options_required')
    # Own the model and gate sequence before trusted callbacks can run. The
    # planner separately owns candidate JSON and selected mapping resource bytes.
    model = model.snapshot()
    gates = tuple(gates)
    fields = dict(input_format=input_format, input_bytes=input_bytes,
        mapping_resources=mapping_resources, mapping_key=mapping_key,
        mapping_sha256=mapping_sha256, strategy=strategy, change_plan_id=change_plan_id,
        request_id=request_id, actor=actor, planned_at=planned_at,
        scope_descriptor=scope_descriptor, metadata_policy_version=metadata_policy_version,
        policy=policy, gates=gates, strict=strict)
    if plan_bytes is None:
        report = prepare_import_plan(model, candidates, **fields)
    else:
        report = assess_import_plan(plan_bytes, model, candidates, **fields)
    plan = report.require_valid().plan
    execution = _apply_saved_plan(plan, model, command_id='import.apply',
        transaction_id=transaction_id, authority=authority, gates=gates,
        strict=strict, bound_policy=policy)
    return {'format_version': 'artifact-import-execution-v1',
        'submitted_import_plan': report.data, 'submitted_import_plan_sha256': report.sha256,
        'execution': execution, 'input_parsed': False, 'approval_granted': False}
