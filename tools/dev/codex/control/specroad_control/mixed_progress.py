"""Passive typed Apply progress and original-prefix proof; no execution."""
import re
from .apply_reconcile_proof import plan, member, public_plan, hashed, unique
from .blocked_chain_proof import progress_shape
from .errors import ControlError
from .local import decode_object
from .mixed_contract import validate_roles


def fail(message):
    raise ControlError('mixed_handoff_unproven', message)


def progress(result):
    lines = member(result, 'logs/execution.log').decode('utf-8').splitlines()
    plans = [decode_object(line[len('SPECROAD_APPLY_PLAN '):]) for line in lines if line.startswith('SPECROAD_APPLY_PLAN ')]
    records = [decode_object(line[len('SPECROAD_APPLY_PROGRESS '):]) for line in lines if line.startswith('SPECROAD_APPLY_PROGRESS ')]
    if len(plans) != 1 or not records:
        fail('One complete public plan and terminal progress are required.')
    value, final = plans[0], records[-1]
    progress_shape(final)
    if type(value.get('format_version')) is not int or value['format_version'] != 2:
        fail('A v4 request needs an explicit typed Apply plan.')
    validate_roles(value)
    ids = [s['commit_id'] for s in value['stages']]
    done = final.get('committed')
    if (type(done) is not list or len(done) > len(ids)
            or final.get('kind') != 'specroad-apply-progress-v1' or type(final.get('format_version')) is not int or final['format_version'] != 1
            or final.get('phase') != ('completed' if result['success'] else 'failed')
            or final.get('plan_sha256') != hashed(value)
            or final.get('source_result_sha256') != value['source_result_sha256']
            or final.get('actual_head') != result['binding']['base_commit']
            or value['binding'] != result['expected']
            or [s['commit_id'] for s in done] != ids[:len(done)]
            or final.get('remaining_commit_ids') != ids[len(done):]):
        fail('Terminal Result does not prove the exact typed commit prefix.')
    parent = value['binding']['base_commit']; seen = {parent}
    for row in done:
        gate = row['gate']
        if (row['parent'] != parent or row['commit'] in seen
                or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', row['commit'])
                or not re.fullmatch('[0-9a-f]{64}', gate['selection_sha256'])
                or not re.fullmatch('[0-9a-f]{64}', gate['observations_sha256'])
                or type(gate['tests']) is not int or type(gate['required_tests']) is not int
                or not 0 < gate['required_tests'] <= gate['tests']
                or type(gate['partition_index']) is not int or gate['partition_index'] not in (0, 1, 2)):
            fail('Commit chain or exact per-stage gates are not proven.')
        parent = row['commit']; seen.add(parent)
    if parent != final['actual_head']:
        fail('HEAD changed outside the recorded commit prefix.')
    if result['success']:
        if (result['dirty'] or result['completed_commit'] != parent or len(done) != len(ids)
                or final.get('error') is not None or final.get('active_commit_id') is not None):
            fail('The mixed bundle did not finish every stage cleanly.')
    else:
        # Failure can occur before a stage or in its post-commit clean check.
        active = final.get('active_commit_id')
        allowed_active = ([ids[len(done)]] if len(done) < len(ids) else []) + ([ids[len(done)-1]] if done else [None])
        if (not isinstance(final.get('error'), str) or not final['error']
                or active not in allowed_active or result.get('completed_commit') is not None):
            fail('An unsuccessful Result needs a consistent actual failure record.')
    return value, final


def source_parent(engine, source):
    from .handoff_rebase import candidate, original
    if candidate(source):
        return original(engine, source)
    old, failed = progress(source)
    patches = engine.exchange.candidates('patch', lambda m: all(m.get(k) == v for k, v in source['expected'].items()))
    original = unique((p for p in patches if p['sha256'] == source['patch_sha256']), 'Original typed patch is missing.')
    data, _ = plan(original)
    if (source['dry_run'] or source['operation'] != 'apply' or not source['entrypoint_started']
            or public_plan(data) != old or data['binding'] != original['binding']
            or data['apply_repository'] != source['repository_path']):
        fail('The failed Result log does not match its actual original ZIP.')
    return old, failed
