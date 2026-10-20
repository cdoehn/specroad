"""Explicit Generic Evidence sets using the shared saved-plan transaction.

The embedding host supplies existing bound original attachments, reserved IDs,
actor/time, project model and publication authority. No CLI or ID discovery.
"""
from ..changes import AuthoringError, TargetModel
from ..changes.evidence_import import prepare_generic_operations
from .plans import preview_authoring_request
from .execution import apply_authoring_plan


def preview_generic_import(model, *, source_path, policy, evidence_ids, title,
        actor, planned_at, change_plan_id, configuration_id=None, request_id=None,
        gates=(), strict=False, fail_on_change=False):
    """Plan every accepted observation together; originals remain immutable.

    The initial writer profile requires a nonempty prepared Generic set with
    explicitly mapped Verification targets. Each original/imported attachment
    must already be supplied in the native model and match its live project bytes.
    No parser outcome grants external-run authentication or verification success.
    """
    if type(model) is not TargetModel:
        raise AuthoringError('typed_authoring_model_required')
    operations, preparation = prepare_generic_operations(model, source_path=source_path, policy=policy,
        evidence_ids=evidence_ids, title=title, configuration_id=configuration_id,
        actor=actor, planned_at=planned_at)
    result = preview_authoring_request(model, 'evidence.import', operations,
        actor=actor, planned_at=planned_at, change_plan_id=change_plan_id,
        request_id=request_id, gates=gates, strict=strict, fail_on_change=fail_on_change)
    return {**result, 'import_preparation': preparation}


def import_evidence(plan, model, *, transaction_id, authority, gates=(),
                    strict=False, package_files=()):
    """Publish the saved complete set, or replay its confirmed native request.

    Retry uses the original saved plan/IDs. The ordinary request hash binds all
    source/mapping/preparation bytes, policy, run/configuration and record values.
    No reallocation, new write, approval or currentness is claimed on replay.
    """
    return apply_authoring_plan(plan, model, command_id='evidence.import',
        transaction_id=transaction_id, authority=authority, gates=gates,
        strict=strict, package_files=package_files)
