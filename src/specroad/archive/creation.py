"""Native working-Baseline authoring with explicit host-owned identities.

Preparation returns a saveable plan; execution never reallocates or silently
replans it. The trusted host supplies model/history, ID/time and semantic gates.
No CLI registration, release readiness or general historical verifier is implied.
"""
from ._working_plan import prepare_working_baseline
from ..authoring.execution import apply_authoring_plan


def create_working_baseline(plan, model, *, transaction_id, authority,
        gates=(), strict=False, package_files=()):
    """Publish exactly the saved working plan with native lock/journal/receipt.

    Native failures preserve actual transaction state. A confirmed identical
    request replays its durable receipt without a second Baseline or object write.
    Every referenced object is staged before the sealed record is published.
    """
    return apply_authoring_plan(plan, model, command_id='baseline.create',
        transaction_id=transaction_id, authority=authority, gates=gates,
        strict=strict, package_files=package_files)
