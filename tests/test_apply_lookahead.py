"""Extended v2 plans retain prefix binding and one gate per actual state."""
from copy import deepcopy
import pytest
from test_apply_mixed_bundle_right import correction
from test_apply_commit_plan import Backend
from verification_support.bundle_contract import validate_continuation
from verification_support.bundle_apply import run_bundle


def extended(failed='step.R'):
    previous, progress, value = correction(failed)
    for suffix in 'WRC':
        item = deepcopy(value['stages'][-1])
        item['commit_id'] = 'next.' + suffix
        item['test_plan']['commit_id'] = item['commit_id']
        item['role'] = 'implementation'
        item['message'] = 'Planned next ' + suffix
        value['stages'].append(item)
    return previous, progress, value


def test_complete_rest_then_appended_group_each_has_its_own_gate():
    previous, progress, value = extended()
    validate_continuation(previous, progress, value)
    backend = Backend()
    backend.current = value['binding']['base_commit']
    result = run_bundle(value, backend)
    ids = ['step.R', 'step.C', 'next.W', 'next.R', 'next.C']
    assert [row['commit_id'] for row in result['committed']] == ids
    assert backend.calls == [(action, identity) for identity in ids for action in ('install', 'test', 'commit')]


@pytest.mark.parametrize('fault', ['omit', 'reorder', 'replay', 'role', 'clarification', 'false-rest'])
def test_extensions_cannot_replace_rest_replay_commits_or_add_decisions(fault):
    previous, progress, value = extended()
    if fault == 'omit':
        value['stages'].pop(0)
    elif fault == 'reorder':
        value['stages'][:2] = reversed(value['stages'][:2])
    elif fault == 'replay':
        value['stages'][-1]['commit_id'] = 'step.W'
        value['stages'][-1]['test_plan']['commit_id'] = 'step.W'
    elif fault in ('role', 'clarification'):
        value['stages'][-1]['role'] = 'correction' if fault == 'role' else 'clarification'
    else:
        value['correction_of']['remaining_commit_ids'] += ['next.W']
    with pytest.raises(ValueError):
        validate_continuation(previous, progress, value)


def test_pending_clarification_targets_cannot_change_with_lookahead():
    previous, progress, value = extended('DECISION')
    validate_continuation(previous, progress, value)
    value['stages'][0]['after'].pop(next(iter(value['stages'][0]['after'])))
    with pytest.raises(ValueError):
        validate_continuation(previous, progress, value)
