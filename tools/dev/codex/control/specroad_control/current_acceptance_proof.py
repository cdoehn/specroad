"""Prove the selected tested state, not its entire automation ancestry."""
from pathlib import Path

from .apply_reconcile_proof import member, plan, public_plan, hashed, unique
from .apply_snapshot import snapshot, inventory_hash
from .blocked_chain_proof import test_selection
from .contracts import timestamp
from .errors import ControlError
from .local import decode_object
from .mixed_contract import supports_v4
from .mixed_evidence import verify_followup, guarded

PATH = 'verification/current_acceptance.json'
CAPABILITY = {'format_version': 1, 'decision_rule': 'SPECROAD-DECISION-1',
              'decision_contract_version': 4, 'authorization_mode': 'explicit_current',
              'budget_policy': 'preserve', 'maximum_grants_per_result': 1}


def fail(message):
    raise ControlError('current_acceptance_rejected', message)


def stable(value):
    if isinstance(value, dict):
        return {key: stable(item) for key, item in value.items() if key != 'path'}
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


def prove(engine, target, *, unused=True):
    result = engine.exchange.source(target)
    raw = member(result, 'base/' + PATH)
    marker = decode_object(raw)
    if (len(raw) > 4096 or set(marker) != set(CAPABILITY)
            or any(type(marker[k]) is not type(v) or marker[k] != v for k, v in CAPABILITY.items())
            or not supports_v4(result) or not result['success'] or result['dirty']
            or result['primary_kind'] != 'success' or result['dry_run']
            or result['operation'] != 'apply' or not result['entrypoint_started']
            or not result['completed_commit'] or result['completed_commit'] != result['binding']['base_commit']):
        fail('Select a clean committed successful Apply with explicit current-state support.')
    candidates = engine.exchange.candidates('patch', lambda m: all(m.get(k) == v for k, v in result['expected'].items()))
    package = unique((p for p in candidates if p['sha256'] == result['patch_sha256']),
                     'The exact final Apply package is required.')
    data, program = plan(package)
    candidates = engine.exchange.candidates('result', lambda m: all(
        m.get(k) == v for k, v in result['expected'].items()))
    parent = unique((p for p in candidates if p['sha256'] == data['source_result_sha256']),
                    'The exact immediate preimage Result is required.')
    parent = engine.exchange.source(parent)
    package = engine.core.validate(Path(package['path']), parent)
    if (data['format_version'] != 2 or data['binding'] != parent['binding']
            or data['initial_dirty'] != parent['dirty']
            or parent['repository_path'] != result['repository_path']):
        fail('Final package and immediate preimage do not agree.')
    for stage in data['stages']:
        test_selection(stage)
    following = unique(engine.exchange.following(parent, package['sha256']),
                       'The final Apply has competing outcomes.')
    if following['sha256'] != result['sha256']:
        fail('Selected Result differs from the final Apply outcome.')
    verify_followup(engine, parent, package['sha256'], result, data['handoff_kind'])
    stamps = [timestamp(v.get('captured_at')) for v in (parent, result)]
    if None in stamps or not stamps[0] < stamps[1]:
        fail('Final Apply chronology is not proven.')
    base, work = snapshot(result)
    if base != work:
        fail('The selected snapshot is not clean.')
    if unused:
        engine.core.current(result)  # Native nonblocking repository lock, read-only capture.
        # Even previously known later Results veto adoption of an old state.
        engine.exchange.assert_current(result, {result['run_id']})
        if engine.exchange.patches(result):
            fail('A follow-up already exists for the selected Result.')
    return {'parent': parent, 'patch': package, 'result': result,
            'plan_sha256': hashed(public_plan(data)), 'program_sha256': program,
            'snapshot_sha256': inventory_hash(work)}


def checked(engine, target, *, unused=True):
    return guarded(lambda: prove(engine, target, unused=unused))
