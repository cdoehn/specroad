"""Durable boundaries, abrupt exits and conservative, read-only observations."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import stat
from unittest.mock import patch
import pytest
from specroad.changes import (CommittingJournal, CommitPublicationError, PublicationAuthority,
    read_committing_journal, project_lock, begin_building_journal, stage_building_journal,
    prepare_publication_check, TargetModel, ProjectLockError)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.model_manifest import ProjectReadBinding
from specroad.storage.project import ProjectSource
from specroad.storage.read_only import validate_project_read_only
from support.committing import staged, publish
from support.publication import files, options, prepared, ALLOW, TRANSACTION
from support.folds import goal, edit, create
from support.domain import domain_value
from support.targets import model, plan, POLICY, ACTOR, TIME
from support.read_only import profile_resources, no_write_attempts, inventory
from support.processes import run_core, run_python
from support.portable import build_distribution


def disk(root, j):return json.loads((root/j.path).read_bytes())


def test_complete_journal_is_read_without_write_or_unlock(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        done=publish(f,j,h);before=inventory(tmp_path)
        with no_write_attempts():
            read=read_committing_journal(ProjectSource(tmp_path),TRANSACTION,
                 expected_sha256=done.data['journal_sha256'],preflight=f)
        assert inventory(tmp_path)==before and h.check()
        assert read.data['published_count']==1 and read.data['state']=='committing'
        assert not done.data['commit_completed']
        read.data['files'].clear()
        assert len(read.data['files'])==1


def test_completed_file_phase_still_blocks_normal_project_reads(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):publish(f,j,h)
    result=validate_project_read_only(tmp_path,profile_resources=profile_resources(),core_key='core@0.2.0')
    assert not result.passed and result.exit_code==5
    assert not result.data['model_loaded'] and result.data['operational']['recovery_required']
    assert disk(tmp_path,j)['state']=='committing'


@pytest.mark.parametrize('fail_at',range(1,16))
def test_each_file_and_journal_sync_failure_stops_without_cleanup(tmp_path,fail_at):
    a,b=goal(1),goal(2)
    with staged(tmp_path,artifacts=[a,b],operations=[edit(a,'A'),edit(b,'B')]) as (m,p,f,h,j):
        native_sync,native_replace=os.fsync,os.replace;calls=0;targets=[]
        def sync(fd):
            nonlocal calls
            calls+=1
            if calls==fail_at:raise OSError(5,'injected sync boundary')
            return native_sync(fd)
        def replace(src,dst,**kw):
            r=native_replace(src,dst,**kw)
            if dst!='journal.json':targets.append(dst)
            return r
        with patch.object(os,'fsync',side_effect=sync),patch.object(os,'replace',side_effect=replace):
            with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
        assert calls==fail_at and e.value.mutation_possible
        assert e.value.published_count<=len(targets)
        assert e.value.publication_possible==bool(targets)
        assert not e.value.diagnostic()['commit_completed']
        assert (tmp_path/j.path).exists()
        assert disk(tmp_path,j)['state'] in ('prepared','committing')
        for entry in j.data['files']:
            assert (tmp_path/entry['before_image_path']).read_bytes()==m.source_files[entry['path']]
        assert files(tmp_path) in (m.source_files,{**m.source_files,**{d.path:d.content for d in f.request.documents}}) or len(targets)==1


def test_short_journal_writes_are_completed(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        native=os.write
        with patch.object(os,'write',side_effect=lambda fd,data:native(fd,data[:11])):
            result=publish(f,j,h)
        assert result.data['all_files_published'] and disk(tmp_path,j)['published_count']==1


@pytest.mark.parametrize('count',[0,-1,True,None])
def test_invalid_short_write_never_starts_targets(tmp_path,count):
    with staged(tmp_path) as (m,p,f,h,j):
        with patch.object(os,'write',return_value=count):
            with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
        assert not e.value.publication_possible
        assert files(tmp_path)==m.source_files
        assert (tmp_path/Path(j.path).parent/'journal.next').is_file()


def test_lost_committing_rename_result_stops_before_targets(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        native=os.replace;count=0
        def rename(*args,**kw):
            nonlocal count
            count+=1;native(*args,**kw);raise OSError(5,'lost journal result')
        with patch.object(os,'replace',side_effect=rename):
            with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
        assert count==1 and files(tmp_path)==m.source_files
        assert not e.value.publication_possible and disk(tmp_path,j)['state']=='committing'
        r=read_committing_journal(ProjectSource(tmp_path),TRANSACTION,preflight=f)
        assert r.data['published_count']==0


def test_lost_acknowledgement_result_is_not_retried(tmp_path):
    a,b=goal(1),goal(2)
    with staged(tmp_path,artifacts=[a,b],operations=[edit(a,'A'),edit(b,'B')]) as (m,p,f,h,j):
        native=os.replace;targets=[]
        def rename(src,dst,**kw):
            value=native(src,dst,**kw)
            if dst!='journal.json':targets.append(dst)
            elif targets:raise OSError(5,'ack reply lost')
            return value
        with patch.object(os,'replace',side_effect=rename):
            with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
        assert len(targets)==1 and e.value.publication_possible
        assert disk(tmp_path,j)['published_count']==1
        observed=read_committing_journal(ProjectSource(tmp_path),TRANSACTION,preflight=f)
        assert observed.data['published_count']==1
        assert (tmp_path/j.data['files'][1]['path']).read_bytes()==m.source_files[j.data['files'][1]['path']]


def test_unacknowledged_move_is_refused_by_reader_not_repaired(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        native=os.replace
        def rename(src,dst,**kw):
            value=native(src,dst,**kw)
            if dst!='journal.json':raise OSError(5,'lost move')
            return value
        with patch.object(os,'replace',side_effect=rename):
            with pytest.raises(CommitPublicationError):publish(f,j,h)
        before=inventory(tmp_path)
        with pytest.raises(CommitPublicationError):
            read_committing_journal(ProjectSource(tmp_path),TRANSACTION,preflight=f)
        assert inventory(tmp_path)==before and disk(tmp_path,j)['published_count']==0


@pytest.mark.parametrize('damage',['extra-stage','extra-before','missing-before','target','hardlink','journal-next'])
def test_reader_rejects_inconsistent_complete_files(tmp_path,damage):
    with staged(tmp_path) as (m,p,f,h,j):publish(f,j,h)
    entry=j.data['files'][0];folder=tmp_path/Path(j.path).parent
    if damage=='extra-stage':(folder/'staging'/'extra').write_bytes(b'x')
    elif damage=='extra-before':(folder/'before'/'extra').write_bytes(b'x')
    elif damage=='missing-before':(tmp_path/entry['before_image_path']).unlink()
    elif damage=='journal-next':(folder/'journal.next').write_bytes(b'partial')
    elif damage=='target':
        path=tmp_path/entry['path'];old=path.stat();raw=path.read_bytes()
        path.write_bytes(b'X'+raw[1:]);os.utime(path,ns=(old.st_atime_ns,old.st_mtime_ns))
    else:os.link(tmp_path/entry['path'],tmp_path/'aliased')
    before=inventory(tmp_path)
    with pytest.raises(CommitPublicationError):read_committing_journal(ProjectSource(tmp_path),TRANSACTION)
    assert inventory(tmp_path)==before


def test_reader_rejects_other_project_instance(tmp_path):
    root=tmp_path/'first'
    with staged(root) as (m,p,f,h,j):publish(f,j,h)
    other=tmp_path/'copy';shutil.copytree(root,other)
    with pytest.raises(CommitPublicationError) as e:
        read_committing_journal(ProjectSource(other),TRANSACTION)
    assert e.value.reason=='committing_project_binding_mismatch'


def test_reader_expected_raw_digest_is_checked(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):publish(f,j,h)
    with pytest.raises(CommitPublicationError) as e:
        read_committing_journal(ProjectSource(tmp_path),TRANSACTION,expected_sha256='0'*64)
    assert e.value.reason=='committing_journal_bytes_changed'


@pytest.mark.parametrize('raw',[b'{}',b'{',b'[]',b'{} {}',b'\xff',b'{"state":"committing","state":"committed"}'])
def test_invalid_raw_records_have_controlled_errors(raw):
    with pytest.raises(CommitPublicationError):CommittingJournal(raw)


def test_acknowledgements_are_a_strict_canonical_prefix(tmp_path):
    a,b=goal(1),goal(2)
    with staged(tmp_path,artifacts=[a,b],operations=[edit(a,'A'),edit(b,'B')]) as (m,p,f,h,j):
        data=j.data;data.update(state='committing',published_count=1)
        data['files'][1]['published']=True
        with pytest.raises(CommitPublicationError) as e:CommittingJournal(canonical_json_bytes(data))
        assert e.value.reason=='publication_prefix_required'


def test_preserves_explicit_target_rwx_modes(tmp_path):
    m,p,f=prepared(tmp_path);target=tmp_path/next(d.path for d in f.request.documents)
    target.chmod(0o664);f=prepare_publication_check(p,m,policy=POLICY)
    with project_lock(tmp_path,**options(f)) as h:
        b=begin_building_journal(f,held_lock=h,transaction_id=TRANSACTION,authority=ALLOW)
        j=stage_building_journal(f,b,held_lock=h,authority=ALLOW)
        publish(f,j,h)
        assert stat.S_IMODE(target.stat().st_mode)==0o664
        assert stat.S_IMODE((tmp_path/j.data['files'][0]['before_image_path']).stat().st_mode)==0o600


def test_missing_target_parents_are_created_only_when_publishing(tmp_path):
    a=domain_value('need')
    value=goal(9,revision=1,created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR)
    with staged(tmp_path,artifacts=[a],operations=[create(value)]) as (m,p,f,h,j):
        target=tmp_path/j.data['files'][0]['path'];assert not target.parent.exists()
        publish(f,j,h)
        assert target.read_bytes()==f.request.documents[0].content
        assert target.parent.stat().st_dev==(tmp_path/Path(j.path).parent).stat().st_dev


def test_target_permissions_changed_during_authority_stop_before_mutation(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        calls=0;path=tmp_path/j.data['files'][0]['path']
        def auth(request):
            nonlocal calls
            calls+=1
            if calls==2:path.chmod(0o444)
            return True
        with pytest.raises(CommitPublicationError) as e:
            publish(f,j,h,authority=PublicationAuthority('change-mode','1',auth))
        assert not e.value.publication_possible and disk(tmp_path,j)['state']=='prepared'
        path.chmod(0o644)


def test_same_byte_image_replacement_during_authority_is_detected(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        calls=0;image=tmp_path/j.data['files'][0]['staging_path']
        def auth(request):
            nonlocal calls
            calls+=1
            if calls==2:
                raw=image.read_bytes();replacement=tmp_path/'replacement';replacement.write_bytes(raw)
                os.replace(replacement,image)
            return True
        with pytest.raises(CommitPublicationError) as e:
            publish(f,j,h,authority=PublicationAuthority('replace-image','1',auth))
        assert not e.value.publication_possible and files(tmp_path)==m.source_files


def test_no_following_file_after_unchanged_dependency_tampered(tmp_path):
    a,b,c=goal(1),goal(2),goal(3)
    with staged(tmp_path,artifacts=[a,b,c],operations=[edit(a,'A'),edit(b,'B')]) as (m,p,f,h,j):
        native=os.replace;calls=0
        untouched=next(d for d in m.documents if json.loads(d.content)['id']==c['id'])
        def rename(src,dst,**kw):
            nonlocal calls
            r=native(src,dst,**kw)
            if dst!='journal.json':
                calls+=1;path=tmp_path/untouched.path;raw=path.read_bytes();path.write_bytes(raw+b' ')
            return r
        with patch.object(os,'replace',side_effect=rename):
            with pytest.raises(CommitPublicationError):publish(f,j,h)
        assert calls==1 and disk(tmp_path,j)['published_count']==0
        assert (tmp_path/j.data['files'][1]['staging_path']).exists()


def test_both_before_images_and_remaining_stages_survive_real_child_crash(tmp_path):
    root=tmp_path/'project';root.mkdir()
    body=f'''import sys,os,json
sys.path.insert(0,{str(Path(__file__).parent.resolve())!r})
from pathlib import Path
from support.committing import staged,publish
from support.folds import goal,edit
root=Path({str(root)!r});a,b=goal(1),goal(2)
with staged(root,artifacts=[a,b],operations=[edit(a,'A'),edit(b,'B')]) as (m,p,f,h,j):
 (root.parent/'journalpath').write_text(j.path)
 native=os.replace
 def die(src,dst,**kw):
  r=native(src,dst,**kw)
  if dst!='journal.json':os._exit(41)
  return r
 os.replace=die
 publish(f,j,h)
'''
    result=run_core(body,tmp_path,capture=True)
    assert result.returncode==41,result.stderr
    path=(tmp_path/'journalpath').read_text();data=json.loads((root/path).read_bytes())
    assert data['state']=='committing' and data['published_count']==0
    assert len(list((root/Path(path).parent/'before').iterdir()))==2
    assert len(list((root/Path(path).parent/'staging').iterdir()))==1
    for i,e in enumerate(data['files']):
        assert sha256((root/e['path']).read_bytes()).hexdigest()==e['after_sha256' if i==0 else 'before_sha256']
    with pytest.raises(ProjectLockError):
        with project_lock(root,kind='writer',command='change apply',project_id='sample',
                          transaction_id=TRANSACTION,request_id='request-1'):pass
    status=validate_project_read_only(root,profile_resources=profile_resources(),core_key='core@0.2.0')
    assert status.exit_code==5 and not status.data['model_loaded']


def test_inherited_lock_never_publishes_for_parent(tmp_path):
    body=f'''import sys,os
sys.path.insert(0,{str(Path(__file__).parent.resolve())!r})
from pathlib import Path
from support.committing import staged,publish
from support.publication import files
from specroad.changes import CommitPublicationError
root=Path({str(tmp_path)!r})
with staged(root) as (m,p,f,h,j):
 pid=os.fork()
 if pid==0:
  try:publish(f,j,h)
  except CommitPublicationError:os._exit(0)
  except BaseException:os._exit(3)
  os._exit(2)
 _,status=os.waitpid(pid,0)
 assert os.waitstatus_to_exitcode(status)==0
 assert files(root)==m.source_files and (root/j.path).read_bytes()==j.source_bytes
 assert h.check()
'''
    result=run_core(body,tmp_path,capture=True)
    assert result.returncode==0,result.stderr


def test_many_files_all_acknowledged_and_rehashed(tmp_path):
    artifacts=[goal(i) for i in range(1,34)]
    with staged(tmp_path,artifacts=artifacts,operations=[edit(a,'new') for a in reversed(artifacts)]) as (m,p,f,h,j):
        r=publish(f,j,h)
        assert r.data['published_count']==33
        assert [e['path'] for e in disk(tmp_path,j)['files']]==sorted(d.path for d in f.request.documents)
        assert all(e['published'] for e in disk(tmp_path,j)['files'])
        assert r.data['target_model_root_sha256']==f.request.data['target_root_sha256']


def test_module_and_zipapp_publishing_and_reader_remain_portable(tmp_path):
    products=build_distribution(tmp_path/'distribution')
    for index,original in enumerate(products):
        moved=tmp_path/('moved-'+str(index)+('.pyz' if original.suffix=='.pyz' else ''))
        original.rename(moved);root=tmp_path/('project-'+str(index));root.mkdir()
        body=f'''import sys
sys.path[:0]=[{str(moved)!r},{str(Path(__file__).parent.resolve())!r}]
from pathlib import Path
from support.committing import staged,publish
from support.publication import TRANSACTION
from specroad.changes import read_committing_journal
from specroad.storage.project import ProjectSource
root=Path({str(root)!r})
with staged(root) as (m,p,f,h,j):
 r=publish(f,j,h)
 assert r.data['all_files_published'] and not r.data['commit_completed']
 assert read_committing_journal(ProjectSource(root),TRANSACTION,preflight=f).data['published_count']==1
'''
        result=run_python(['-I','-S','-B','-c',body],tmp_path,capture=True)
        assert result.returncode==0,result.stderr
