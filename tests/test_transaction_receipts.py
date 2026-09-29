"""Receipts precede the durable committed marker; no duplicate model write."""
from hashlib import sha256
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from specroad.changes import (TransactionReceipt, RequestReceipt, CommittedJournal,
    ReceiptError, prepare_completion_receipts, PublicationAuthority,
    request_receipt_path, transaction_receipt_path, finalize_committing_journal)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from support.receipts import published, finish
from support.publication import files
from support.folds import goal, create, edit
from support.targets import TIME, ACTOR


def test_complete_receipts_bind_plan_actor_source_target_and_operations(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        result=finish(f,h,j)
        t,r,c=prepare_completion_receipts(f,j)
        assert result.data['commit_completed'] and result.data['current_target_verified']
        assert (tmp_path/t.path).read_bytes()==t.source_bytes
        assert (tmp_path/r.path).read_bytes()==r.source_bytes
        assert (tmp_path/j.path).read_bytes()==c.source_bytes
        data=r.data
        assert data['actor']==p.data['actor']
        assert data['operations_sha256']==canonical_json_sha256(p.data['operations'])
        assert data['base_model_root_sha256']==p.data['base']['model_root_sha256']
        assert data['target_model_root_sha256']==p.data['expected_result']['model_root_sha256']
        assert data['result_object']['exit_code']==0
        assert data['transaction_receipt']['sha256']==t.sha256
        assert t.data['journal']['plan_bytes_sha256']==sha256(p.source_bytes).hexdigest()


def test_receipts_are_synced_before_committed_marker(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j)
        original_sync, original_replace = os.fsync, os.replace
        synced=[]; replacements=[]
        def sync(fd):
            name=os.readlink('/proc/self/fd/'+str(fd));original_sync(fd);synced.append(name)
        def replace(src,dst,**kwargs):
            assert dst=='journal.json'
            for receipt in (t,r):
                assert str(tmp_path/receipt.path) in synced
                assert str((tmp_path/receipt.path).parent) in synced
                assert (tmp_path/receipt.path).read_bytes()==receipt.source_bytes
            replacements.append(dst);return original_replace(src,dst,**kwargs)
        with patch.object(os,'fsync',sync),patch.object(os,'replace',replace): finish(f,h,j)
        assert replacements==['journal.json']
        assert str((tmp_path/j.path).parent)==synced[-1]


def test_no_normative_write_no_revision_bump_no_cleanup(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        baseline=files(tmp_path)
        finish(f,h,j)
        assert files(tmp_path)==baseline
        for entry in j.data['files']:
            if entry['before_image_path']:
                assert (tmp_path/entry['before_image_path']).read_bytes()==m.source_files[entry['path']]
        assert (tmp_path/j.path).exists()


def test_no_request_id_does_not_create_request_receipt(tmp_path):
    with published(tmp_path, request_id=None) as (m,p,f,h,j):
        result=finish(f,h,j)
        assert result.data['request_id'] is None
        assert result.data['receipts']['request'] is None
        assert not (tmp_path/'.specroad/requests').exists()
        assert (tmp_path/transaction_receipt_path(j.data['transaction_id'])).is_file()


def test_empty_plan_has_real_completion_without_fake_targets(tmp_path):
    with published(tmp_path, operations=[]) as (m,p,f,h,j):
        baseline=files(tmp_path)
        result=finish(f,h,j)
        t=TransactionReceipt((tmp_path/result.data['receipts']['transaction']['path']).read_bytes())
        assert t.data['result_object']['published_paths']==[]
        assert t.data['created_ids']==[]
        assert files(tmp_path)==baseline


def test_created_ids_record_actual_plan_identities(tmp_path):
    a=goal(9,revision=1,created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR)
    with published(tmp_path,operations=[create(a)]) as (m,p,f,h,j):
        result=finish(f,h,j)
        t=TransactionReceipt((tmp_path/result.data['receipts']['transaction']['path']).read_bytes())
        assert t.data['created_ids']==[a['id']]
        assert t.data['result_object']['created_ids']==[a['id']]


def test_existing_transaction_receipt_is_not_overwritten(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j)
        q=tmp_path/t.path;q.parent.mkdir(parents=True);q.write_bytes(b'foreign')
        with pytest.raises(ReceiptError) as err: finish(f,h,j)
        assert err.value.reason=='completion_receipt_already_exists'
        assert q.read_bytes()==b'foreign'
        assert (tmp_path/j.path).read_bytes()==j.source_bytes
        assert not (tmp_path/r.path).exists()


def test_existing_request_receipt_blocks_before_transaction_receipt_write(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j)
        q=tmp_path/r.path;q.parent.mkdir(parents=True);q.write_bytes(b'foreign')
        with pytest.raises(ReceiptError): finish(f,h,j)
        assert not (tmp_path/t.path).exists()
        assert q.read_bytes()==b'foreign'


def test_denied_authority_produces_no_receipt(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        with pytest.raises(ReceiptError) as e:
            finish(f,h,j,authority=PublicationAuthority('denied','1',lambda request:False))
        assert e.value.exit_code==7
        assert not (tmp_path/'.specroad/transactions/receipts').exists()
        assert (tmp_path/j.path).read_bytes()==j.source_bytes


def test_target_changed_before_completion_is_not_attested(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        q=tmp_path/f.request.documents[0].path;q.write_bytes(q.read_bytes()+b' ')
        with pytest.raises(ReceiptError): finish(f,h,j)
        assert not (tmp_path/'.specroad/transactions/receipts').exists()


def test_unchanged_resource_changed_before_completion_is_not_attested(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        q=tmp_path/'profiles/core.json';q.write_bytes(q.read_bytes()+b' ')
        with pytest.raises(ReceiptError): finish(f,h,j)
        assert not (tmp_path/'.specroad/transactions/receipts').exists()


def test_incomplete_publication_is_not_finalizable(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        from specroad.changes import CommittingJournal
        data=j.data;data['published_count']=0;data['files'][0]['published']=False
        incomplete=CommittingJournal(canonical_json_bytes(data))
        with pytest.raises(ReceiptError) as err: prepare_completion_receipts(f,incomplete)
        assert err.value.reason=='complete_publication_required'


def test_projection_only_never_writes_files(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        before={q.relative_to(tmp_path).as_posix():q.read_bytes() for q in tmp_path.rglob('*') if q.is_file()}
        a=prepare_completion_receipts(f,j);b=prepare_completion_receipts(f,j)
        assert [v.source_bytes for v in a]==[v.source_bytes for v in b]
        assert before=={q.relative_to(tmp_path).as_posix():q.read_bytes() for q in tmp_path.rglob('*') if q.is_file()}


def test_returned_data_is_independent(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        t,r,c=prepare_completion_receipts(f,j)
        for value in (t,r,c):
            expected=value.source_bytes
            data=value.data;data.clear()
            assert value.source_bytes==expected and value.data
            with pytest.raises(TypeError): bool(value)
        result=finish(f,h,j);data=result.data;data.clear();assert result.data['commit_completed']
        with pytest.raises(TypeError): bool(result)


@pytest.mark.parametrize('raw',[b'',b'{',b'[]',b'{} garbage',b'\xff',b'{"x":1,"x":2}'])
def test_malformed_receipt_bytes_fail_closed(raw):
    for kind in (TransactionReceipt,RequestReceipt,CommittedJournal):
        with pytest.raises(ReceiptError):kind(raw)


def test_private_file_modes(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        result=finish(f,h,j)
        for ref in result.data['receipts'].values():
            if ref: assert (tmp_path/ref['path']).stat().st_mode & 0o777==0o600


def test_request_path_is_case_sensitive_and_path_safe():
    assert request_receipt_path('AbC')!=request_receipt_path('abc')
    value=request_receipt_path('x:Y._-z')
    assert value.startswith('.specroad/requests/') and len(value.rsplit('/',1)[1])==69
    with pytest.raises(Exception): request_receipt_path('../unsafe')


def test_reusing_old_finalization_input_never_repeats_target_write(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);baseline=files(tmp_path)
        with pytest.raises(ReceiptError): finish(f,h,j)
        assert files(tmp_path)==baseline


def test_foreign_journal_blocks_completion(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        (tmp_path/'.specroad/transactions/other').mkdir()
        with pytest.raises(ReceiptError):finish(f,h,j)
        assert not (tmp_path/'.specroad/transactions/receipts').exists()


def test_modified_journal_binding_is_rejected(tmp_path):
    from specroad.changes import CommittingJournal
    with published(tmp_path) as (m,p,f,h,j):
        data=j.data;data['target_model_root_sha256']='0'*64
        bad=CommittingJournal(canonical_json_bytes(data))
        with pytest.raises(Exception):prepare_completion_receipts(f,bad)


def test_prepared_is_not_complete(tmp_path):
    from support.committing import staged
    with staged(tmp_path) as (m,p,f,h,j):
        with pytest.raises(ReceiptError):
            finalize_committing_journal(f,j,held_lock=h,authority=PublicationAuthority('a','1',lambda r: True))
        assert not (tmp_path/'.specroad/transactions/receipts').exists()
