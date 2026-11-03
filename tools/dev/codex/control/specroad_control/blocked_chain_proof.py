"""Passive proof of a blocked source, failed partial Apply and corrected remainder."""
from pathlib import Path
import re
import zipfile
import zlib

from .apply_reconcile_proof import (member, plan, public_plan, completion,
                                    hashed, fail, unique)
from .contracts import timestamp
from .errors import ControlError
from .local import decode_object

from .apply_snapshot import (safe_path, no_collisions, blob, lf_lines, modified_files,
                             snapshot, inventory_hash, apply_stage, FILE_LIMIT, SNAPSHOT_LIMIT)

PLAN_LIMIT = 64 * 1024 * 1024


def test_selection(stage):
    selection = stage['test_plan']
    if (set(selection) != {'format_version', 'commit_id', 'test_ids', 'test_files', 'reason'}
            or type(selection['format_version']) is not int or selection['format_version'] != 1
            or not isinstance(selection['reason'], str) or not 0 < len(selection['reason']) <= 32768):
        fail('Unsupported required-test selection.')
    for key in ('test_files', 'test_ids'):
        values = selection[key]
        if (not isinstance(values, list) or len(values) > FILE_LIMIT
                or any(not isinstance(value, str) or not value or len(value) > 4096 or '\0' in value for value in values)
                or len(set(values)) != len(values)):
            fail('Invalid or duplicate required-test selector.')
    for name in selection['test_files']:
        safe_path(name)
    changed_tests = {name for name in stage['after'] if name.startswith('tests/') and Path(name).name.startswith('test_') and name.endswith('.py')}
    if not changed_tests <= set(selection['test_files']):
        fail('Every changed test file must remain fully mandatory.')
    return selection


def progress_shape(final):
    if (set(final) != {'kind', 'format_version', 'phase', 'source_result_sha256', 'plan_sha256',
                       'active_commit_id', 'actual_head', 'committed', 'error', 'remaining_commit_ids'}
            or type(final['format_version']) is not int or final['format_version'] != 1
            or not isinstance(final['committed'], list) or len(final['committed']) > 128
            or not isinstance(final['remaining_commit_ids'], list)):
        fail('Unsupported progress record.')
    for row in final['committed']:
        if (not isinstance(row, dict) or set(row) != {'commit_id', 'parent', 'commit', 'gate'}
                or not isinstance(row['gate'], dict)
                or set(row['gate']) != {'tests', 'required_tests', 'partition_index',
                                        'selection_sha256', 'observations_sha256'}):
            fail('Unsupported commit gate record.')


def failed_progress(checkpoint, data):
    lines = member(checkpoint, 'logs/execution.log').decode('utf-8').splitlines()
    plans = [decode_object(line[len('SPECROAD_APPLY_PLAN '):]) for line in lines if line.startswith('SPECROAD_APPLY_PLAN ')]
    progress = [decode_object(line[len('SPECROAD_APPLY_PROGRESS '):]) for line in lines if line.startswith('SPECROAD_APPLY_PROGRESS ')]
    if plans != [public_plan(data)] or not progress:
        fail('Failed Apply did not record the exact original plan.')
    final = progress[-1]
    progress_shape(final)
    count = len(final['committed'])
    if (not 0 < count < len(data['stages']) or final.get('phase') != 'failed'
            or not isinstance(final.get('error'), str) or not final['error']
            or final.get('active_commit_id') != data['stages'][count]['commit_id']
            or final.get('remaining_commit_ids') != [s['commit_id'] for s in data['stages'][count:]]):
        fail('Failed Apply does not prove a completed prefix and failed first remainder.')
    # Validate the recorded successful prefix with the completion gate/parent rules.
    if (final.get('kind') != 'specroad-apply-progress-v1' or type(final.get('format_version')) is not int
            or final['format_version'] != 1 or final.get('plan_sha256') != hashed(plans[0])
            or final.get('source_result_sha256') != data['source_result_sha256']
            or final.get('actual_head') != checkpoint['binding']['base_commit']):
        fail('Failed Apply progress binding differs.')
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
            fail('Successful prefix parents or test gates are unproven.')
        parent = row['commit']; seen.add(parent)
    if parent != checkpoint['binding']['base_commit']:
        fail('Checkpoint HEAD differs from the successful prefix.')
    return count, hashed(final)


