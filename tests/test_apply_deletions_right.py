"""Deletion boundary failures preserve foreign bytes and the exact open intent."""
import base64
from copy import deepcopy
from hashlib import sha256
import os

import pytest

from apply_deletion_support import deletion_bundle, git_apply, empty_source, regular_file
from verification_support.bundle_apply import run_bundle, delete_bound_file
from verification_support.bundle_contract import validate_bundle, validate_continuation, public_plan
from verification_support.bundle_prepare import prepare_stage
from test_apply_commit_plan import make_plan


@pytest.mark.parametrize('fault', ['missing-bytes','hash','legacy','clarification','absent','overlap',
    'traversal','empty','file-parent','padding','selected-retired','empty-selection'])
def test_ambiguous_deletion_is_rejected_before_any_backend_work(fault):
    data = deletion_bundle(); stage = data['stages'][0]
    if fault == 'missing-bytes': stage.pop('delete_preimages')
    elif fault == 'hash': stage['delete_preimages']['gone.py'] = base64.b64encode(b'other').decode()
    elif fault == 'legacy': data['format_version']=1; data.pop('handoff_kind'); stage.pop('role')
    elif fault == 'clarification': stage['role']='clarification'
    elif fault == 'absent': stage['before']={}
    elif fault == 'overlap': stage['after']=dict(stage['deletions']); stage['payloads']=dict(stage['delete_preimages'])
    elif fault == 'traversal':
        for key in ('before','deletions','delete_preimages'): stage[key]={'../gone.py':stage[key]['gone.py']}
    elif fault == 'empty': stage['deletions']={}; stage['delete_preimages']={}
    elif fault == 'file-parent':
        stage['after']={'gone.py/child':sha256(b'x').hexdigest()}; stage['payloads']={'gone.py/child':'eA=='}
    elif fault == 'padding': stage['delete_preimages']['gone.py'] += '='
    elif fault == 'selected-retired': stage['test_plan']['test_files']=['gone.py']
    else: stage['test_plan'].update(test_files=[],test_ids=[])
    with pytest.raises((ValueError, TypeError)): validate_bundle(data)


@pytest.mark.parametrize('fault', ['mode','symlink','hardlink','directory','fifo','parent-link','bytes'])
def test_deletion_refuses_unsafe_leaf_or_parent_without_removing_other_data(tmp_path, fault):
    parent=tmp_path/'parent'; parent.mkdir()
    outside=tmp_path/'outside'; outside.mkdir(); regular_file(outside/'leaf', b'original\n')
    leaf=parent/'leaf'
    if fault == 'symlink': leaf.symlink_to(outside/'leaf')
    elif fault == 'hardlink': leaf.hardlink_to(outside/'leaf')
    elif fault == 'directory': leaf.mkdir()
    elif fault == 'fifo': os.mkfifo(leaf)
    elif fault == 'parent-link': parent.rmdir(); parent.symlink_to(outside,target_is_directory=True)
    else:
        regular_file(leaf, b'other' if fault == 'bytes' else b'original\n')
        if fault == 'mode': leaf.chmod(0o755)
    with pytest.raises((ValueError,OSError)):
        delete_bound_file(tmp_path,'parent/leaf',sha256(b'original\n').hexdigest())
    assert os.path.lexists(leaf) and (outside/'leaf').read_bytes()==b'original\n'


@pytest.mark.parametrize('parent_swap',[False,True])
def test_inode_or_parent_replacement_during_read_never_unlinks_foreign_file(tmp_path,monkeypatch,parent_swap):
    parent=tmp_path/'parent'; parent.mkdir(); regular_file(parent/'leaf', b'original\n')
    real_read=os.read; changed=False
    def replace_after_read(fd,size):
        nonlocal changed
        raw=real_read(fd,size)
        if raw and not changed:
            changed=True
            if parent_swap:
                parent.rename(tmp_path/'retained-parent'); parent.mkdir()
            else: (parent/'leaf').unlink()
            regular_file(parent/'leaf', b'foreign\n')
        return raw
    monkeypatch.setattr(os,'read',replace_after_read)
    with pytest.raises(ValueError):
        delete_bound_file(tmp_path,'parent/leaf',sha256(b'original\n').hexdigest())
    assert changed
    assert (parent/'leaf').read_bytes()==b'foreign\n'


def test_reappearing_deleted_file_prevents_commit_after_gate(tmp_path, monkeypatch):
    backend=git_apply(tmp_path); original=backend.head(); real_test=backend.test
    def gate(stage,head):
        proof=real_test(stage,head); regular_file(backend.root/'gone.py', b'foreign\n'); return proof
    monkeypatch.setattr(backend,'test',gate)
    with pytest.raises(ValueError): run_bundle(backend.data,backend)
    assert backend.head()==original and (backend.root/'gone.py').read_bytes()==b'foreign\n'
    assert backend.events[-1]['remaining_commit_ids']==['step.W']


