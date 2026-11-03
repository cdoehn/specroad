"""No forced clarification, laundering, replay or new authority on correction."""
from copy import deepcopy
from hashlib import sha256
import base64
import pytest
from verification_support.bundle_contract import validate_bundle, validate_continuation
from verification_support.bundle_apply import run_bundle
from test_apply_commit_plan import Backend
from test_apply_mixed_bundle import typed


@pytest.mark.parametrize('fault', ['hidden', 'second', 'late', 'pure', 'no-implementation',
    'unknown-role', 'missing-role', 'unknown-kind', 'unknown-field', 'v1-role', 'v1-kind',
    'source-in-clarification', 'missing-spec', 'missing-plan', 'unchanged', 'alibi'])
def test_invalid_classification_never_installs_any_stage(fault):
    value = typed(True); first = value['stages'][0]
    if fault == 'hidden': value['handoff_kind'] = 'patch_ready'
    elif fault == 'second': value['stages'][1]['role'] = 'clarification'
    elif fault == 'late': value['stages'][0], value['stages'][1] = value['stages'][1], value['stages'][0]
    elif fault == 'pure': value['stages'] = value['stages'][:1]
    elif fault == 'no-implementation':
        for stage in value['stages'][1:]: stage['role'] = 'correction'
    elif fault == 'unknown-role': first['role'] = 'approval'
    elif fault == 'missing-role': del first['role']
    elif fault == 'unknown-kind': value['handoff_kind'] = 'spec_clarification'
    elif fault == 'unknown-field': first['approved'] = True
    elif fault == 'v1-role': value['format_version'] = 1; del value['handoff_kind']
    elif fault == 'v1-kind':
        value['format_version'] = 1
        for stage in value['stages']: del stage['role']
    elif fault == 'source-in-clarification':
        first['after']['src/changed.py'] = sha256(b'new').hexdigest()
        first['payloads']['src/changed.py'] = base64.b64encode(b'new').decode()
    elif fault in ('missing-spec', 'missing-plan'):
        name = next(n for n in first['after'] if ('specification/' if fault == 'missing-spec' else 'implementation/') in n)
        del first['after'][name]; del first['payloads'][name]
    elif fault == 'unchanged': first['before'] = dict(first['after'])
    else:
        for stage in value['stages'][1:]: stage['before'] = dict(stage['after'])
    backend = Backend()
    with pytest.raises(ValueError): run_bundle(value, backend)
    assert not backend.calls and not backend.events


def correction(failed):
    original = typed(True); backend = Backend(failed)
    with pytest.raises(ValueError): run_bundle(original, backend)
    progress = backend.events[-1]; count = len(progress['committed'])
    value = deepcopy(original)
    value.update(binding={**original['binding'], 'base_commit': backend.head()},
        source_result_sha256='e'*64, initial_dirty=True, stages=value['stages'][count:],
        handoff_kind='patch_ready_with_clarification' if count == 0 else 'patch_ready',
        correction_of={'plan_sha256': progress['plan_sha256'],
                       'remaining_commit_ids': progress['remaining_commit_ids']})
    return backend.plan, progress, value


@pytest.mark.parametrize('failed', ['DECISION', 'step.W', 'step.R', 'step.C'])
def test_bound_correction_preserves_roles_and_complete_remainder(failed):
    previous, progress, value = correction(failed)
    assert validate_continuation(previous, progress, value) == value
    assert ('clarification' in [s['role'] for s in value['stages']]) == (failed == 'DECISION')


@pytest.mark.parametrize('fault', ['relabel', 'omit', 'plan', 'head', 'new-decision'])
def test_correction_cannot_invent_new_clarification_or_replay_commit(fault):
    previous, progress, value = correction('DECISION' if fault == 'new-decision' else 'step.R')
    if fault == 'relabel': value['stages'][0]['role'] = 'correction'
    elif fault == 'omit': value['stages'].pop(); value['correction_of']['remaining_commit_ids'].pop()
    elif fault == 'plan': value['correction_of']['plan_sha256'] = '0'*64
    elif fault == 'head': value['binding']['base_commit'] = '0'*40
    else:
        first=value['stages'][0]; name=next(iter(first['after'])); raw=b'Another normative decision'
        first['after'][name]=sha256(raw).hexdigest(); first['payloads'][name]=base64.b64encode(raw).decode()
    with pytest.raises(ValueError): validate_continuation(previous, progress, value)


@pytest.mark.parametrize('fault', ['no-binding', 'clean-marker', 'wrong-plan', 'new-target',
                                  'extra-target', 'role', 'omit', 'completed-prefix'])
def test_retained_clarification_cannot_bypass_bound_continuation(fault):
    previous, progress, value = correction('DECISION')
    first = value['stages'][0]
    first['before'] = dict(first['after'])
    if fault == 'no-binding': value['correction_of'] = None
    elif fault == 'clean-marker': value['initial_dirty'] = False
    elif fault == 'wrong-plan': value['correction_of']['plan_sha256'] = '0' * 64
    elif fault in ('new-target', 'extra-target'):
        name = next(iter(first['after'])) if fault == 'new-target' else 'verification/requirements/SR-TC-9999.json'
        raw = b'Unapproved target'
        first['after'][name] = sha256(raw).hexdigest()
        first['payloads'][name] = base64.b64encode(raw).decode()
    elif fault == 'role': first['role'] = 'correction'
    elif fault == 'omit':
        value['stages'].pop()
        value['correction_of']['remaining_commit_ids'] = [s['commit_id'] for s in value['stages']]
    else:
        _, progress, _ = correction('step.W')
    with pytest.raises(ValueError):
        validate_continuation(previous, progress, value)
