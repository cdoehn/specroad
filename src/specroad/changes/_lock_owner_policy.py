"""Conservative owner/risk decisions, independent of command kind and I/O."""
from .lock_values import ProjectLockError

def observe_owner(record, probe):
    owner = record.owner
    host = probe.host_id()
    if host is None or owner.host_id is None:
        return 'unverifiable'
    if host != owner.host_id:
        return 'foreign'
    if owner.process_start_id is None:
        return 'unverifiable'
    state, start = probe.process(owner.process_id)
    if state == 'absent':
        return 'dead'
    if state not in ('alive', 'dead') or start is None:
        return 'unverifiable'
    if start != owner.process_start_id:
        return 'pid_reused'
    return state


def _recovery_permitted(record, probe, accept_remote_risk):
    state = observe_owner(record, probe)
    if state == 'alive':
        raise ProjectLockError('live_owner_recovery_denied', exit_code=7)
    if state != 'dead' and not accept_remote_risk:
        raise ProjectLockError('accept_remote_risk_required', exit_code=7)
    return state