def test_correction_cannot_drop_a_tombstone_or_invent_an_absent_one(tmp_path):
    backend=git_apply(tmp_path); backend.fail_gate=True
    with pytest.raises(ValueError): run_bundle(backend.data,backend)
    data=deepcopy(backend.data); data['initial_dirty']=True
    data['correction_of']={'plan_sha256':backend.events[-1]['plan_sha256'],'remaining_commit_ids':['step.W']}
    stage=data['stages'][0]; stage['before']={}
    assert validate_continuation(public_plan(backend.data),backend.events[-1],data)==data
    # A replacement tombstone must not erase the original open deletion.
    for key in ('deletions','delete_preimages'): stage[key]={'invented.py':stage[key]['gone.py']}
    with pytest.raises(ValueError): validate_continuation(public_plan(backend.data),backend.events[-1],data)


def test_preparation_refuses_linked_preimage_even_for_absent_final(tmp_path):
    before,after=tmp_path/'before',tmp_path/'after'; empty_source(before);empty_source(after)
    other=tmp_path/'source';other.write_bytes(b'original\n');(before/'gone.py').symlink_to(other)
    with pytest.raises((ValueError,OSError)):
        prepare_stage(before,after,['gone.py'],commit_id='step.W',message='Bound deletion',
                      test_plan=make_plan(['surviving']),role='implementation')
    assert other.read_bytes()==b'original\n'


def test_native_capability_requires_both_current_bytes_and_bound_committed_marker(tmp_path):
    import subprocess
    from verification_support.bundle_contract import canonical, DELETION_CAPABILITY, DELETION_CAPABILITY_PATH
    backend=git_apply(tmp_path)
    marker=backend.root/DELETION_CAPABILITY_PATH;marker.parent.mkdir()
    marker.write_bytes(canonical(DELETION_CAPABILITY)+b'\n')
    with pytest.raises(subprocess.CalledProcessError):backend.require_deletion_support()
    backend.git('add','--',DELETION_CAPABILITY_PATH);backend.git('commit','-m','fixture capability')
    backend.data['binding']['base_commit']=backend.head()
    backend.require_deletion_support()
    marker.write_bytes(b'{}\n')
    with pytest.raises(ValueError):backend.require_deletion_support()
    assert (backend.root/'gone.py').read_bytes()==b'original\n'


def test_partial_unlink_failure_retains_actual_state_for_exact_correction(tmp_path,monkeypatch):
    backend=git_apply(tmp_path)
    regular_file(backend.root/'other.py', b'second\n')
    backend.git('add','--','other.py');backend.git('commit','-m','fixture second target')
    backend.data['binding']['base_commit']=backend.head();original=backend.head()
    stage=backend.data['stages'][0]
    stage['deletions']['other.py']=sha256(b'second\n').hexdigest()
    stage['before']['other.py']=stage['deletions']['other.py']
    stage['delete_preimages']['other.py']=base64.b64encode(b'second\n').decode()
    real_unlink=os.unlink
    def fail_second(name,**kwargs):
        if name=='other.py': raise OSError('fixture disk failure')
        return real_unlink(name,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(os,'unlink',fail_second)
        with pytest.raises(OSError):run_bundle(backend.data,backend)
    assert backend.head()==original and not backend.gates
    assert not (backend.root/'gone.py').exists() and (backend.root/'other.py').read_bytes()==b'second\n'
    old=public_plan(backend.data);progress=backend.events[-1]
    correction=deepcopy(backend.data);correction.update(initial_dirty=True,
        correction_of={'plan_sha256':progress['plan_sha256'],'remaining_commit_ids':['step.W']})
    correction['stages'][0]['before'].pop('gone.py')
    validate_continuation(old,progress,correction)
    backend.data=correction
    assert run_bundle(correction,backend)['phase']=='completed'
    assert not (backend.root/'other.py').exists()


def test_existing_nonexecutable_write_preimages_keep_their_legacy_permissions_contract(tmp_path):
    before,after=tmp_path/'before',tmp_path/'after';empty_source(before);empty_source(after)
    for root,raw in ((before,b'old'),(after,b'new')):
        path=root/'ordinary.py';path.write_bytes(raw);path.chmod(0o600)
    stage=prepare_stage(before,after,['ordinary.py'],commit_id='step.W',message='Ordinary write',
                        test_plan=make_plan(['surviving']))
    assert 'deletions' not in stage and stage['before']['ordinary.py']==sha256(b'old').hexdigest()
    assert base64.b64decode(stage['payloads']['ordinary.py'])==b'new'