def compare(original, resumed, source, checkpoint, result):
    left, left_program = plan(original, data_limit=PLAN_LIMIT)
    right, right_program = plan(resumed, data_limit=PLAN_LIMIT)
    if (left_program != right_program or left['initial_dirty'] or left['correction_of'] is not None
            or not right['initial_dirty'] or left['bundle_number'] == right['bundle_number']
            or left['binding'] != source['binding'] or left['source_result_sha256'] != source['sha256']
            or right['binding'] != checkpoint['binding'] or right['source_result_sha256'] != checkpoint['sha256']
            or any(data['apply_repository'] != source['repository_path'] for data in (left, right))
            or len(left['stages']) > 128 or len(right['stages']) > 128):
        fail('Original/correction binding, initial state or entrypoint program differs.')
    count, progress_hash = failed_progress(checkpoint, left)
    remainder = left['stages'][count:]
    if (right['correction_of'] != {'plan_sha256': hashed(public_plan(left)),
                                   'remaining_commit_ids': [s['commit_id'] for s in remainder]}
            or len(right['stages']) != len(remainder)):
        fail('Correction must preserve exactly the uncommitted remainder.')
    for old in left['stages']:
        test_selection(old)
    for old, new in zip(remainder, right['stages']):
        tests = test_selection(new)
        if (old['commit_id'] != new['commit_id'] or old['message'] != new['message']
                or not set(old['after']) <= set(new['after'])
                or any(not set(old['test_plan'][key]) <= set(tests[key]) for key in ('test_files', 'test_ids'))):
            fail('Correction omitted scope, commit identity or mandatory test selection.')
    for line in member(result, 'logs/execution.log').decode('utf-8').splitlines():
        if line.startswith('SPECROAD_APPLY_PROGRESS '):
            progress_shape(decode_object(line[len('SPECROAD_APPLY_PROGRESS '):]))
    initial, work = snapshot(source)
    prefix, dirty = snapshot(checkpoint)
    final_base, final_work = snapshot(result)
    for stage in left['stages'][:count]:
        work = apply_stage(work, stage)
    if work != prefix or apply_stage(work, remainder[0]) != dirty:
        fail('Failed Apply snapshot does not match the completed prefix and failed stage.')
    modified = {name for name in set(prefix) | set(dirty) if prefix.get(name) != dirty.get(name)}
    if not modified <= set(right['stages'][0]['after']):
        fail('Correction does not account for every retained dirty file.')
    for stage in right['stages']:
        dirty = apply_stage(dirty, stage)
    if dirty != final_base or final_base != final_work:
        fail('Final snapshot differs from the complete corrected plan.')
    return {'original_plan_sha256': hashed(public_plan(left)),
            'resumed_plan_sha256': hashed(public_plan(right)), 'program_sha256': left_program,
            'checkpoint_progress_sha256': progress_hash, 'completion_sha256': completion(result, right),
            'snapshot_sha256': hashed([inventory_hash(initial), inventory_hash(prefix),
                                       inventory_hash(apply_stage(prefix, remainder[0])), inventory_hash(final_base)])}


def artifacts(engine, source, original_sha, requested, *, check_current=True):
    source = engine.exchange.source(source); result = engine.exchange.source(requested)
    if (source['dirty'] or source['dry_run'] or not source['success']
            or not result['success'] or result['primary_kind'] != 'success' or result['dirty']
            or result['dry_run'] or result['operation'] != 'apply' or not result['entrypoint_started']
            or not result['completed_commit'] or result['completed_commit'] != result['binding']['base_commit']):
        fail('Blocked source and final committed success must be clean.')
    original = unique(engine.exchange.patches(source), 'Exactly one manual original patch is required.')
    if original_sha is not None and original['sha256'] != original_sha:
        fail('The pinned original patch changed.')
    checkpoint = unique(engine.exchange.following(source, original['sha256']), 'Exactly one failed original Apply is required.')
    if (checkpoint['success'] or checkpoint['primary_kind'] != 'entrypoint_exit' or not checkpoint['dirty']
            or not checkpoint['entrypoint_started'] or checkpoint['completed_commit'] is not None
            or checkpoint['binding']['base_commit'] == source['binding']['base_commit']):
        fail('Checkpoint must prove a failed dirty Apply with a committed prefix.')
    resumed = unique(engine.exchange.patches(checkpoint), 'Exactly one corrective patch is required.')
    following = unique(engine.exchange.following(checkpoint, resumed['sha256']), 'Exactly one corrective Apply is required.')
    if following['sha256'] != result['sha256']:
        fail('Requested Result is not the proven correction outcome.')
    sequence = [source, checkpoint, result]
    if (len({item['run_id'] for item in sequence}) != 3
            or any(item['repository_path'] != source['repository_path'] for item in sequence)):
        fail('Recovery crossed repositories or reused a Result identity.')
    stamps = [timestamp(item.get('captured_at')) for item in sequence]
    if any(stamp is None for stamp in stamps) or not stamps[0] < stamps[1] <= stamps[2]:
        fail('Recovery chronology is missing or contradictory.')
    hashes = compare(original, resumed, source, checkpoint, result)
    if check_current:
        engine.exchange.assert_current(result, {item['run_id'] for item in sequence})
    return {'source': source, 'original': original, 'checkpoint': checkpoint,
            'resumed': resumed, 'result': result, **hashes}


def prove(engine, source, original_sha, requested, *, check_current=True):
    try:
        return artifacts(engine, source, original_sha, requested, check_current=check_current)
    except ControlError:
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError, SyntaxError, RecursionError,
            zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, OverflowError):
        fail('Malformed or unavailable blocked correction chain.')
