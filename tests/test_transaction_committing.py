"""Real atomic file effects and durable journal sequence, never console snapshots."""
import copy
from hashlib import sha256
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from specroad.changes import (CommittingJournal, CommitPublicationError, PreparedJournal,
    JournalError, PublicationAuthority, verify_committing_journal,
    prepare_building_journal, prepare_publication_check)
from specroad.model.canonical import canonical_json_bytes
from support.committing import staged, publish
from support.publication import files
from support.folds import goal, create, edit
from support.targets import ACTOR, TIME, POLICY


def record(root, journal):
    return json.loads((root / journal.path).read_bytes())


def test_all_targets_and_live_root_match_request(tmp_path):
    a,b,c = goal(1),goal(2),goal(3)
    with staged(tmp_path, artifacts=[a,b,c], operations=[edit(b,'second'),edit(a,'first')]) as (m,p,f,h,j):
        original = files(tmp_path)
        expected = {**original, **{d.path:d.content for d in f.request.documents}}
        result = publish(f,j,h)
        assert files(tmp_path) == expected
        assert result.data['all_files_published'] and result.data['target_root_verified']
        assert result.data['target_model_root_sha256'] == f.request.data['target_root_sha256']
        v = CommittingJournal((tmp_path/j.path).read_bytes())
        assert verify_committing_journal(v,f) is None
        assert v.data['published_count'] == 2 and all(e['published'] for e in v.data['files'])
        assert h.check()


