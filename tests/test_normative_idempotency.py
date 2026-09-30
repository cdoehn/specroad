"""Actual local committed receipts, not mock success or console assertions."""
import json
from unittest.mock import patch
import pytest
from specroad.changes import (resolve_normative_request, bind_plan_authoring,
    prepare_authoring_request, ReceiptError, request_receipt_path, RequestReceipt,
    cleanup_completed_transaction, prepare_completion_receipts,
    begin_building_journal, project_lock, prepare_publication_check, PublicationCheckError)
from specroad.storage.project import ProjectSource
from support.receipts import published, finish
from support.publication import ALLOW, TRANSACTION, files, prepared, NativeGuardStorage
from support.targets import ACTOR, TIME, POLICY, plan
from support.folds import goal, create, edit
from support.read_only import no_write_attempts


def inventory(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def retry(root, p):
    return resolve_normative_request(ProjectSource(root), bind_plan_authoring(p))


def test_identical_retry_returns_exact_stored_result_without_any_write(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j)
        saved=RequestReceipt((tmp_path/request_receipt_path('request-1')).read_bytes())
    before=inventory(tmp_path)
    with no_write_attempts():
        first=retry(tmp_path,p); second=retry(tmp_path,p)
    assert first.data==second.data
    assert first.data['action']=='replay'
    assert first.data['result_object']==saved.data['result_object']
    assert first.data['original_request']==saved.data
    assert first.data['normative_writes']==0 and not first.data['write_authorized']
    assert inventory(tmp_path)==before


def test_created_ids_are_reused_not_allocated_again(tmp_path):
    artifact=goal(9,revision=1,created_at=TIME,updated_at=TIME,created_by=ACTOR,updated_by=ACTOR)
    with published(tmp_path,operations=[create(artifact)]) as (m,p,f,h,j): finish(f,h,j)
    before=files(tmp_path)
    for _ in range(3):
        result=retry(tmp_path,p).data
        assert result['created_ids']==[artifact['id']]
        assert result['result_object']['created_ids']==[artifact['id']]
    assert files(tmp_path)==before
    assert len(list((tmp_path/'.specroad/requests').iterdir()))==1


def test_request_missing_is_non_authorizing_and_write_free(tmp_path):
    m,p,f=prepared(tmp_path)
    before=inventory(tmp_path)
    with no_write_attempts(): result=retry(tmp_path,p).data
    assert result['action']=='new_request' and result['result_object'] is None
    assert not result['write_authorized'] and result['locked_recheck_required']
    assert not (tmp_path/'.specroad').exists() and inventory(tmp_path)==before


def test_absent_optional_id_never_accesses_receipt_store(tmp_path):
    m,p,f=prepared(tmp_path)
    request=prepare_authoring_request(command_id='change apply',actor=ACTOR,operations=[],request_id=None)
    with patch('specroad.changes.idempotency._confirmed_receipt', side_effect=AssertionError('receipt read')):
        result=resolve_normative_request(ProjectSource(tmp_path),request).data
    assert result['action']=='not_applicable' and not result['receipt_verified']


def test_dry_run_never_consumes_a_stored_normative_receipt(tmp_path):
    with published(tmp_path) as (m,p,f,h,j): finish(f,h,j)
    request=prepare_authoring_request(command_id='change apply',actor=ACTOR,
        operations=p.data['operations'],request_id='request-1',dry_run=True)
    with patch('specroad.changes.idempotency._confirmed_receipt', side_effect=AssertionError('receipt read')):
        result=resolve_normative_request(ProjectSource(tmp_path),request).data
    assert result['action']=='not_applicable'


def test_changed_operations_fail_closed_without_writes(tmp_path):
    with published(tmp_path) as (m,p,f,h,j): finish(f,h,j)
    before=inventory(tmp_path)
    request=prepare_authoring_request(command_id='change apply',actor=ACTOR,operations=[],request_id='request-1')
    with pytest.raises(ReceiptError) as error: resolve_normative_request(ProjectSource(tmp_path),request)
    assert error.value.exit_code==6 and error.value.reason=='request_operations_conflict'
    assert inventory(tmp_path)==before


def test_orphan_receipt_is_not_a_completed_request(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        _,receipt,_=prepare_completion_receipts(f,j)
        path=tmp_path/receipt.path;path.parent.mkdir(parents=True);path.write_bytes(receipt.source_bytes)
        with pytest.raises(ReceiptError): retry(tmp_path,p)
        assert json.loads((tmp_path/j.path).read_bytes())['state']=='committing'


def test_retry_survives_completed_work_cleanup(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j)
        result=cleanup_completed_transaction(f,TRANSACTION,held_lock=h,authority=ALLOW)
        assert result.data['cleanup_completed']
    with no_write_attempts(): result=retry(tmp_path,p).data
    assert result['action']=='replay' and result['receipt_verified']
    assert not (tmp_path/j.path).exists()


def test_corrupt_receipt_never_becomes_a_new_request(tmp_path):
    with published(tmp_path) as (m,p,f,h,j): finish(f,h,j)
    q=tmp_path/request_receipt_path('request-1');q.write_bytes(b'{}')
    before=inventory(tmp_path)
    with pytest.raises(ReceiptError): retry(tmp_path,p)
    assert inventory(tmp_path)==before


def test_native_new_writer_cannot_reuse_a_completed_request_id(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):
        finish(f,h,j);cleanup_completed_transaction(f,TRANSACTION,held_lock=h,authority=ALLOW)
    current=NativeGuardStorage(m,f).read_model()
    second=plan(current,[edit(current.artifacts[0],'A different write')])
    check=prepare_publication_check(second,current,policy=POLICY)
    before=files(tmp_path)
    with project_lock(tmp_path,kind='writer',command='change apply',project_id='sample',
                      request_id='request-1',transaction_id='second') as held:
        with pytest.raises(PublicationCheckError) as error:
            begin_building_journal(check,held_lock=held,transaction_id='second',authority=ALLOW)
        assert error.value.exit_code==6
    assert files(tmp_path)==before and not (tmp_path/'.specroad/transactions/second').exists()


def test_results_are_detached_values_not_write_capabilities(tmp_path):
    with published(tmp_path) as (m,p,f,h,j): finish(f,h,j)
    result=retry(tmp_path,p); expected=result.data
    value=result.data;value['original_request'].clear();value['result_object'].clear()
    assert result.data==expected
    with pytest.raises(TypeError): bool(result)
