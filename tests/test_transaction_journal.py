"""Building journal contracts and real owned-tempdir effects, not presentation."""
import copy
import json
import os
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import pytest
from specroad.changes import (BuildingJournal, JournalError, prepare_building_journal,
    verify_building_journal, begin_building_journal, read_building_journal,
    project_lock, PublicationAuthority, PublicationCheckError)
from specroad.storage.project import ProjectSource
from specroad.model.canonical import canonical_json_bytes
from support.publication import prepared, options, files, ALLOW, TRANSACTION
from support.folds import goal, edit, create
from support.targets import TIME, ACTOR


def record(check):
    return prepare_building_journal(check,transaction_id=TRANSACTION)


def begin(check, held, **kw):
    return begin_building_journal(check,held_lock=held,transaction_id=TRANSACTION,
                                 authority=kw.pop('authority',ALLOW),**kw)


def altered(journal, fn):
    data=journal.data;fn(data)
    return canonical_json_bytes(data)


def test_inventory_binds_actual_before_and_after_bytes(tmp_path):
    m,p,c=prepared(tmp_path);j=record(c);v=j.data;e=v['files'][0];target=c.request.documents[0]
    assert v['state']=='building' and v['published_count']==0
    assert v['plan_sha256']==p.sha256 and v['request_sha256']==c.request.sha256
    assert v['base_model_root_sha256']==p.data['base']['model_root_sha256']
    assert v['target_model_root_sha256']==p.data['expected_result']['model_root_sha256']
    assert e['path']==target.path and e['existed_before'] is True and e['published'] is False
    assert e['before_sha256']==sha256(m.source_files[target.path]).hexdigest()
    assert e['after_sha256']==sha256(target.content).hexdigest()
    assert e['before_size']==len(m.source_files[target.path]) and e['after_size']==len(target.content)
    assert e['staging_path'].startswith('.specroad/transactions/'+TRANSACTION+'/staging/')
    assert e['before_image_path'].startswith('.specroad/transactions/'+TRANSACTION+'/before/')
    assert verify_building_journal(j,c) is None


def test_prepare_is_pure_and_does_not_stage_or_acquire_lock(tmp_path):
    m,p,c=prepared(tmp_path);before=files(tmp_path)
    with patch.object(os,'open',side_effect=AssertionError('open')):
        j=record(c)
    assert files(tmp_path)==before and not (tmp_path/'.specroad').exists()
    assert j.data['actor']==p.data['actor'] and j.data['planned_at']==p.data['planned_at']


def test_create_is_complete_synced_journal_only(tmp_path):
    m,p,c=prepared(tmp_path);before=files(tmp_path);syncs=[];sync=os.fsync
    with project_lock(tmp_path,**options(c)) as held:
        with patch.object(os,'fsync',side_effect=lambda fd:(syncs.append(os.fstat(fd).st_mode),sync(fd))[1]):
            j=begin(c,held)
        assert held.check() and len(syncs)>=3
        path=tmp_path/j.path
        assert path.read_bytes()==j.source_bytes
        assert (path.stat().st_mode&0o777)==0o600
        assert sorted(x.name for x in path.parent.iterdir())==['journal.json']
        assert read_building_journal(ProjectSource(tmp_path),TRANSACTION,expected_sha256=j.sha256).data==j.data
    assert files(tmp_path)==before
    assert not (tmp_path/'.specroad/locks/project.json').exists()
    assert (tmp_path/j.path).is_file()


def test_new_file_has_no_before_image(tmp_path):
    a=goal(2,revision=1,created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR);m,p,c=prepared(tmp_path,operations=[create(a)])
    e=record(c).data['files'][0]
    assert e['existed_before'] is False
    assert e['before_sha256'] is None and e['before_size'] is None and e['before_image_path'] is None


def test_noop_does_not_invent_changed_files(tmp_path):
    m,p,c=prepared(tmp_path,operations=[])
    assert record(c).data['files']==[]
    with project_lock(tmp_path,**options(c)) as h:
        assert begin(c,h).data['files']==[]
    assert files(tmp_path)==m.source_files


