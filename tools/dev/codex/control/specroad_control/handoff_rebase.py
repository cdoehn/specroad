"""Worker coordination for proven native refusals; never run Apply here."""
from pathlib import Path
from .errors import ControlError
from .apply_reconcile_proof import unique
from .handoff_rebase_proof import (CAPABILITY, CAPABILITY_PATH, candidate,
                                  original, rejection, require_remaining_scope)

def followups(engine, source, patch_sha, results):
    """Keep waiting through proven busy observations; retain every Result file."""
    effective, ignored = [], set()
    for result in results:
        if candidate(result) and result['primary_kind'] == 'repository_busy' and result['binding'] == source['binding']:
            package = unique((p for p in engine.exchange.patches(source) if p['sha256'] == patch_sha),
                             'Pending package is missing.')
            from .mixed_evidence import guarded
            guarded(rejection, engine, source, package, result)
            ignored.add(result['run_id'])
        else:
            effective.append(result)
    engine.update(apply_wait_reason='repository_busy' if ignored and not effective else None)
    return effective, ignored


def require_current(engine, source, known_runs):
    current = engine.core.call('current', Path(source['path']))
    if (current['sha256'] != source['sha256'] or current['binding'] != source['binding']
            or current['repository_path'] != source['repository_path']
            or current['dirty'] != source['dirty']):
        raise ControlError('current_repository_mismatch', 'A newer native Result is needed before rebinding.')
    engine.exchange.assert_current(source, set(known_runs) | {source['run_id']})


def wait_if_busy(engine, source, known_runs):
    try:
        require_current(engine, source, known_runs)
    except ControlError as error:
        if error.code != 'repository_busy':
            raise
        engine.update(apply_wait_reason='repository_busy')
        return {'halted': False, 'again': False, 'retry_after': 30}
    engine.update(apply_wait_reason=None)
    return None
