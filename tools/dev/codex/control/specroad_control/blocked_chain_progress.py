"""Passive terminal-prefix checks, including unchanged native outer timeouts."""
import re
from .apply_reconcile_proof import member, public_plan, hashed, fail
from .blocked_chain_proof import progress_shape
from .local import decode_object


def records(result, prefix):
    return [decode_object(line[len(prefix):])
            for line in member(result, 'logs/execution.log').decode('utf-8').splitlines()
            if line.startswith(prefix)]


def partial_progress(result, data):
    plans = records(result, 'SPECROAD_APPLY_PLAN ')
    progress = records(result, 'SPECROAD_APPLY_PROGRESS ')
    if plans != [public_plan(data)] or not progress:
        fail('Failed Apply did not record its exact plan and progress.')
    final = progress[-1]
    progress_shape(final)
    count = len(final['committed'])
    if (not 0 <= count < len(data['stages'])
            or final['kind'] != 'specroad-apply-progress-v1'
            or final['active_commit_id'] != data['stages'][count]['commit_id']
            or final['remaining_commit_ids'] != [s['commit_id'] for s in data['stages'][count:]]
            or final['plan_sha256'] != hashed(plans[0])
            or final['source_result_sha256'] != data['source_result_sha256']
            or final['actual_head'] != result['binding']['base_commit']):
        fail('Failed Apply does not prove its complete remaining sequence.')
    if result['primary_kind'] == 'timeout':
        run = decode_object(member(result, 'logs/run.json'))
        primary = run['primary_result']
        if (run.get('run_id') != result['run_id'] or not run.get('ended_at')
                or run.get('operation') != 'apply' or run.get('dry_run') is not False
                or primary.get('kind') != 'timeout' or primary.get('success') is not False
                or primary.get('timed_out') is not True or primary.get('interrupted') is not False
                or primary.get('entrypoint_started') is not True
                or primary.get('entrypoint_exit_code') is not None
                or final['phase'] != 'testing' or final['error'] is not None):
            fail('Outer timeout and its unchanged testing record are unproven.')
    elif (result['primary_kind'] != 'entrypoint_exit' or final['phase'] != 'failed'
          or not isinstance(final['error'], str) or not final['error']):
        fail('Only explicit failed-gate or native outer-timeout checkpoints are supported.')
    parent, seen = data['binding']['base_commit'], {data['binding']['base_commit']}
    for stage, row in zip(data['stages'][:count], final['committed']):
        gate = row['gate']
        if (row['commit_id'] != stage['commit_id'] or row['parent'] != parent or row['commit'] in seen
                or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', row['commit'])
                or not re.fullmatch('[0-9a-f]{64}', gate['selection_sha256'])
                or not re.fullmatch('[0-9a-f]{64}', gate['observations_sha256'])
                or type(gate['tests']) is not int or type(gate['required_tests']) is not int
                or not 0 < gate['required_tests'] <= gate['tests']
                or type(gate['partition_index']) is not int or gate['partition_index'] < 0):
            fail('A recorded prefix commit has no valid parent/test gate.')
        parent = row['commit']; seen.add(parent)
    if parent != result['binding']['base_commit']:
        fail('Native checkpoint HEAD differs from the recorded prefix.')
    return count, hashed(final)