def test_changed_files_are_ordered_not_operation_order(tmp_path):
    a,b=goal(1),goal(2)
    m,p,c=prepared(tmp_path,artifacts=[a,b],operations=[edit(b,'B'),edit(a,'A')])
    j=record(c);names=[e['path'] for e in j.data['files']]
    assert len(names)==2 and names==sorted(names)
    assert len({e['staging_path'] for e in j.data['files']})==2


def test_journal_data_and_original_bytes_are_independent(tmp_path):
    m,p,c=prepared(tmp_path);j=record(c);data=j.data
    data['files'][0]['published']=True
    assert j.data['files'][0]['published'] is False
    pretty=json.dumps(j.data,indent=4).encode();parsed=BuildingJournal(pretty)
    assert parsed.source_bytes==pretty and parsed.data==j.data and parsed.sha256==sha256(pretty).hexdigest()
    assert verify_building_journal(parsed,c) is None
    with pytest.raises(TypeError):bool(j)
    assert copy.deepcopy(j).data==j.data


@pytest.mark.parametrize('name',['../x','/tmp/x','a/b','a\\b','.', '..','receipts','RECEIPTS','.git','CON','x.', 'a'*129])
def test_transaction_namespace_is_safe(tmp_path,name):
    m,p,c=prepared(tmp_path)
    with pytest.raises(JournalError):prepare_building_journal(c,transaction_id=name)
    assert not (tmp_path/'.specroad').exists()


@pytest.mark.parametrize('change',[
    lambda v:v.update(published_count=1),
    lambda v:v['files'][0].update(published=True),
    lambda v:v['files'][0].update(existed_before=False),
    lambda v:v['files'][0].update(before_sha256=None),
    lambda v:v['files'][0].update(before_image_path='../bad'),
    lambda v:v['files'][0].update(staging_path='spec/new.json'),
    lambda v:v['files'][0].update(path='.specroad/locks/project.json'),
    lambda v:v.update(extra=True),
    lambda v:v['files'][0].update(after_size=True),
    lambda v:v['files'].append(v['files'][0].copy()),
    lambda v:v.update(state='committed'),
])
def test_malformed_building_records_are_not_success(tmp_path,change):
    m,p,c=prepared(tmp_path);j=record(c)
    with pytest.raises(JournalError):BuildingJournal(altered(j,change))


def test_missing_inventory_entry_fails_independent_plan_binding(tmp_path):
    m,p,c=prepared(tmp_path);j=record(c)
    incomplete=BuildingJournal(altered(j,lambda v:(v.update(files=[]),v['discard_basis'].update(staging_images=[]))))
    with pytest.raises(JournalError) as e:verify_building_journal(incomplete,c)
    assert e.value.exit_code==6


def test_matching_transaction_id_cannot_overwrite_existing_journal(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        j=begin(c,h); before=(tmp_path/j.path).read_bytes()
        with pytest.raises(PublicationCheckError):begin(c,h)
        assert (tmp_path/j.path).read_bytes()==before
    with pytest.raises(Exception):
        with project_lock(tmp_path,**options(c)):pass


def test_denied_authority_creates_no_journal(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError):
            begin(c,h,authority=PublicationAuthority('deny','1',lambda r:False))
    assert not (tmp_path/'.specroad/transactions').exists()


def test_expired_native_lock_cannot_create_record(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:pass
    with pytest.raises(PublicationCheckError):begin(c,h)
    assert not (tmp_path/'.specroad/transactions').exists()


def test_changed_base_refuses_before_journal_creation(tmp_path):
    m,p,c=prepared(tmp_path);f=tmp_path/m.documents[0].path;f.write_bytes(f.read_bytes()+b' ')
    before=files(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError):begin(c,h)
    assert not (tmp_path/'.specroad/transactions').exists() and files(tmp_path)==before


def test_read_wrong_hash_is_not_a_valid_current_record(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:j=begin(c,h)
    with pytest.raises(JournalError) as e:
        read_building_journal(ProjectSource(tmp_path),TRANSACTION,expected_sha256='0'*64)
    assert e.value.reason=='journal_bytes_changed'
