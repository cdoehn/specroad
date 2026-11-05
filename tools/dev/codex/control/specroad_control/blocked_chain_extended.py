"""Explicit, bounded recovery across native failed, corrected and completed Applies.

This proves existing artifacts only. It never executes a patch, retries Apply,
classifies an unknown handoff, or changes the original clarification budget.
"""
from pathlib import Path
import re
import zipfile
import zlib

from .apply_reconcile_proof import member, plan, public_plan, completion, hashed, fail, unique
from .apply_snapshot import snapshot, apply_stage, inventory_hash
from .blocked_chain_proof import progress_shape, test_selection
from .contracts import BINDING, timestamp
from .errors import ControlError
from .local import decode_object

MAX_LINKS = 32
MAX_STAGES = 128


def records(result, prefix):
    return [decode_object(line[len(prefix):])
            for line in member(result, 'logs/execution.log').decode('utf-8').splitlines()
            if line.startswith(prefix)]


def push_source(result):
    start = records(result, 'SPECROAD_PUSH_START ')
    end = records(result, 'SPECROAD_PUSH_COMPLETE ')
    if len(start) != 1 or len(end) != 1:
        fail('An unchanged bridge requires one native push start/completion pair.')
    left, right = start[0], end[0]
    common = {'source_result_sha256', 'target_commit', 'remote', 'ref', 'remote_before'}
    if (set(left) != common | {'force'}
            or set(right) != common | {'remote_after', 'success', 'local_product_changes', 'new_commit_created'}
            or any(left[key] != right[key] for key in common)
            or left['force'] is not False or right['success'] is not True
            or right['local_product_changes'] is not False or right['new_commit_created'] is not False
            or left['remote'] != 'origin' or left['ref'] != 'refs/heads/dev'
            or left['target_commit'] != result['binding']['base_commit']
            or right['remote_after'] != left['target_commit']
            or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', left['remote_before'])
            or not re.fullmatch('[0-9a-f]{64}', left['source_result_sha256'])):
        fail('Unchanged push bridge has incomplete or contradictory evidence.')
    return left['source_result_sha256'], hashed([left, right])


def previous_result(engine, current, source_sha):
    candidates = engine.exchange.candidates('result',
        lambda m: all(m.get(key) == current['expected'][key] for key in BINDING))
    return unique([item for item in candidates if item['sha256'] == source_sha],
                  'The exact predecessor Result is missing or ambiguous.')


def walk_back(engine, source, requested):
    """Select predecessors by SHA and four bindings; timestamps only veto."""
    current, links, seen = requested, [], set()
    while current['sha256'] != source['sha256']:
        if len(links) >= MAX_LINKS or current['run_id'] in seen:
            fail('Correction chain is cyclic or exceeds the explicit recovery limit.')
        seen.add(current['run_id'])
        if (current['operation'] != 'apply' or current['dry_run']
                or not current['entrypoint_started'] or current['expected'] is None
                or current['repository_path'] != source['repository_path']):
            fail('Every link must be a real native Apply in the same repository.')
        candidates = engine.exchange.candidates('patch',
            lambda m: all(m.get(key) == current['expected'][key] for key in BINDING))
        package = unique([item for item in candidates if item['sha256'] == current['patch_sha256']],
                         'The exact applied patch is missing or ambiguous.')
        if current['success'] and current['completed_commit'] is None:
            source_sha, progress_hash = push_source(current)
            data, program = None, None
        else:
            data, program = plan(package)
            if len(data['stages']) > MAX_STAGES:
                fail('Apply stage count exceeds the explicit recovery limit.')
            source_sha, progress_hash = data['source_result_sha256'], None
        previous = previous_result(engine, current, source_sha)
        package = engine.core.validate(Path(package['path']), previous)
        if (package['binding'] != previous['binding'] or current['expected'] != previous['binding']
                or not package.get('binding_matches') or package.get('reference_sha256') != previous['sha256']):
            fail('Native patch validation does not bind this exact predecessor.')
        following = unique(engine.exchange.following(previous, package['sha256']),
                           'An Apply link has competing outcomes.')
        if following['sha256'] != current['sha256']:
            fail('Selected native Result differs from the unique Apply outcome.')
        stamps = [timestamp(item.get('captured_at')) for item in (previous, current)]
        if any(stamp is None for stamp in stamps) or not stamps[0] < stamps[1]:
            fail('Correction-chain chronology is missing or contradictory.')
        links.append((previous, package, current, data, program, progress_hash))
        current = previous
    if not links or current['run_id'] != source['run_id'] or current['run_id'] in seen:
        fail('Chain does not start at the exact blocked source.')
    return list(reversed(links))


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


def correction(previous_data, data, count, program, previous_program):
    rest = previous_data['stages'][count:]
    if (program != previous_program or not data['initial_dirty']
            or data['bundle_number'] == previous_data['bundle_number']
            or data['correction_of'] != {'plan_sha256': hashed(public_plan(previous_data)),
                                        'remaining_commit_ids': [s['commit_id'] for s in rest]}
            or len(data['stages']) != len(rest)):
        fail('Correction changed the entrypoint or omitted the complete pending remainder.')
    for old, new in zip(rest, data['stages']):
        tests = test_selection(new)
        if (any(old.get(key) != new.get(key) for key in ('commit_id', 'message', 'role'))
                or not set(old['after']) <= set(new['after'])
                or any(not set(old['test_plan'][key]) <= set(tests[key]) for key in ('test_ids', 'test_files'))
                or (old.get('role') == 'clarification' and old['after'] != new['after'])):
            fail('Correction changed commit identity, clarification bytes, scope or mandatory tests.')


