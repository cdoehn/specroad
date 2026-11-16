"""Explicit deletion bytes, surviving mandatory tests and actual Apply commit order."""
import base64
from copy import deepcopy
from hashlib import sha256

import pytest

from apply_deletion_support import deletion_bundle, git_apply, empty_source, regular_file
from test_apply_commit_plan import bundle, make_plan
from verification_support.bundle_contract import validate_bundle, public_plan, remaining_commits
from verification_support.bundle_prepare import prepare_stage, render_entrypoint
from verification_support.bundle_apply import run_bundle, delete_bound_file
from verification_support.commit_tests import resolve_required


@pytest.mark.parametrize('raw', [b'', b'original\n', b'no newline', b'binary\0payload'])
def test_deletion_binds_full_preimage_and_public_plan_keeps_only_its_digest(raw):
    data = deletion_bundle(raw)
    assert validate_bundle(data) == data
    public = public_plan(data)['stages'][0]
    assert public['deletions'] == {'gone.py': sha256(raw).hexdigest()}
    assert 'delete_preimages' not in public and 'payloads' not in public
    assert base64.b64decode(data['stages'][0]['delete_preimages']['gone.py']) == raw


def test_existing_plan_format_and_public_hash_input_are_unchanged():
    data = bundle()
    assert validate_bundle(data) == data
    assert all('deletions' not in s for s in public_plan(data)['stages'])
    assert public_plan(data) == {**{k: v for k, v in data.items() if k not in ('stages','apply_repository')},
        'stages': [{k: v for k, v in s.items() if k != 'payloads'} for s in data['stages']]}


def test_prepare_deletion_keeps_surviving_regressions_and_never_selects_retired_file(tmp_path):
    before, after = tmp_path/'before', tmp_path/'after'
    for root in (before, after):
        empty_source(root)
    name = 'tests/test_retired.py'
    regular_file(before/name, b'def test_old(): pass\n')
    value = prepare_stage(before, after, [name], commit_id='DELETE.W', message='Delete bound legacy test',
        test_plan=make_plan(files=['tests/test_surviving.py']), role='implementation')
    assert value['after'] == {} and set(value['deletions']) == {name}
    assert value['test_plan']['test_files'] == ['tests/test_surviving.py']
    assert resolve_required(value['test_plan'], {'tests/test_surviving.py::test_new': 'surviving'})
    with pytest.raises(ValueError):
        prepare_stage(before, after, [name], commit_id='DELETE.W', message='Delete bound legacy test',
            test_plan=make_plan(files=[name]), role='implementation')


def test_prepare_absent_correction_requires_explicit_original_bytes(tmp_path):
    before, after = tmp_path/'before', tmp_path/'after'
    empty_source(before); empty_source(after)
    options = dict(commit_id='step.W', message='Retain deletion', test_plan=make_plan(['case.0']), role='implementation')
    with pytest.raises(ValueError):
        prepare_stage(before, after, ['gone.py'], **options)
    stage = prepare_stage(before, after, ['gone.py'], deletion_preimages={'gone.py': b'original\n'}, **options)
    data = deletion_bundle(); data['stages'] = [stage]
    with pytest.raises(ValueError): validate_bundle(data)
    data.update(initial_dirty=True, correction_of={'plan_sha256':'e'*64,'remaining_commit_ids':['step.W']})
    assert validate_bundle(data) == data and stage['before'] == {}


@pytest.mark.parametrize('raw', [b'', b'original\n', b'binary\0payload'])
def test_actual_git_deletion_is_gated_then_committed_and_surviving_file_is_preserved(tmp_path, raw):
    backend = git_apply(tmp_path, raw)
    original = backend.head()
    result = run_bundle(backend.data, backend)
    assert result['phase'] == 'completed' and backend.head() != original
    assert backend.gates == [(original, backend.data['stages'][0]['deletions'])]
    assert not (backend.root/'gone.py').exists()
    assert (backend.root/'survives.py').read_bytes() == b'keep\n'
    assert not backend.git('status','--porcelain')
    assert backend.git('diff','--name-status',original,'HEAD') == b'D\tgone.py\n'


def test_failed_gate_retains_deleted_state_and_resumes_the_same_uncommitted_stage(tmp_path):
    backend = git_apply(tmp_path)
    backend.fail_gate = True
    original = backend.head()
    with pytest.raises(ValueError): run_bundle(backend.data, backend)
    assert backend.head() == original and not (backend.root/'gone.py').exists()
    rest = remaining_commits(backend.plan, backend.events[-1], result_head=original)
    assert [s['commit_id'] for s in rest] == ['step.W']
    correction = deepcopy(backend.data)
    correction.update(initial_dirty=True, correction_of={
        'plan_sha256':backend.events[-1]['plan_sha256'], 'remaining_commit_ids':['step.W']})
    correction['stages'][0]['before'] = {}
    backend.data = correction; backend.fail_gate = False
    assert run_bundle(correction, backend)['phase'] == 'completed'


def test_already_staged_deletion_can_finish_without_unmatched_git_add(tmp_path):
    backend = git_apply(tmp_path)
    stage = backend.data['stages'][0]
    backend.before(stage, backend.head()); backend.install(stage)
    backend.git('add', '-A', '--', 'gone.py')
    backend.data.update(initial_dirty=True, correction_of={'plan_sha256':'f'*64,'remaining_commit_ids':['step.W']})
    stage['before'] = {}
    assert run_bundle(backend.data, backend)['phase'] == 'completed'


def test_primitive_deletes_only_the_requested_file_and_leaves_its_directory(tmp_path):
    folder = tmp_path/'folder'; folder.mkdir()
    regular_file(folder/'gone', b'old'); regular_file(folder/'keep', b'keep')
    delete_bound_file(tmp_path, 'folder/gone', sha256(b'old').hexdigest())
    assert folder.is_dir() and (folder/'keep').read_bytes() == b'keep'
    with pytest.raises(ValueError):
        delete_bound_file(tmp_path, 'folder/gone', sha256(b'old').hexdigest())


def test_deletion_entrypoint_is_self_contained_syntax_without_execution():
    raw = render_entrypoint(deletion_bundle(), core_python='/fixture/core/python')
    code = raw.split(b"<<'SPECROAD_APPLY_COMMIT_PLAN'\n",1)[1].rsplit(b'\nSPECROAD_APPLY_COMMIT_PLAN',1)[0]
    compile(code, '<prepared deletion driver>', 'exec')
    assert b'from .bundle_' not in code
