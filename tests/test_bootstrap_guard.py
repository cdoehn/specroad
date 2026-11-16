"""Guard admission, owner uncertainty and exact preservation at real boundaries."""
import json
from pathlib import Path
import pytest
from specroad.authoring import bootstrap_guard as guard
from specroad.authoring.initialization import initialize_project
from specroad.authoring._bootstrap_io import BootstrapError
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.cli.application import dispatch_result
from specroad.storage.project import ProjectSource
from support.read_only import inventory,no_write_attempts


def interrupted(root,monkeypatch,point='marker_synced'):
    seen=[]
    def stop(event):
        if event==point:seen.append(event);raise OSError('native bootstrap interruption')
    with monkeypatch.context() as patch:
        patch.setattr(guard,'_checkpoint',stop)
        with pytest.raises(BootstrapError):initialize_project(root)
    assert seen==[point]


@pytest.mark.parametrize('exists',[False,True])
def test_pre_guard_failure_has_no_target_or_marker_effect(tmp_path,monkeypatch,exists):
    root=tmp_path/'target'
    if exists:root.mkdir();(root/'foreign').write_bytes(b'unchanged')
    before=inventory(tmp_path)
    interrupted(root,monkeypatch,'before_marker')
    assert inventory(tmp_path)==before


@pytest.mark.parametrize('point',['owner_synced','marker_synced','target_verified',
    'before_marker_unlink','marker_unlinked','marker_removed'])
@pytest.mark.parametrize('exists',[False,True])
def test_every_guard_boundary_blocks_missing_and_existing_root(tmp_path,monkeypatch,point,exists):
    root=tmp_path/'target'
    if exists:root.mkdir()
    interrupted(root,monkeypatch,point)
    before=inventory(tmp_path)
    with no_write_attempts():
        state=guard.observe_bootstrap(root)
        retry=dispatch_result(['init',str(root)])
        read=dispatch_result(['validate','--project',str(root)])
    assert state['state']=='corrupted' and state['manual_git_restore_required']
    assert retry.exit_code==5 and read.exit_code==5
    assert inventory(tmp_path)==before
    with no_write_attempts(),pytest.raises(BootstrapError):ProjectSource(root)
    assert inventory(tmp_path)==before


@pytest.mark.parametrize('damage',['missing-owner','missing-marker','invalid-json','unknown-field',
    'unknown-version','owner-type','wrong-parent','wrong-target','link','hardlink','mode'])
def test_malformed_or_incomplete_protection_never_authorizes_changes(tmp_path,monkeypatch,damage):
    root=tmp_path/'target';interrupted(root,monkeypatch)
    pending,owner=(tmp_path/n for n in guard.names(root))
    if damage.startswith('missing-'):(owner if damage=='missing-owner' else pending).unlink()
    elif damage=='invalid-json':pending.write_bytes(b'{')
    elif damage in ('link','hardlink'):
        import os
        original=tmp_path/'foreign';original.write_bytes(pending.read_bytes());pending.unlink()
        if damage=='link':pending.symlink_to(original)
        else:os.link(original,pending)
    elif damage=='mode':pending.chmod(0o666)
    else:
        value=json.loads(pending.read_bytes())
        if damage=='unknown-field':value['permission']=True
        elif damage=='unknown-version':value['format_version']='other'
        elif damage=='owner-type':value['owner']['lock_id']={}
        elif damage=='wrong-parent':value['parent_identity'][1]+=1
        else:value['target_name']='another-root'
        pending.write_bytes(jcs(value))
    before=inventory(tmp_path)
    with no_write_attempts():
        assert guard.observe_bootstrap(root)['state']=='corrupted'
        assert dispatch_result(['init',str(root)]).exit_code==5
    assert inventory(tmp_path)==before


def test_live_owner_requires_actual_parent_mutex_and_never_grants_read_permission(tmp_path,monkeypatch):
    root=tmp_path/'target';observed=[]
    def see(point):
        if point=='marker_synced':observed.append(guard.observe_bootstrap(root))
    monkeypatch.setattr(guard,'_checkpoint',see)
    initialize_project(root)
    assert len(observed)==1 and observed[0]['state']=='writer_active'
    assert observed[0]['observation_only'] and not observed[0]['write_authorized']
    assert guard.observe_bootstrap(root)['state']=='clean'


@pytest.mark.parametrize('which',['marker','owner'])
def test_recreated_marker_after_unlink_cannot_escape_late_validation(tmp_path,monkeypatch,which):
    root=tmp_path/'target';saved={};seen=[]
    names=guard.names(root)
    def replace(point):
        if point=='target_verified':
            saved.update({n:(tmp_path/n).read_bytes() for n in names})
        if point==('marker_unlinked' if which=='marker' else 'owner_removed'):
            name=names[0 if which=='marker' else 1]
            (tmp_path/name).write_bytes(saved[name]);seen.append(point)
    with monkeypatch.context() as patch:
        patch.setattr(guard,'_checkpoint',replace)
        with pytest.raises(BootstrapError):initialize_project(root)
    assert seen
    before=inventory(tmp_path)
    with no_write_attempts():assert dispatch_result(['init',str(root)]).exit_code==5
    assert inventory(tmp_path)==before


def test_completed_init_repeat_is_passive_including_file_identities(tmp_path):
    root=tmp_path/'target';first=initialize_project(root);before=inventory(tmp_path)
    inodes={p:p.stat().st_ino for p in root.rglob('*')}
    with no_write_attempts():assert initialize_project(root)==first
    assert inventory(tmp_path)==before and all(p.stat().st_ino==i for p,i in inodes.items())


@pytest.mark.parametrize('which',[0,1])
def test_guard_record_change_at_unlink_boundary_is_preserved(tmp_path,monkeypatch,which):
    root=tmp_path/'target';changed=tmp_path/guard.names(root)[which];raw=b'foreign changed protection';seen=[]
    def replace(point):
        if point=='before_marker_unlink':changed.write_bytes(raw);seen.append(point)
    with monkeypatch.context() as patch:
        patch.setattr(guard,'_checkpoint',replace)
        with pytest.raises(BootstrapError):initialize_project(root)
    assert seen==['before_marker_unlink'] and changed.read_bytes()==raw
    before=inventory(tmp_path)
    with no_write_attempts():assert dispatch_result(['init',str(root)]).exit_code==5
    assert inventory(tmp_path)==before
