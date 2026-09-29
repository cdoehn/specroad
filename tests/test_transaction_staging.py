"""Real temporary-file effects, not output or documentation assertions."""
from hashlib import sha256
import copy
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from specroad.changes import (BuildingJournal, PreparedJournal, StagingError, JournalError,
    PublicationAuthority, project_lock, begin_building_journal, stage_building_journal,
    read_prepared_journal, verify_prepared_journal, prepare_building_journal)
from specroad.model.canonical import canonical_json_bytes
from specroad.storage.project import ProjectSource
from support.publication import prepared, options, files, ALLOW, TRANSACTION
from support.folds import goal, create, edit
from support.targets import ACTOR, TIME


def begin(c,h):
    return begin_building_journal(c,held_lock=h,transaction_id=TRANSACTION,authority=ALLOW)


def finish(c,j,h,**kw):
    return stage_building_journal(c,j,held_lock=h,authority=kw.pop('authority',ALLOW),**kw)


def test_prepare_writes_images_and_only_changes_journal_state(tmp_path):
    m,p,c=prepared(tmp_path);original=files(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h);v=finish(c,j,h)
        expected=j.data;expected['state']='prepared'
        assert v.data==expected and v.data['published_count']==0
        assert verify_prepared_journal(v,c) is None
        assert (tmp_path/v.path).read_bytes()==v.source_bytes
        for e in v.data['files']:
            assert (tmp_path/e['staging_path']).read_bytes()==c.request.documents[0].content
            assert (tmp_path/e['before_image_path']).read_bytes()==m.source_files[e['path']]
            assert not e['published']
        assert read_prepared_journal(ProjectSource(tmp_path),TRANSACTION,expected_sha256=v.sha256,preflight=c).data==v.data
        assert h.check()
    assert files(tmp_path)==original
    assert not (tmp_path/'.specroad/locks/project.json').exists()


def test_new_file_has_no_before_image(tmp_path):
    a=goal(2,revision=1,created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR)
    m,p,c=prepared(tmp_path,operations=[create(a)])
    with project_lock(tmp_path,**options(c)) as h:
        j=finish(c,begin(c,h),h);e=j.data['files'][0]
        assert e['before_image_path'] is None and e['before_sha256'] is None
        assert (tmp_path/e['staging_path']).is_file()
        assert list((tmp_path/Path(j.path).parent/'before').iterdir())==[]
        assert not (tmp_path/e['path']).exists()


def test_noop_prepared_has_no_phantom_images(tmp_path):
    m,p,c=prepared(tmp_path,operations=[])
    with project_lock(tmp_path,**options(c)) as h:
        j=finish(c,begin(c,h),h)
        assert j.data['files']==[] and j.data['published_count']==0
        assert read_prepared_journal(ProjectSource(tmp_path),TRANSACTION,preflight=c).data==j.data
    assert files(tmp_path)==m.source_files


def test_multiple_changes_bind_all_bytes(tmp_path):
    a,b=goal(1),goal(2)
    m,p,c=prepared(tmp_path,artifacts=[a,b],operations=[edit(b,'two'),edit(a,'one')])
    with project_lock(tmp_path,**options(c)) as h:
        j=finish(c,begin(c,h),h)
        assert len(j.data['files'])==2
        for e in j.data['files']:
            for pk,sk,hk in [('staging_path','after_size','after_sha256'),('before_image_path','before_size','before_sha256')]:
                b=(tmp_path/e[pk]).read_bytes()
                assert len(b)==e[sk] and sha256(b).hexdigest()==e[hk]
    assert files(tmp_path)==m.source_files


