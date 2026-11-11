"""Pure successor authority; persistence stays inside the ledger transaction."""
from .job_contract import contract, new_contract, fresh_contract
from .mixed_contract import MIXED, supports_v4


def successor_contract(previous, handoff, source, *, verified=False, pending_clarification=False, clarification_allowed=True):
    committed = (source['success'] and not source['dirty'] and source.get('completed_commit')
                 and source['completed_commit'] == source['binding']['base_commit'])
    if previous and previous['version'] == 4:
        remaining = previous['clarifications_remaining']
        if handoff == MIXED and not previous['clarification_continuation']:
            remaining -= 1
        if verified and committed and handoff in ('patch_ready', MIXED) and supports_v4(source):
            return fresh_contract(source, allowed=clarification_allowed)
        continuing = bool(verified and handoff == MIXED and not committed and pending_clarification)
        return new_contract(remaining, allowed=False, version=4, continuation=continuing,
                            limit=previous['clarification_limit'])
    # Only a proven normal handoff opens a fresh v3 budget on a new source.
    # Already bound attempts and legacy clarification chains stay unchanged.
    if handoff == 'patch_ready' and committed:
        return (fresh_contract(source, allowed=clarification_allowed) if supports_v4(source)
                else new_contract(allowed=clarification_allowed))
    if previous and previous['version'] == 3:
        remaining = previous['clarifications_remaining']
        if handoff == 'spec_clarification':
            remaining -= 1
        allowed = bool(handoff == 'spec_clarification' and committed and remaining > 0)
        return new_contract(remaining, allowed=allowed)
    if previous and previous['version'] == 2:
        # Failed normal work preserves the old v2 rule. Unknown/crashed output
        # cannot prove that a clarification ended or upgrade its authority.
        allowed = previous['clarification_allowed'] if handoff == 'patch_ready' else False
        return {'version': 2, 'clarification_allowed': allowed}
    return contract()
