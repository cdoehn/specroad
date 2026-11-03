"""Passive direct-successor proof for explicit grants; no writes or dispatch."""
from .apply_reconcile_proof import hashed, public_plan, completion, unique
from .contracts import timestamp
from .clarification_authorization_contract import require_support
from .job_contract import new_contract
from .mixed_contract import supports_v4
from .mixed_evidence import verify_handoff, verify_followup
from .errors import ControlError


def fail(message):
    raise ControlError('clarification_authorization_rejected', message)


def prove(engine, ledger, source, requested):
    source, result = engine.exchange.source(source), engine.exchange.source(requested)
    require_support(result)
    if (not result['success'] or result['primary_kind'] != 'success' or result['dirty']
            or result['dry_run'] or result['operation'] != 'apply' or not result['entrypoint_started']
            or not result['completed_commit'] or result['completed_commit'] != result['binding']['base_commit']
            or not supports_v4(result) or result['expected'] != source['binding']):
        fail('A direct clean committed successor with installed contract 4 is required.')
    package = unique(engine.exchange.patches(source), 'Exactly one bound manual bundle is required.')
    following = unique(engine.exchange.following(source, package['sha256']), 'Exactly one Apply result is required.')
    if following['sha256'] != result['sha256']:
        fail('The explicit Result is not the unique successor of this source.')
    data = verify_handoff(engine, source, package, new_contract(version=4), 'patch_ready')
    if not any(stage['role'] in ('implementation', 'correction') and any(
            not name.startswith(('docs/', 'verification/')) and stage['before'].get(name) != value
            for name, value in stage['after'].items()) for stage in data['stages']):
        fail('A real implementation or correction is required, not an authority-only document commit.')
    verify_followup(engine, source, package['sha256'], result, 'patch_ready')
    stamps = [timestamp(item.get('captured_at')) for item in (source, result)]
    if None in stamps or not stamps[0] < stamps[1]:
        fail('Source and successor chronology is not proven.')
    engine.exchange.assert_current(result, ledger.known_runs() | {result['run_id']})
    return {'source': source, 'patch': package, 'result': result,
            'plan_sha256': hashed(public_plan(data)), 'completion_sha256': completion(result, data)}
