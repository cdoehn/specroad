"""Failure preservation, hostile paths and independently bound journal reads."""
import json
import os
import stat
import errno
from pathlib import Path
from unittest.mock import patch
import pytest
from specroad.changes import (BuildingJournal, JournalError, begin_building_journal,
    read_building_journal, prepare_building_journal, verify_building_journal,
    project_lock, PublicationCheckError, prepare_publication_check)
from specroad.storage.project import ProjectSource
from specroad.model.canonical import canonical_json_bytes
from support.publication import prepared, options, files, ALLOW, TRANSACTION
from support.targets import POLICY, TIME, ACTOR
from support.folds import goal, edit, create
from test_transaction_journal import record, begin, altered


@pytest.mark.parametrize('field',['plan_sha256','plan_bytes_sha256','request_sha256',
                                   'base_model_root_sha256','target_model_root_sha256'])
def test_rehashed_but_wrong_plan_binding_is_refused(tmp_path,field):
    m,p,c=prepared(tmp_path)
    # Authoring consistency is checked during decoding, before independent
    # plan verification. Either boundary must reject the hostile binding.
    with pytest.raises(JournalError) as e:
        j=BuildingJournal(altered(record(c),lambda v:v.update({field:'0'*64})))
        verify_building_journal(j,c)
    expected = ('invalid_journal_authoring_binding' if field in
                ('plan_sha256','base_model_root_sha256') else 'journal_plan_inventory_mismatch')
    assert e.value.reason==expected


def test_consistent_but_false_existence_does_not_override_source(tmp_path):
    m,p,c=prepared(tmp_path)
    def change(v):v['files'][0].update(existed_before=False,before_sha256=None,before_size=None,before_image_path=None)
    j=BuildingJournal(altered(record(c),change))
    with pytest.raises(JournalError):verify_building_journal(j,c)


