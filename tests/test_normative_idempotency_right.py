"""Conflicts, canonical operation identity and fail-closed retry boundaries."""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
import shutil
from unittest.mock import patch
import pytest
from specroad.changes import (RequestIdConflict, ReceiptError, RequestReceipt,
    AuthoringRequest, prepare_authoring_request, resolve_normative_request,
    request_receipt_path, prepare_publication_check, begin_building_journal,
    project_lock, PublicationAuthority, PublicationCheckError)
from specroad.model.canonical import canonical_json_sha256
from specroad.storage.project import ProjectSource
from support.receipts import published, finish
from support.publication import prepared, files, ALLOW
from support.targets import ACTOR, POLICY
from support.folds import goal, edit
from support.read_only import no_write_attempts
from test_normative_idempotency import retry, inventory


def request(operations=(), **changes):
    return prepare_authoring_request(**dict(command_id='change apply', actor=ACTOR,
        operations=list(operations), request_id='request-1', **changes))


def test_conflict_reports_both_hashes_and_no_recovery_or_write(tmp_path):
    with published(tmp_path) as (m,p,f,h,j): finish(f,h,j)
    before=inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RequestIdConflict) as error:
        resolve_normative_request(ProjectSource(tmp_path),request())
    data=error.value.diagnostic()
    assert error.value.exit_code==6 and data['write_state']=='not_committed'
    assert data['expected_operations_sha256']==canonical_json_sha256(p.data['operations'])
    assert data['received_operations_sha256']==canonical_json_sha256([])
    assert data['receipt_verified'] and data['existing_request_committed']
    assert not data['recovery_required'] and not data['normative_write_attempted']
    assert not data['mutation_possible'] and not data['committed_possible']
    assert inventory(tmp_path)==before


def test_count_hash_and_revision_prove_exactly_one_model_write(tmp_path):
    native=os.replace; published_names=[]
    def replace(src,dst,**kwargs):
        if str(dst).startswith('SR-GOAL-'): published_names.append(str(dst))
        return native(src,dst,**kwargs)
    with patch.object(os,'replace',replace):
        with published(tmp_path) as (m,p,f,h,j): finish(f,h,j)
        target=f.request.documents[0].path
        initial=m.source_files[target]; committed=(tmp_path/target).read_bytes()
        assert sha256(initial).digest()!=sha256(committed).digest()
        assert json.loads(committed)['revision']==json.loads(initial)['revision']+1
        count=len(files(tmp_path)); expected_hash=sha256(committed).hexdigest()
        for _ in range(4): assert retry(tmp_path,p).data['action']=='replay'
        with pytest.raises(RequestIdConflict):resolve_normative_request(ProjectSource(tmp_path),request())
    assert published_names==[target.rsplit('/',1)[-1]]
    assert len(files(tmp_path))==count and sha256((tmp_path/target).read_bytes()).hexdigest()==expected_hash
    assert json.loads((tmp_path/target).read_bytes())['revision']==json.loads(initial)['revision']+1
    assert len(list((tmp_path/'.specroad/requests').iterdir()))==1


def test_object_key_order_does_not_create_a_new_operation_hash(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):finish(f,h,j)
    # JSON object key order is irrelevant; array order remains normative.
    operations=json.loads(json.dumps(p.data['operations'],sort_keys=True))
    result=resolve_normative_request(ProjectSource(tmp_path),request(operations)).data
    assert result['action']=='replay'


def test_operation_order_is_significant(tmp_path):
    a,b=goal(0),goal(1)
    with published(tmp_path,artifacts=[a,b],operations=[edit(a,'A'),edit(b,'B')]) as (m,p,f,h,j):finish(f,h,j)
    with pytest.raises(RequestIdConflict):
        resolve_normative_request(ProjectSource(tmp_path),request(list(reversed(p.data['operations']))))


def test_request_identity_is_case_sensitive(tmp_path):
    with published(tmp_path,request_id='Case') as (m,p,f,h,j):finish(f,h,j)
    value=prepare_authoring_request(command_id='change apply',actor=ACTOR,
        operations=p.data['operations'],request_id='case')
    assert resolve_normative_request(ProjectSource(tmp_path),value).data['action']=='new_request'


def test_historical_result_does_not_depend_on_current_model_or_retry_actor(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):finish(f,h,j)
    expected=retry(tmp_path,p).data['result_object']
    (tmp_path/f.request.documents[0].path).unlink()  # Lost current target is not historical proof.
    value=prepare_authoring_request(command_id='change apply',actor={'actor_type':'human','actor_id':'later'},
        operations=p.data['operations'],request_id='request-1')
    result=resolve_normative_request(ProjectSource(tmp_path),value).data
    assert result['result_object']==expected and result['original_request']['actor']==ACTOR
    assert not result['current_target_verified'] and not result['authenticity_verified']


