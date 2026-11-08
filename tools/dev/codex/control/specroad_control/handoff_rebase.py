"""Prove a rejected native handoff before scheduling one newly bound Dev turn."""
from pathlib import Path

from .apply_reconcile_proof import member, plan, public_plan, unique
from .apply_snapshot import apply_stage, snapshot
from .blocked_chain_proof import test_selection
from .contracts import timestamp
from .errors import ControlError
from .local import decode_object
from .mixed_contract import MIXED, supports_v4

CAPABILITY_PATH = 'verification/handoff_rebase.json'
CAPABILITY = {'format_version': 1, 'mode': 'native_rejection_successor',
              'busy_policy': 'wait_for_existing_apply', 'budget_policy': 'preserve',
              'one_patch_per_result': True, 'clarification_targets': 'unchanged'}
KINDS = ('state_mismatch', 'repository_busy')


def fail(message):
    raise ControlError('handoff_rebase_unproven', message)


def candidate(result):
    return result.get('primary_kind') in KINDS and not result.get('entrypoint_started')


def installed(result):
    raw = member(result, 'base/' + CAPABILITY_PATH)
    value = decode_object(raw)
    if (len(raw) > 4096 or type(value) is not dict or set(value) != set(CAPABILITY)
            or any(type(value[k]) is not type(v) or value[k] != v for k, v in CAPABILITY.items())):
        fail('The source project does not authorize native rejection successors.')


def rejection(engine, source, patch, result):
    """Passive original package and native no-entrypoint rejection proof."""
    installed(source); installed(result)
    if (not supports_v4(source) or not supports_v4(result) or not candidate(result)
            or source['dry_run'] or result['success'] or result['dry_run'] or result['operation'] != 'apply'
            or result.get('completed_commit') is not None
            or result['expected'] != source['binding'] or patch['binding'] != source['binding']
            or result['patch_sha256'] != patch['sha256']
            or result['repository_path'] != source['repository_path']
            or result['binding']['repo_id'] != source['binding']['repo_id']
            or result['binding']['fingerprint_algorithm'] != source['binding']['fingerprint_algorithm']
            or result['run_id'] == source['run_id']):
        fail('Only the exact native no-entrypoint rejection of this handoff may advance.')
    stamps = [timestamp(v.get('captured_at')) for v in (source, result)]
    if None in stamps or not stamps[0] < stamps[1]:
        fail('Rejection chronology is not proven.')
    checked = engine.core.validate(Path(patch['path']), source)
    if checked['sha256'] != patch['sha256']:
        fail('The rejected package changed.')
    data, _ = plan(patch)
    if (data['format_version'] != 2 or data['binding'] != source['binding']
            or data['source_result_sha256'] != source['sha256']
            or data['initial_dirty'] != source['dirty']
            or data['apply_repository'] != source['repository_path']):
        fail('The original plan is not bound to the actual preimage Result.')
    base, files = snapshot(source)
    dirty = {p for p in set(base) | set(files) if base.get(p) != files.get(p)}
    if not dirty <= set(data['stages'][0]['payloads']):
        fail('The original first stage omits retained work.')
    for stage in data['stages']:
        test_selection(stage)
        files = apply_stage(files, stage)
    snapshot(result)
    if member(result, 'logs/execution.log').strip():
        fail('A pre-entrypoint rejection must not claim execution output.')
    if result['binding'] == source['binding']:
        if result['primary_kind'] != 'repository_busy':
            fail('A state mismatch without a changed binding is contradictory.')
        if snapshot(result) != snapshot(source):
            fail('An unchanged binding must retain both complete file maps.')
    return data


def original(engine, result):
    """Recover all still-open stages of a rejected patch; never invent progress."""
    package = unique((p for p in engine.exchange.candidates('patch', lambda m: all(
        m.get(k) == v for k, v in result['expected'].items()))
        if p['sha256'] == result['patch_sha256']), 'Exact rejected ZIP is required.')
    data, _ = plan(package)
    parent = unique((s for s in engine.exchange.candidates('result', lambda m: all(
        m.get(k) == v for k, v in data['binding'].items()))
        if s['sha256'] == data['source_result_sha256']), 'Exact rejected preimage Result is required.')
    rejection(engine, parent, package, result)
    if result['binding'] == parent['binding']:
        fail('An unchanged busy result does not authorize a second package.')
    return public_plan(data), {'committed': [],
        'remaining_commit_ids': [s['commit_id'] for s in data['stages']]}


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


def require_remaining_scope(previous, stages):
    """A rejected package retains every stage, intended path and required gate."""
    if len(previous) != len(stages):
        fail('The complete rejected sequence must remain present.')
    for old, new in zip(previous, stages):
        if (any(new[key] != old[key] for key in ('commit_id', 'role', 'message'))
                or not set(old['after']) <= set(new['after'])
                or any(not set(old['test_plan'][key]) <= set(new['test_plan'][key])
                       for key in ('test_files', 'test_ids'))):
            fail('Rebinding must preserve IDs, roles, messages, path scope and required gates.')
