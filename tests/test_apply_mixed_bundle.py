"""Optional clarification and separately gated ordinary/mixed commit plans."""
import ast
import base64
from copy import deepcopy
from hashlib import sha256
import json
import zlib
import pytest
from verification_support.bundle_apply import run_bundle, validate_bundle, remaining_commits, public_plan, canonical
from verification_support.bundle_prepare import prepare_stage, render_entrypoint
from test_apply_commit_plan import bundle, Backend, make_plan


def typed(mixed=False):
    value = bundle()
    value.update(format_version=2, handoff_kind='patch_ready_with_clarification' if mixed else 'patch_ready')
    for stage in value['stages']:
        stage['role'] = 'implementation'
    if mixed:
        stage = deepcopy(value['stages'][0])
        stage.update(commit_id='DECISION', message='OFF-PLAN explicit decision', role='clarification',
            before={}, after={}, payloads={}, test_plan=make_plan(['case.0'], commit_id='DECISION'))
        for name in ('docs/specification/SpecRoad_Spezifikation.md', 'docs/implementation/SpecRoad_Implementierungsplan.md'):
            raw = b'Explicit fixture decision\n'
            stage['after'][name] = sha256(raw).hexdigest()
            stage['payloads'][name] = base64.b64encode(raw).decode()
        value['stages'].insert(0, stage)
    return value


def test_no_gap_requires_no_clarification_commit():
    value = typed()
    backend = Backend()
    final = run_bundle(value, backend)
    assert final['phase'] == 'completed'
    assert backend.calls == [(action, 'step.' + phase) for phase in 'WRC' for action in ('install', 'test', 'commit')]
    assert len(final['committed']) == 3
    assert all(s['role'] == 'implementation' for s in backend.plan['stages'])


def test_optional_prefix_is_gated_and_committed_before_implementation():
    backend = Backend()
    final = run_bundle(typed(True), backend)
    ids = ['DECISION', 'step.W', 'step.R', 'step.C']
    assert backend.calls == [(action, identifier) for identifier in ids for action in ('install', 'test', 'commit')]
    assert [s['commit_id'] for s in final['committed']] == ids
    assert backend.plan['handoff_kind'] == 'patch_ready_with_clarification'


def test_split_plan_prefix_preserves_separate_gates():
    from support.plan_scope import PLAN_PARTS, add_plan_payload
    value = typed(True)
    for name in PLAN_PARTS:
        add_plan_payload(value['stages'][0], name)
    backend = Backend()
    final = run_bundle(value, backend)
    ids = ['DECISION', 'step.W', 'step.R', 'step.C']
    assert [row['commit_id'] for row in final['committed']] == ids
    assert backend.calls == [(action, identifier) for identifier in ids
                             for action in ('install', 'test', 'commit')]
    assert set(PLAN_PARTS) <= set(backend.plan['stages'][0]['after'])


@pytest.mark.parametrize('mixed', [False, True])
def test_rendered_entrypoint_binds_roles_in_literal_data_without_execution(mixed):
    value = typed(mixed)
    raw = render_entrypoint(value, core_python='/fixture/python')
    code = raw.split(b"<<'SPECROAD_APPLY_COMMIT_PLAN'\n", 1)[1].rsplit(b'\nSPECROAD_APPLY_COMMIT_PLAN', 1)[0]
    tree = ast.parse(code)
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'DATA')
    packed = node.value.args[0].args[0].args[0].value
    assert json.loads(zlib.decompress(base64.b64decode(packed))) == value
    assert public_plan(value)['stages'][0]['role'] == value['stages'][0]['role']


def test_stage_preparation_keeps_v1_default_and_supports_explicit_v2_role(tmp_path):
    before, after = tmp_path/'before', tmp_path/'after'
    before.mkdir(); after.mkdir(); (after/'sample.py').write_text('value = 1\n')
    for root in (before, after):
        for name in ('src/specroad', 'tests', 'tools', 'verification'):
            (root/name).mkdir(parents=True)
        (root/'pyproject.toml').write_text('[project]\nname="fixture"\n')
    args = dict(commit_id='step.W', message='implementation', test_plan=make_plan(['case.0']))
    old = prepare_stage(before, after, ['sample.py'], **args)
    new = prepare_stage(before, after, ['sample.py'], role='implementation', **args)
    assert 'role' not in old and new == {**old, 'role': 'implementation'}


@pytest.mark.parametrize('failed,done', [('DECISION', 0), ('step.W', 1), ('step.R', 2), ('step.C', 3)])
def test_failure_retains_exact_commit_prefix_and_all_unfinished_roles(failed, done):
    value = typed(True); backend = Backend(failed)
    with pytest.raises(ValueError):
        run_bundle(value, backend)
    final = backend.events[-1]
    rest = remaining_commits(backend.plan, final, result_head=backend.head())
    assert rest == public_plan(value)['stages'][done:]
    assert len(final['committed']) == done
    assert backend.calls[-1] == ('test', failed)
    continuation = deepcopy(value)
    continuation.update(binding={**value['binding'], 'base_commit': backend.head()},
        initial_dirty=True, source_result_sha256='e'*64, stages=value['stages'][done:],
        handoff_kind='patch_ready_with_clarification' if done == 0 else 'patch_ready',
        correction_of={'plan_sha256': final['plan_sha256'], 'remaining_commit_ids': [s['commit_id'] for s in rest]})
    resumed = Backend(); result = run_bundle(continuation, resumed)
    assert result['phase'] == 'completed'
    assert [s['commit_id'] for s in result['committed']] == [s['commit_id'] for s in rest]


def test_v1_contract_and_public_hash_stay_unextended():
    old = bundle(); original = canonical(public_plan(old))
    validate_bundle(old)
    assert canonical(public_plan(old)) == original
    assert 'handoff_kind' not in old and all('role' not in s for s in old['stages'])


def test_retained_clarification_rebinds_preimage_without_replaying_commits():
    from verification_support.bundle_contract import validate_continuation
    from test_apply_mixed_bundle_right import correction
    previous, progress, value = correction('DECISION')
    first = value['stages'][0]
    first['before'] = dict(first['after'])
    assert validate_continuation(previous, progress, value) == value
    backend = Backend()
    final = run_bundle(value, backend)
    assert [s['commit_id'] for s in final['committed']] == progress['remaining_commit_ids']
    assert backend.calls == [(action, name) for name in progress['remaining_commit_ids']
                             for action in ('install', 'test', 'commit')]
    assert first['after'] == previous['stages'][0]['after']
