"""Explicit native Requirement approval with the ordinary guarded writer."""
from ..changes.requirement_approval import (bind_requirement_approval,
    requirement_approval_gates, ApprovalPrerequisiteProvider)
from .lifecycle import transition_artifact


def approve_requirement(model, operation, *, context, review, verifier,
        prerequisite_provider, gates=(), **options):
    """The operation must already bind the original review/context for retry.

    Gate construction is passive. Current service checks run only if the native
    writer needs a new publication; confirmed receipts replay without reapproval.
    """
    registered = requirement_approval_gates(model, operation,
        actor=options['actor'], planned_at=options['planned_at'], context=context,
        review=review, verifier=verifier, prerequisite_provider=prerequisite_provider,
        gates=gates)
    return transition_artifact(model, operation, gates=registered, **options)