def verify_links(links, source):
    base, work = snapshot(source)
    if base != work:
        fail('Blocked source must have a complete clean snapshot.')
    pending, steps, committed_ids, bundle_numbers = None, [], set(), set()
    for previous, package, result, data, program, progress_hash in links:
        result_base, result_work = snapshot(result)
        if data is None:
            if (pending is not None or result['dirty'] or result['primary_kind'] != 'success'
                    or result['binding'] != previous['binding'] or result_base != base
                    or result_work != work or base != work):
                fail('A push bridge must preserve the complete clean state after finished work.')
            plan_hash, kind = None, 'unchanged_push'
        else:
            if (data['binding'] != previous['binding'] or data['source_result_sha256'] != previous['sha256']
                    or data['apply_repository'] != source['repository_path']
                    or data['initial_dirty'] != previous['dirty'] or data['bundle_number'] in bundle_numbers):
                fail('Apply plan binding, dirty state or bundle identity is inconsistent.')
            bundle_numbers.add(data['bundle_number'])
            for stage in data['stages']:
                test_selection(stage)
                if stage['commit_id'] in committed_ids:
                    fail('A successful commit ID must never be replayed.')
            if pending is None:
                if data['correction_of'] is not None or data['initial_dirty']:
                    fail('A new complete plan needs a clean predecessor and no invented correction.')
            else:
                old, count, old_program = pending
                correction(old, data, count, program, old_program)
                dirty = {name for name in set(base) | set(work) if base.get(name) != work.get(name)}
                if not dirty <= set(data['stages'][0]['after']):
                    fail('Correction does not account for every retained dirty file.')
            if result['success']:
                if (result['primary_kind'] != 'success' or result['dirty']
                        or result['completed_commit'] != result['binding']['base_commit']):
                    fail('A completed plan requires the clean native final commit.')
                for record in records(result, 'SPECROAD_APPLY_PROGRESS '):
                    progress_shape(record)
                progress_hash = completion(result, data)
                count = len(data['stages']); pending = None; kind = 'completed_plan'
            else:
                if result['completed_commit'] is not None or not result['dirty']:
                    fail('An incomplete plan needs a native dirty checkpoint.')
                count, progress_hash = partial_progress(result, data)
                pending = (data, count, program); kind = 'timeout' if result['primary_kind'] == 'timeout' else 'failed_gate'
            for stage in data['stages'][:count]:
                work = apply_stage(work, stage)
                committed_ids.add(stage['commit_id'])
            # Zero-prefix corrections retain the old base, not their dirty preimage.
            expected_base = work if count else base
            expected_work = apply_stage(work, data['stages'][count]) if pending else work
            if result_base != expected_base or result_work != expected_work:
                fail('Native snapshot differs from the committed prefix and materialized next stage.')
            plan_hash = hashed(public_plan(data))
        steps.append({'source': previous, 'patch': package, 'result': result, 'kind': kind,
                      'plan_sha256': plan_hash, 'program_sha256': program,
                      'progress_sha256': progress_hash,
                      'snapshot_sha256': hashed([inventory_hash(base), inventory_hash(work),
                                                  inventory_hash(result_base), inventory_hash(result_work)])})
        base, work = result_base, result_work
    if pending is not None or steps[-1]['kind'] != 'completed_plan':
        fail('Requested recovery must finish every announced stage with a final committed plan.')
    return steps


def artifacts(engine, source, original_sha, requested, *, check_current=True):
    source = engine.exchange.source(source); result = engine.exchange.source(requested)
    if (source['dirty'] or source['dry_run'] or not source['success']
            or not result['success'] or result['dirty'] or not result['completed_commit']):
        fail('Blocked source and requested committed outcome must be clean.')
    links = walk_back(engine, source, result)
    if original_sha is not None and links[0][1]['sha256'] != original_sha:
        fail('Pinned original patch changed.')
    # Reject alternate native candidates. A same-binding push from an earlier
    # proven link is already consumed; it cannot become a second future patch.
    consumed = set()
    for previous, package, *_ in links:
        candidates = [item for item in engine.exchange.patches(previous) if item['sha256'] not in consumed]
        chosen = unique(candidates, 'Each chain source must have exactly one unconsumed patch.')
        if chosen['sha256'] != package['sha256']:
            fail('Another patch competes with the requested recovery chain.')
        consumed.add(package['sha256'])
    steps = verify_links(links, source)
    if check_current:
        engine.exchange.assert_current(result, {source['run_id'], *(row['result']['run_id'] for row in steps)})
    hashes = [{key: value for key, value in row.items() if key not in ('source', 'patch', 'result')}
              | {key + '_sha256': row[key]['sha256'] for key in ('source', 'patch', 'result')} for row in steps]
    return {'source': source, 'result': result, 'steps': steps, 'chain_sha256': hashed(hashes)}


def prove(engine, source, original_sha, requested, *, check_current=True):
    try:
        return artifacts(engine, source, original_sha, requested, check_current=check_current)
    except ControlError:
        raise
    except (OSError, ValueError, TypeError, KeyError, IndexError, SyntaxError, RecursionError,
            zipfile.BadZipFile, zlib.error, RuntimeError, NotImplementedError, OverflowError):
        fail('Malformed or unavailable extended blocked correction chain.')