def test_value_independence_and_no_success_coercion(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:j=finish(c,begin(c,h),h)
    raw=json.dumps(j.data,indent=2).encode();v=PreparedJournal(raw)
    data=v.data;data['files'][0]['published']=True
    assert v.source_bytes==raw and v.sha256==sha256(raw).hexdigest()
    assert copy.deepcopy(v).data==j.data and verify_prepared_journal(v,c) is None
    with pytest.raises(TypeError):bool(v)
    with pytest.raises(JournalError):BuildingJournal(v.source_bytes)


@pytest.mark.parametrize('field,value',[('state','building'),('state','committing'),('published_count',1),('published_count',True),('extra',True)])
def test_codec_rejects_wrong_state_and_publication(tmp_path,field,value):
    m,p,c=prepared(tmp_path)
    v=prepare_building_journal(c,transaction_id=TRANSACTION).data
    v['state']='prepared';v[field]=value
    with pytest.raises(JournalError):PreparedJournal(canonical_json_bytes(v))


def test_self_consistent_missing_inventory_is_not_a_proof(tmp_path):
    m,p,c=prepared(tmp_path)
    v=prepare_building_journal(c,transaction_id=TRANSACTION).data;v.update(state='prepared',files=[])
    with pytest.raises(StagingError) as e:verify_prepared_journal(PreparedJournal(canonical_json_bytes(v)),c)
    assert e.value.exit_code==6


def test_authority_denial_preserves_building(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h)
        with pytest.raises(StagingError) as e:finish(c,j,h,authority=PublicationAuthority('deny','1',lambda r:False))
        assert e.value.exit_code==7 and not e.value.mutation_possible
        assert (tmp_path/j.path).read_bytes()==j.source_bytes
        assert sorted(f.name for f in (tmp_path/j.path).parent.iterdir())==['journal.json']
    assert files(tmp_path)==m.source_files


def test_existing_staging_is_not_reused_or_deleted(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h);d=tmp_path/Path(j.path).parent/'staging';d.mkdir();(d/'kept').write_bytes(b'recovery')
        with pytest.raises(StagingError):finish(c,j,h)
        assert (d/'kept').read_bytes()==b'recovery'
        assert BuildingJournal((tmp_path/j.path).read_bytes()).data['state']=='building'


def test_saved_prepared_marker_does_not_prove_images(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h);v=j.data;v['state']='prepared';(tmp_path/j.path).write_bytes(canonical_json_bytes(v))
        with pytest.raises(StagingError):read_prepared_journal(ProjectSource(tmp_path),TRANSACTION)


def test_expired_writer_handle_is_refused(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:j=begin(c,h)
    with pytest.raises(StagingError) as e:finish(c,j,h)
    assert e.value.exit_code==7 and files(tmp_path)==m.source_files


def test_wrong_plan_binding_cannot_stage(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h);v=j.data;v['plan_sha256']='0'*64
        with pytest.raises(JournalError):finish(c,BuildingJournal(canonical_json_bytes(v)),h)
        assert sorted(f.name for f in (tmp_path/j.path).parent.iterdir())==['journal.json']


def test_changed_source_refuses_before_payload_creation(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h);f=tmp_path/m.documents[0].path;f.write_bytes(f.read_bytes()+b' ')
        with pytest.raises(StagingError) as e:finish(c,j,h)
        assert e.value.exit_code==6 and not e.value.mutation_possible
        assert not (tmp_path/Path(j.path).parent/'staging').exists()


def test_images_and_parents_synced_before_prepared_replace(tmp_path):
    m,p,c=prepared(tmp_path);synced=set();real=os.fsync;replace=os.replace
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h)
        def sync(fd):
            real(fd);synced.add(os.readlink('/proc/self/fd/'+str(fd)))
        def rename(src,dst,**kw):
            for e in j.data['files']:
                assert str(tmp_path/e['staging_path']) in synced
                assert str(tmp_path/e['before_image_path']) in synced
            for name in ('staging','before','journal.prepared'):
                assert str(tmp_path/Path(j.path).parent/name) in synced
            return replace(src,dst,**kw)
        with patch.object(os,'fsync',side_effect=sync),patch.object(os,'replace',side_effect=rename):v=finish(c,j,h)
    assert v.data['state']=='prepared' and files(tmp_path)==m.source_files


def test_read_is_read_only_and_requires_matching_hash(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:j=finish(c,begin(c,h),h)
    before={f.relative_to(tmp_path).as_posix():f.read_bytes() for f in tmp_path.rglob('*') if f.is_file()}
    with patch.object(os,'write',side_effect=AssertionError('write')),patch.object(os,'mkdir',side_effect=AssertionError('mkdir')):
        assert read_prepared_journal(ProjectSource(tmp_path),TRANSACTION,preflight=c).data==j.data
        with pytest.raises(StagingError):read_prepared_journal(ProjectSource(tmp_path),TRANSACTION,expected_sha256='0'*64)
    assert before=={f.relative_to(tmp_path).as_posix():f.read_bytes() for f in tmp_path.rglob('*') if f.is_file()}


@pytest.mark.parametrize('errno_value',[13,28,5])
def test_write_failures_never_publish_a_normative_file(tmp_path,errno_value):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h)
        with patch.object(os,'write',side_effect=OSError(errno_value,'injected')):
            with pytest.raises(StagingError) as e:finish(c,j,h)
        assert e.value.mutation_possible and not e.value.prepared_possible
        assert (tmp_path/j.path).read_bytes()==j.source_bytes
    assert files(tmp_path)==m.source_files


def test_late_authority_denial_keeps_images_and_building(tmp_path):
    m,p,c=prepared(tmp_path);count=0
    def authorize(request):
        nonlocal count
        count+=1
        return count==1
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h)
        with pytest.raises(StagingError) as e:finish(c,j,h,authority=PublicationAuthority('change','1',authorize))
        assert e.value.mutation_possible and (tmp_path/j.path).read_bytes()==j.source_bytes
        assert (tmp_path/j.data['files'][0]['staging_path']).exists()
    assert count==2 and files(tmp_path)==m.source_files


def test_modified_image_during_last_authorization_is_refused(tmp_path):
    m,p,c=prepared(tmp_path);count=0
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h)
        def authorize(request):
            nonlocal count
            count+=1
            if count==2:
                f=tmp_path/j.data['files'][0]['staging_path'];b=f.read_bytes();f.write_bytes(b'X'+b[1:])
            return True
        with pytest.raises(StagingError) as e:finish(c,j,h,authority=PublicationAuthority('tamper','1',authorize))
        assert e.value.exit_code==6 and (tmp_path/j.path).read_bytes()==j.source_bytes
    assert files(tmp_path)==m.source_files


def test_fsync_failure_after_journal_replace_is_not_success_or_rollback(tmp_path):
    m,p,c=prepared(tmp_path);real=os.fsync;replaced=False;rename=os.replace
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h)
        def replace(*a,**kw):
            nonlocal replaced
            r=rename(*a,**kw);replaced=True;return r
        def sync(fd):
            if replaced:raise OSError(5,'injected post-replace fsync')
            return real(fd)
        with patch.object(os,'replace',side_effect=replace),patch.object(os,'fsync',side_effect=sync):
            with pytest.raises(StagingError) as e:finish(c,j,h)
        assert e.value.prepared_possible and e.value.mutation_possible
        assert PreparedJournal((tmp_path/j.path).read_bytes()).data['state']=='prepared'
    assert files(tmp_path)==m.source_files