@pytest.mark.parametrize('value', ['request-1', {'request_id':'request-1'}, None, 1])
def test_analysis_style_values_cannot_trigger_normative_receipt_lookup(tmp_path,value):
    prepared(tmp_path)
    with patch('specroad.changes.idempotency._confirmed_receipt',side_effect=AssertionError('lookup')):
        with pytest.raises(ReceiptError) as error:
            resolve_normative_request(ProjectSource(tmp_path),value)
    assert error.value.exit_code==2


def test_analysis_correlation_object_is_not_coerced(tmp_path):
    @dataclass
    class AnalysisCorrelation:
        value: str
        namespace: str='analysis'
    prepared(tmp_path)
    with no_write_attempts(), pytest.raises(ReceiptError) as error:
        resolve_normative_request(ProjectSource(tmp_path),AnalysisCorrelation('request-1'))
    assert error.value.exit_code==2 and not (tmp_path/'.specroad/requests').exists()


@pytest.mark.parametrize('change', [dict(namespace='analysis'),dict(operation_sequence_sha256='0'*64),
    dict(receipt_checked=True),dict(write_authorized=True),dict(actor_authenticated=True),
    dict(format_version='invented'),dict(secret='do-not-leak'),dict(plan_sha256='0'*64)])
def test_relabelled_or_forged_authoring_bindings_never_read_receipts(tmp_path,change):
    prepared(tmp_path); data=request().data;data.update(change)
    with patch('specroad.changes.idempotency._confirmed_receipt',side_effect=AssertionError('lookup')):
        with pytest.raises(ReceiptError) as error:
            resolve_normative_request(ProjectSource(tmp_path),AuthoringRequest._create(data))
    assert error.value.exit_code==2 and 'do-not-leak' not in json.dumps(error.value.diagnostic())


@pytest.mark.parametrize('field',['operations','actor','request_id','dry_run','as_proposal','command_id'])
def test_missing_authoring_fields_are_machine_readable_refusals(tmp_path,field):
    prepared(tmp_path);data=request().data;del data[field]
    with pytest.raises(ReceiptError) as error:
        resolve_normative_request(ProjectSource(tmp_path),AuthoringRequest._create(data))
    assert error.value.exit_code==2


@pytest.mark.parametrize('kind',['symlink','hardlink','fifo','directory'])
def test_special_receipt_paths_are_rejected_without_repair(tmp_path,kind):
    with published(tmp_path) as (m,p,f,h,j):finish(f,h,j)
    q=tmp_path/request_receipt_path('request-1');saved=q.read_bytes();q.unlink()
    other=tmp_path/'receipt-copy';other.write_bytes(saved)
    if kind=='symlink':q.symlink_to(other)
    elif kind=='hardlink':os.link(other,q)
    elif kind=='fifo':os.mkfifo(q)
    else:q.mkdir()
    with no_write_attempts(), pytest.raises(ReceiptError):retry(tmp_path,p)
    assert other.read_bytes()==saved


def test_same_size_restored_timestamp_tampering_does_not_bypass_proof(tmp_path):
    with published(tmp_path) as (m,p,f,h,j):finish(f,h,j)
    q=tmp_path/request_receipt_path('request-1');before=q.stat();raw=q.read_bytes()
    altered=raw.replace(b'planner',b'changed');assert len(altered)==len(raw) and altered!=raw
    q.write_bytes(altered);os.utime(q,ns=(before.st_atime_ns,before.st_mtime_ns))
    with pytest.raises(ReceiptError):retry(tmp_path,p)


def test_copied_root_is_not_the_original_request_owner(tmp_path):
    root=tmp_path/'original'
    with published(root) as (m,p,f,h,j):finish(f,h,j)
    other=tmp_path/'copy';shutil.copytree(root,other)
    with pytest.raises(ReceiptError) as error:retry(other,p)
    assert error.value.exit_code==6


def test_late_authorizer_receipt_creation_cannot_start_publication(tmp_path):
    m,p,check=prepared(tmp_path);before=files(tmp_path)
    def race(request):
        q=tmp_path/request_receipt_path('request-1');q.parent.mkdir(parents=True);q.write_bytes(b'{}')
        return True
    authority=PublicationAuthority('explicit-host','1',race)
    with project_lock(tmp_path,kind='writer',command='change apply',project_id='sample',
                      request_id='request-1',transaction_id='new') as held:
        with pytest.raises(PublicationCheckError):
            begin_building_journal(check,held_lock=held,transaction_id='new',authority=authority)
    assert files(tmp_path)==before and not (tmp_path/'.specroad/transactions/new').exists()


def test_preview_is_neither_lookup_nor_locked_writer_request(tmp_path):
    prepared(tmp_path)
    value=prepare_authoring_request(command_id='change apply',actor=ACTOR,
        operations=[],request_id='request-1',dry_run=True)
    result=resolve_normative_request(ProjectSource(tmp_path),value).data
    assert result['action']=='not_applicable' and not result['locked_recheck_required']