def test_correct_sha_of_false_inventory_still_fails_bound_read(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:j=begin(c,h)
    other=BuildingJournal(altered(j,lambda v:(v.update(files=[]),v['discard_basis'].update(staging_images=[]))))
    (tmp_path/j.path).write_bytes(other.source_bytes)
    with pytest.raises(JournalError) as e:
        read_building_journal(ProjectSource(tmp_path),TRANSACTION,expected_sha256=other.sha256,preflight=c)
    assert e.value.reason=='journal_plan_inventory_mismatch'


@pytest.mark.parametrize('path',['generated/out.json','notes.txt','archive/objects/aa/x','.git/config',
                                '.patchharbor/config.json','spec/../evil.json','/tmp/z.json'])
def test_non_normative_or_unsafe_target_paths_are_refused(tmp_path,path):
    m,p,c=prepared(tmp_path)
    with pytest.raises(JournalError):BuildingJournal(altered(record(c),lambda v:v['files'][0].update(path=path)))


@pytest.mark.parametrize('field',['staging_path','before_image_path'])
def test_cross_transaction_references_are_refused(tmp_path,field):
    m,p,c=prepared(tmp_path)
    raw=altered(record(c),lambda v:v['files'][0].update({field:'.specroad/transactions/foreign/staging/0.bin'}))
    with pytest.raises(JournalError):BuildingJournal(raw)


def test_hash_and_length_of_every_151_file_is_bound(tmp_path):
    originals=[goal(i) for i in range(151)]
    m,p,c=prepared(tmp_path,artifacts=originals,operations=[edit(a,'New') for a in originals])
    j=record(c); assert len(j.data['files'])==151
    assert len({e['staging_path'] for e in j.data['files']})==151
    with pytest.raises(JournalError) as error:
        bad=BuildingJournal(altered(j,lambda v:v['files'][79].update(after_size=17)))
        verify_building_journal(bad,c)
    assert error.value.reason=='journal_target_inventory_mismatch'
    with project_lock(tmp_path,**options(c)) as h:saved=begin(c,h)
    assert read_building_journal(ProjectSource(tmp_path),TRANSACTION,preflight=c).data==saved.data


def test_empty_old_file_is_not_inferred_from_truthiness(tmp_path):
    # Raw empty normative sources are rejected by the existing preflight, never
    # silently interpreted as absent so an invalid before-image can be omitted.
    m,p,c=prepared(tmp_path);path=tmp_path/m.documents[0].path;path.write_bytes(b'')
    with project_lock(tmp_path,**options(c)) as h:
        with pytest.raises(PublicationCheckError):begin(c,h)
    assert path.read_bytes()==b'' and not (tmp_path/'.specroad/transactions').exists()


def test_truncated_journal_survives_as_blocker(tmp_path):
    m,p,c=prepared(tmp_path);before=files(tmp_path);original=os.write
    with project_lock(tmp_path,**options(c)) as h:
        calls=[]
        def write(fd,b):
            if not calls:
                calls.append(1);return original(fd,b[:19])
            raise OSError(errno.ENOSPC,'test disk full')
        with patch.object(os,'write',side_effect=write):
            with pytest.raises(JournalError) as e:begin(c,h)
        assert e.value.mutation_possible
    path=tmp_path/record(c).path
    assert path.is_file() and path.stat().st_size==19 and files(tmp_path)==before
    with pytest.raises(JournalError):read_building_journal(ProjectSource(tmp_path),TRANSACTION)
    with pytest.raises(Exception):
        with project_lock(tmp_path,**options(c)):pass
    assert path.read_bytes()==record(c).source_bytes[:19]


def test_partial_system_writes_are_completed_without_truncation(tmp_path):
    m,p,c=prepared(tmp_path);original=os.write;calls=[]
    with project_lock(tmp_path,**options(c)) as h:
        def short(fd,b):calls.append(len(b));return original(fd,b[:13])
        with patch.object(os,'write',side_effect=short):j=begin(c,h)
    assert len(calls)>1 and (tmp_path/j.path).read_bytes()==j.source_bytes


def test_zero_write_is_error_not_spin_or_success(tmp_path):
    m,p,c=prepared(tmp_path);before=files(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:
        with patch.object(os,'write',return_value=0):
            with pytest.raises(JournalError) as e:begin(c,h)
        assert e.value.reason=='journal_short_write' and e.value.mutation_possible
    assert files(tmp_path)==before and (tmp_path/record(c).path).exists()


@pytest.mark.parametrize('boundary',['file','parent'])
def test_failed_fsync_preserves_operational_state(tmp_path,boundary):
    m,p,c=prepared(tmp_path);before=files(tmp_path);real=os.fsync
    with project_lock(tmp_path,**options(c)) as h:
        def sync(fd):
            path=Path('/proc/self/fd/'+str(fd)).readlink()
            if (boundary=='file' and path.name=='journal.json') or (boundary=='parent' and path.name==TRANSACTION):
                raise OSError(errno.EIO,'test synchronization failure')
            return real(fd)
        with patch.object(os,'fsync',side_effect=sync):
            with pytest.raises(JournalError) as e:begin(c,h)
        assert e.value.mutation_possible
    assert files(tmp_path)==before and (tmp_path/record(c).path).exists()


def test_same_bytes_replaced_journal_is_not_original_write(tmp_path):
    m,p,c=prepared(tmp_path);real=os.fsync;triggered=[]
    with project_lock(tmp_path,**options(c)) as h:
        def sync(fd):
            real(fd);path=Path('/proc/self/fd/'+str(fd)).readlink()
            if path.name==TRANSACTION and not triggered:
                triggered.append(True);f=path/'journal.json';tmp=path/'replace';tmp.write_bytes(f.read_bytes());tmp.replace(f)
        with patch.object(os,'fsync',side_effect=sync):
            with pytest.raises(JournalError) as e:begin(c,h)
        assert e.value.reason=='journal_file_replaced' and e.value.mutation_possible
    assert triggered and (tmp_path/record(c).path).exists()


def test_new_foreign_recovery_entry_during_write_is_preserved(tmp_path):
    m,p,c=prepared(tmp_path);real=os.fsync;foreign=tmp_path/'.specroad/transactions/other'
    with project_lock(tmp_path,**options(c)) as h:
        def sync(fd):
            real(fd)
            if Path('/proc/self/fd/'+str(fd)).readlink().name=='journal.json':foreign.mkdir()
        with patch.object(os,'fsync',side_effect=sync):
            with pytest.raises(JournalError) as e:begin(c,h)
        assert e.value.reason=='journal_recovery_set_changed'
    assert foreign.is_dir() and (tmp_path/record(c).path).exists()


def test_read_missing_journal_creates_nothing(tmp_path):
    m,p,c=prepared(tmp_path);before=files(tmp_path)
    with pytest.raises(JournalError):read_building_journal(ProjectSource(tmp_path),TRANSACTION)
    assert not (tmp_path/'.specroad').exists() and files(tmp_path)==before


def test_read_journal_hardlink_is_rejected_without_deletion(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:j=begin(c,h)
    os.link(tmp_path/j.path,tmp_path/'unmanaged-link')
    with pytest.raises(JournalError) as e:read_building_journal(ProjectSource(tmp_path),TRANSACTION)
    assert e.value.exit_code==7 and (tmp_path/j.path).stat().st_nlink==2


def test_read_journal_symlink_never_opens_external_target(tmp_path):
    m,p,c=prepared(tmp_path)
    with project_lock(tmp_path,**options(c)) as h:j=begin(c,h)
    f=tmp_path/j.path;raw=f.read_bytes();external=tmp_path/'external';external.write_bytes(raw)
    f.unlink();f.symlink_to(external)
    with pytest.raises(JournalError):read_building_journal(ProjectSource(tmp_path),TRANSACTION)
    assert external.read_bytes()==raw and f.is_symlink()


def test_fifo_record_is_rejected_without_blocking(tmp_path):
    m,p,c=prepared(tmp_path);f=tmp_path/record(c).path;f.parent.mkdir(parents=True);os.mkfifo(f)
    with pytest.raises(JournalError):read_building_journal(ProjectSource(tmp_path),TRANSACTION)
    assert stat.S_ISFIFO(f.stat().st_mode)


def test_journal_copied_to_different_project_instance_is_refused(tmp_path):
    import shutil
    m,p,c=prepared(tmp_path/'a')
    with project_lock(tmp_path/'a',**options(c)) as h:j=begin(c,h)
    shutil.copytree(tmp_path/'a',tmp_path/'b')
    with pytest.raises(JournalError) as e:read_building_journal(ProjectSource(tmp_path/'b'),TRANSACTION)
    assert e.value.reason=='journal_project_binding_mismatch'


@pytest.mark.parametrize('raw',[b'{',b'[]',b'{} {}',b'{"a":1,"a":2}',b'\xff',b'\xef\xbb\xbf{}'])
def test_strict_raw_json_and_partial_records_fail_without_read_side_effects(raw):
    with pytest.raises(JournalError):BuildingJournal(raw)


def test_crash_after_creation_retains_record_and_excludes_new_writer(tmp_path):
    from support.processes import run_python,SOURCE
    script='''import sys,os
sys.path[:0]=[sys.argv[1],sys.argv[2]]
from support.publication import prepared,options,ALLOW,TRANSACTION
from specroad.changes import project_lock,begin_building_journal
m,p,c=prepared(sys.argv[3])
with project_lock(sys.argv[3],**options(c)) as h:
 begin_building_journal(c,held_lock=h,transaction_id=TRANSACTION,authority=ALLOW)
 os._exit(23)
'''
    root=tmp_path/'child'
    result=run_python(['-I','-S','-B','-c',script,str(SOURCE),str(Path(__file__).parent),str(root)],tmp_path,capture=True)
    assert result.returncode==23,result.stderr
    j=read_building_journal(ProjectSource(root),TRANSACTION)
    assert j.data['state']=='building' and j.data['published_count']==0
    assert (root/'.specroad/locks/project.json').exists()
    with pytest.raises(Exception):
        with project_lock(root,kind='writer',command='change apply',project_id='sample',transaction_id='other',request_id='req'):pass
    assert (root/j.path).exists()


def test_portable_distributions_keep_journal_codec_and_creation(tmp_path):
    from support.portable import build_distribution
    from support.processes import run_python
    module,archive=build_distribution(tmp_path/'delivery')
    moved=tmp_path/'moved';module.rename(moved);pyz=tmp_path/'moved.pyz';archive.rename(pyz)
    script='''import sys,json
sys.path[:0]=[sys.argv[1],sys.argv[2]]
from support.publication import prepared,options,ALLOW,TRANSACTION
from specroad.changes import project_lock,begin_building_journal,read_building_journal
from specroad.storage.project import ProjectSource
m,p,c=prepared(sys.argv[3])
with project_lock(sys.argv[3],**options(c)) as h:
 j=begin_building_journal(c,held_lock=h,transaction_id=TRANSACTION,authority=ALLOW)
 assert read_building_journal(ProjectSource(sys.argv[3]),TRANSACTION,preflight=c).data==j.data
assert j.data['published_count']==0
'''
    for i,location in enumerate((moved,pyz)):
        run=run_python(['-I','-S','-B','-c',script,str(location),str(Path(__file__).parent),str(tmp_path/str(i))],tmp_path,capture=True)
        assert run.returncode==0,run.stderr