def test_receipt_and_committed_marker_are_not_fabricated(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        r = publish(f,j,h)
        assert r.data['state'] == 'committing'
        assert r.data['receipt_written'] is False and r.data['commit_completed'] is False
        assert r.data['finalization_required'] is True
        assert not (tmp_path/'.specroad/transactions/receipts').exists()
        assert record(tmp_path,j)['state'] == 'committing'
        with pytest.raises(TypeError): bool(r)


def test_before_images_retained_staging_consumed(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        publish(f,j,h)
        for e in j.data['files']:
            assert (tmp_path/e['before_image_path']).read_bytes() == m.source_files[e['path']]
            assert not (tmp_path/e['staging_path']).exists()
        assert (tmp_path/j.path).is_file()
        assert sorted(q.name for q in (tmp_path/Path(j.path).parent).iterdir()) == ['before','journal.json','staging']


def test_empty_write_set_still_has_committing_journal(tmp_path):
    with staged(tmp_path,operations=[]) as (m,p,f,h,j):
        r=publish(f,j,h)
        assert r.data['published_count']==0
        assert files(tmp_path)==m.source_files
        assert record(tmp_path,j)['state']=='committing'


def test_create_has_exact_bytes_and_no_before_image(tmp_path):
    value=goal(9,revision=1,created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR)
    with staged(tmp_path,operations=[create(value)]) as (m,p,f,h,j):
        e=j.data['files'][0];assert not (tmp_path/e['path']).exists()
        publish(f,j,h)
        assert (tmp_path/e['path']).read_bytes()==f.request.documents[0].content
        assert e['before_image_path'] is None
        assert (tmp_path/e['path']).stat().st_mode & 0o777 == 0o644


def test_committing_is_durable_before_target_and_ack_before_next(tmp_path):
    a,b=goal(1),goal(2)
    with staged(tmp_path,artifacts=[a,b],operations=[edit(b,'B'),edit(a,'A')]) as (m,p,f,h,j):
        original_replace, original_sync=os.replace,os.fsync
        persisted=[];published=[]
        journal_dir=tmp_path/Path(j.path).parent
        def sync(fd):
            original_sync(fd)
            if os.readlink('/proc/self/fd/'+str(fd))==str(journal_dir):
                persisted.append(record(tmp_path,j))
        def rename(src,dst,**kw):
            if dst!='journal.json':
                disk=record(tmp_path,j)
                assert disk['state']=='committing'
                assert disk['published_count']==len(published)
                assert persisted and persisted[-1]==disk
                published.append(dst)
            return original_replace(src,dst,**kw)
        with patch.object(os,'fsync',side_effect=sync),patch.object(os,'replace',side_effect=rename):
            publish(f,j,h)
        assert published==[Path(e['path']).name for e in j.data['files']]
        assert persisted[-1]['published_count']==2


def test_target_file_replacement_is_atomic_for_open_reader(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        path=tmp_path/j.data['files'][0]['path']
        with path.open('rb') as old:
            before=path.read_bytes()
            publish(f,j,h)
            assert old.read()==before
            assert path.read_bytes()==f.request.documents[0].content


def test_stale_source_is_rejected_before_committing(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        path=tmp_path/j.data['files'][0]['path'];path.write_bytes(path.read_bytes()+b' ')
        with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
        assert not e.value.publication_possible
        assert record(tmp_path,j)['state']=='prepared'


def test_authorization_denial_does_not_start_publication(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        with pytest.raises(CommitPublicationError) as e:
            publish(f,j,h,authority=PublicationAuthority('deny','1',lambda r:False))
        assert e.value.exit_code==7 and files(tmp_path)==m.source_files
        assert (tmp_path/j.path).read_bytes()==j.source_bytes


def test_missing_lock_rejected(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j): pass
    with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
    assert e.value.exit_code==7 and not e.value.publication_possible


def test_reusing_old_prepared_cannot_write_twice(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        publish(f,j,h);before=files(tmp_path);raw=(tmp_path/j.path).read_bytes()
        with pytest.raises(CommitPublicationError):publish(f,j,h)
        assert files(tmp_path)==before and (tmp_path/j.path).read_bytes()==raw


def test_additional_recovery_entry_prevents_any_target_write(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        extra=tmp_path/'.specroad/transactions/other';extra.mkdir()
        with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
        assert e.value.exit_code==5 and files(tmp_path)==m.source_files
        assert extra.is_dir()


@pytest.mark.parametrize('key',['staging_path','before_image_path'])
def test_corrupt_required_image_is_not_published(tmp_path,key):
    with staged(tmp_path) as (m,p,f,h,j):
        path=tmp_path/j.data['files'][0][key];raw=path.read_bytes()
        path.write_bytes(b'X'+raw[1:])
        with pytest.raises(CommitPublicationError):publish(f,j,h)
        assert files(tmp_path)==m.source_files and record(tmp_path,j)['state']=='prepared'


def test_changed_journal_not_overwritten(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        path=tmp_path/j.path;path.write_bytes(path.read_bytes()+b' ');raw=path.read_bytes()
        with pytest.raises(CommitPublicationError):publish(f,j,h)
        assert path.read_bytes()==raw and files(tmp_path)==m.source_files


@pytest.mark.parametrize('code',[5,13,28])
def test_initial_journal_write_failure_preserves_prepared(tmp_path,code):
    with staged(tmp_path) as (m,p,f,h,j):
        with patch.object(os,'write',side_effect=OSError(code,'injected')):
            with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
        assert e.value.mutation_possible and not e.value.publication_possible
        assert record(tmp_path,j)['state']=='prepared' and files(tmp_path)==m.source_files
        assert (tmp_path/Path(j.path).parent/'journal.next').exists()


def test_committing_fsync_failure_prevents_first_target(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        native=os.fsync
        def sync(fd):
            if record(tmp_path,j)['state']=='committing':raise OSError(5,'injected')
            return native(fd)
        with patch.object(os,'fsync',side_effect=sync):
            with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
        assert files(tmp_path)==m.source_files and not e.value.publication_possible
        assert record(tmp_path,j)['state']=='committing'


def test_lost_target_rename_result_has_no_retry_or_false_rollback(tmp_path):
    a,b=goal(1),goal(2)
    with staged(tmp_path,artifacts=[a,b],operations=[edit(a,'A'),edit(b,'B')]) as (m,p,f,h,j):
        native=os.replace;calls=[]
        def rename(src,dst,**kw):
            result=native(src,dst,**kw)
            if dst!='journal.json':calls.append(dst);raise OSError(5,'lost result')
            return result
        with patch.object(os,'replace',side_effect=rename):
            with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
        assert len(calls)==1 and e.value.publication_possible
        assert e.value.diagnostic()['write_state']=='unknown'
        assert record(tmp_path,j)['published_count']==0
        assert files(tmp_path)!=m.source_files
        assert (tmp_path/j.data['files'][1]['staging_path']).exists()


def test_ack_failure_prevents_second_target(tmp_path):
    a,b=goal(1),goal(2)
    with staged(tmp_path,artifacts=[a,b],operations=[edit(a,'A'),edit(b,'B')]) as (m,p,f,h,j):
        native=os.replace;targets=[]
        def rename(src,dst,**kw):
            if dst=='journal.json' and targets:raise OSError(28,'ack blocked')
            value=native(src,dst,**kw)
            if dst!='journal.json':targets.append(dst)
            return value
        with patch.object(os,'replace',side_effect=rename):
            with pytest.raises(CommitPublicationError) as e:publish(f,j,h)
        assert len(targets)==1 and e.value.published_count==0
        assert record(tmp_path,j)['published_count']==0
        assert (tmp_path/j.data['files'][1]['path']).read_bytes()==m.source_files[j.data['files'][1]['path']]


def test_journal_values_are_independent_and_not_success(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        v=j.data;v['state']='committing';raw=json.dumps(v,indent=1).encode()
        parsed=CommittingJournal(raw);changed=parsed.data;changed['files']=[]
        assert parsed.source_bytes==raw and parsed.sha256==sha256(raw).hexdigest()
        assert copy.deepcopy(parsed).data==v
        assert verify_committing_journal(parsed,f) is None
        with pytest.raises(TypeError):bool(parsed)
        with pytest.raises(JournalError):PreparedJournal(raw)


@pytest.mark.parametrize('value',[-1,True,None,2])
def test_invalid_acknowledgement_counts_rejected(tmp_path,value):
    with staged(tmp_path) as (m,p,f,h,j):
        v=j.data;v.update(state='committing',published_count=value)
        with pytest.raises(CommitPublicationError):CommittingJournal(canonical_json_bytes(v))


def test_self_consistent_short_inventory_cannot_replace_independent_binding(tmp_path):
    with staged(tmp_path) as (m,p,f,h,j):
        v=j.data;v.update(state='committing',files=[])
        with pytest.raises(CommitPublicationError):verify_committing_journal(CommittingJournal(canonical_json_bytes(v)),f)


def test_earlier_target_tampering_blocks_next_ack_and_publication(tmp_path):
    a,b=goal(1),goal(2)
    with staged(tmp_path,artifacts=[a,b],operations=[edit(a,'A'),edit(b,'B')]) as (m,p,f,h,j):
        native=os.fsync;done=False
        def sync(fd):
            nonlocal done
            native(fd)
            path=tmp_path/j.data['files'][0]['path']
            if not done and not (tmp_path/j.data['files'][0]['staging_path']).exists():
                done=True;raw=path.read_bytes();info=path.stat();path.write_bytes(b'X'+raw[1:])
                os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns))
        with patch.object(os,'fsync',side_effect=sync):
            with pytest.raises(CommitPublicationError):publish(f,j,h)
        assert done and record(tmp_path,j)['published_count']==0
        assert (tmp_path/j.data['files'][1]['staging_path']).exists()
