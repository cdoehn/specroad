"""Shared dry-run/direct/saved-plan orchestration; publication is delegated.

Native filesystem execution requires the later transaction/authorization
backend. Dry-run never opens one. Neither callback code nor supplied inventory
is sandboxed or authenticated by this interface.
"""
from .values import ChangePlan
from .target import assess_change_target, prepare_change_target
from .target_model import TargetModel
from .target_values import TargetPolicy
from .execution_values import (EXECUTION_VERSION, ChangeBackend, PublicationRequest,
    PublicationReceipt, ChangeExecutionError, ChangeExecutionResult)
from ._execution_publication import publish_checked_change
from .authoring import prepare_authoring_request, require_direct_authoring, AuthoringError


def _arguments(plan, model, policy, gates, strict, fail_on_change):
    if type(plan) is not ChangePlan or type(model) is not TargetModel or type(policy) is not TargetPolicy:
        raise ChangeExecutionError('plan_model_policy_required', exit_code=2)
    if type(strict) is not bool or type(fail_on_change) is not bool:
        raise ChangeExecutionError('explicit_boolean_options_required', exit_code=2)
    if type(gates) not in (list, tuple):
        raise ChangeExecutionError('explicit_gate_sequence_required', exit_code=2)
    return ChangePlan(plan.source_bytes), model.snapshot(), tuple(gates)


def dry_run_change(plan, model, *, policy, gates=(), strict=False, fail_on_change=False):
    """Read supplied bytes only. No backend, lock, journal, receipt or output file.

    Trusted gates must themselves obey their read-only contract. This API does
    not sandbox Python extensions; no plan field registers one. An invalid
    target retains the full plan and diagnostics, not a success-only summary.
    """
    plan, model, gates = _arguments(plan, model, policy, gates, strict, fail_on_change)
    assessment = assess_change_target(plan, model, policy=policy, gates=gates, strict=strict)
    return ChangeExecutionResult._create(assessment, dry_run=True, fail_on_change=fail_on_change)


def apply_change_plan(plan, model, *, policy, backend=None, gates=(), strict=False, as_proposal=False):
    """Revalidate the SAME plan inside a host transaction and check its readback.

    No native publication is available without explicit trusted integration.
    No automatic retry/rollback on errors, including failures after publication.
    A receipt is evidence of the adapter's assertion, not an fsync/auth proof.
    """
    plan, model, gates = _arguments(plan, model, policy, gates, strict, False)
    require_direct_authoring(plan, as_proposal=as_proposal)
    checked = assess_change_target(plan, model, policy=policy, gates=gates, strict=strict)
    if not checked.target_validated:
        return ChangeExecutionResult._create(checked, dry_run=False)
    if type(backend) is not ChangeBackend:
        raise ChangeExecutionError('transaction_backend_required')
    return publish_checked_change(plan, model, policy=policy, gates=gates, strict=strict,
                                  backend=backend, checked=checked)


def execute_change_request(model, operations, *, dry_run, policy, backend=None,
        gates=(), strict=False, fail_on_change=False, as_proposal=False, **plan_fields):
    """Direct authoring and dry-run share identical plan construction.

    IDs/actor/request/time must be explicitly supplied, never generated here.
    fail_on_change belongs to the dry-run, not a write followed by error code 1.
    """
    if type(dry_run) is not bool or type(fail_on_change) is not bool:
        raise ChangeExecutionError('explicit_boolean_options_required', exit_code=2)
    if fail_on_change and not dry_run:
        raise ChangeExecutionError('fail_on_change_requires_dry_run', exit_code=2)
    if type(gates) not in (tuple, list) or type(strict) is not bool:
        raise ChangeExecutionError('explicit_gate_sequence_and_boolean_required', exit_code=2)
    required = {'change_plan_id', 'request_id', 'actor', 'planned_at',
                'scope_descriptor', 'metadata_policy_version'}
    if not required <= set(plan_fields) or set(plan_fields) - required - {'preconditions'}:
        raise ChangeExecutionError('explicit_plan_fields_required', exit_code=2)
    request = prepare_authoring_request(command_id="change apply",
        actor=plan_fields["actor"], operations=operations, request_id=plan_fields["request_id"],
        dry_run=dry_run, as_proposal=as_proposal)
    if not dry_run and request.data["route"] != "direct":
        raise AuthoringError("proposal_workflow_required", exit_code=7)
    assessment = prepare_change_target(model, operations, policy=policy, gates=tuple(gates),
                                       strict=strict, **plan_fields)
    if dry_run:
        return ChangeExecutionResult._create(assessment, dry_run=True, fail_on_change=fail_on_change)
    return apply_change_plan(assessment.plan, model, policy=policy, backend=backend,
                             gates=tuple(gates), strict=strict, as_proposal=as_proposal)


def execute_change_plan_bytes(raw, model, *, dry_run, policy, backend=None,
                              gates=(), strict=False, fail_on_change=False, as_proposal=False):
    """No implicit path/stdin reads. Preserve exact input bytes through both modes."""
    if type(raw) is not bytes or type(dry_run) is not bool or type(fail_on_change) is not bool:
        raise ChangeExecutionError('explicit_plan_bytes_and_modes_required', exit_code=2)
    if fail_on_change and not dry_run:
        raise ChangeExecutionError('fail_on_change_requires_dry_run', exit_code=2)
    plan = ChangePlan(raw)
    if type(as_proposal) is not bool:
        raise AuthoringError("explicit_boolean_options_required")
    if dry_run:
        return dry_run_change(plan, model, policy=policy, gates=gates,
                              strict=strict, fail_on_change=fail_on_change)
    return apply_change_plan(plan, model, policy=policy, backend=backend,
                             gates=gates, strict=strict, as_proposal=as_proposal)
