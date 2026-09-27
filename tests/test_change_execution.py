"""Change execution boundary; data/effects, not human console wording."""
from copy import deepcopy
from dataclasses import replace
from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from specroad.changes import (dry_run_change, apply_change_plan, execute_change_request,
    ChangeExecutionError, ChangeBackend, ChangePlan, PublicationReceipt)
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.targets import model, plan, gate, POLICY, resign
from support.folds import goal, edit, create, add_relation
from support.execution import Storage, FIELDS, rebuild


def case():
    a=goal();m=model([a]);p=plan(m,[edit(a,'Changed')]);return a,m,p


def test_dry_run_and_apply_retain_identical_plan_target_diff():
    a,m,p=case();store=Storage(m)
    preview=dry_run_change(p,m,policy=POLICY)
    actual=apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    for k in ['plan','plan_sha256','diff','impact','diagnostics','expected_model_root','assessment']:
        assert actual.data[k]==preview.data[k]
    assert actual.write_state=='committed' and preview.write_state=='not_committed'
    assert store.current.artifacts[0]['statement']=='Changed'
    assert store.current.artifacts[0]['revision']==a['revision']+1


def test_direct_and_saved_entry_use_same_plan_bytes():
    a,m,p=case();store=Storage(m)
    d=execute_change_request(m,[edit(a,'Changed')],dry_run=True,policy=POLICY,**FIELDS)
    r=execute_change_request(m,[edit(a,'Changed')],dry_run=False,policy=POLICY,backend=store.backend,**FIELDS)
    assert d.plan.source_bytes==r.plan.source_bytes==p.source_bytes
    assert store.requests[0].plan.source_bytes==p.source_bytes


def test_dry_run_ignores_even_an_unusable_backend():
    a,m,p=case()
    def forbidden(_): raise AssertionError('backend must never run')
    backend=ChangeBackend('forbidden','1',forbidden)
    r=execute_change_request(m,[edit(a,'Changed')],dry_run=True,policy=POLICY,backend=backend,**FIELDS)
    assert r.exit_code==0 and r.data['backend_receipt'] is None


def test_dry_run_preserves_actual_inventory_and_creates_no_receipt(tmp_path):
    a,m,p=case();store=Storage(m,tmp_path)
    before={x.relative_to(tmp_path).as_posix():x.read_bytes() for x in tmp_path.rglob('*') if x.is_file()}
    with patch.object(Path,'write_bytes',side_effect=AssertionError('write forbidden')), \
        patch.object(Path,'mkdir',side_effect=AssertionError('mkdir forbidden')):
        r=dry_run_change(p,m,policy=POLICY,fail_on_change=True)
    after={x.relative_to(tmp_path).as_posix():x.read_bytes() for x in tmp_path.rglob('*') if x.is_file()}
    assert before==after and store.events==[] and r.exit_code==1
    assert not (tmp_path/'.specroad').exists()


def test_actual_adapter_file_publication_matches_dry_run(tmp_path):
    a,m,p=case();store=Storage(m,tmp_path)
    preview=dry_run_change(p,m,policy=POLICY)
    result=apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    changed=json.loads((tmp_path/m.documents[0].path).read_bytes())
    assert changed==preview.plan.data['result_artifacts'][0]['artifact']
    assert result.data['backend_receipt']['target_root_sha256']==preview.data['expected_model_root']
    assert result.data['durability_verified'] is False


def test_native_writer_is_not_silently_invented():
    _,m,p=case()
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY)
    assert e.value.reason=='transaction_backend_required' and e.value.write_state=='not_committed'


def test_invalid_target_never_enters_backend():
    _,m,p=case();store=Storage(m)
    bad=gate(check=lambda c:c.result([{'reason':'invalid','severity':'error'}]))
    result=apply_change_plan(p,m,policy=POLICY,gates=[bad],backend=store.backend)
    assert not result.data['target_validated'] and result.exit_code!=0 and store.events==[]
    assert result.data['diagnostics'] and result.plan.sha256==p.sha256


def test_missing_required_gate_is_not_hidden_by_noop():
    from specroad.changes import TargetPolicy
    a=goal();m=model([a]);p=plan(m,[])
    r=dry_run_change(p,m,policy=TargetPolicy('command','1',('extension:required',)))
    assert not r.data['would_change'] and r.exit_code!=0


@pytest.mark.parametrize('changed,flag,code',[(False,False,0),(False,True,0),(True,False,0),(True,True,1)])
def test_fail_on_change_uses_real_semantic_difference(changed,flag,code):
    a=goal();m=model([a]);p=plan(m,[edit(a,'Changed')] if changed else [])
    r=dry_run_change(p,m,policy=POLICY,fail_on_change=flag)
    assert r.exit_code==code and r.data['would_change'] is changed
    assert r.write_state=='not_committed'


def test_noop_with_explicit_equal_update_is_not_a_change():
    a=goal();m=model([a]);p=plan(m,[edit(a,a['statement'])])
    r=dry_run_change(p,m,policy=POLICY,fail_on_change=True)
    assert r.exit_code==0 and not r.data['diff']['changed']


def test_unpublished_noop_requires_backend_too():
    a=goal();m=model([a]);p=plan(m,[])
    with pytest.raises(ChangeExecutionError):apply_change_plan(p,m,policy=POLICY)


def test_noop_publishes_no_artifact_bytes_but_needs_bound_receipt():
    a=goal();m=model([a]);p=plan(m,[]);store=Storage(m)
    r=apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert r.exit_code==0 and store.requests[0].documents==()
    assert store.current.source_files==m.source_files and r.data['backend_receipt'] is not None


def test_stale_plan_is_rejected_before_transaction():
    a,m,p=case();store=Storage(m);a['statement']='newer'
    with pytest.raises(ModelError):apply_change_plan(p,model([a]),policy=POLICY,backend=store.backend)
    assert store.events==[]


def test_live_base_is_revalidated_under_transaction():
    a,m,p=case();a['statement']='concurrent';store=Storage(model([a]))
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert e.value.reason=='publication_base_changed' and 'publish' not in store.events
    assert store.events[-1]=='exit'


def test_mismatched_receipt_never_reports_success():
    _,m,p=case();store=Storage(m);original=store.publish
    def publish(r):return replace(original(r),target_root_sha256='a'*64)
    store.publish=publish
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert e.value.reason=='publication_receipt_mismatch' and e.value.write_state=='unknown'
    assert store.current.artifacts[0]['statement']=='Changed'  # no destructive rollback


def test_readback_must_contain_actual_target_not_only_good_receipt():
    _,m,p=case();store=Storage(m)
    def publish(r):
        store.events.append('publish');d=r.data
        return PublicationReceipt(r.sha256,d['target_root_sha256'],d['request_id'],tuple(d['changed_paths']),'pretend')
    store.publish=publish
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert e.value.reason=='publication_target_mismatch'


def test_transaction_is_closed_before_success_returns():
    _,m,p=case();store=Storage(m)
    apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert store.events==['enter','read','publish','read','exit']


def test_after_publish_failure_is_unknown_and_not_automatically_retried():
    _,m,p=case();store=Storage(m);original=store.publish
    def fail(r):original(r);raise OSError('backend failure')
    store.publish=fail
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert e.value.write_state=='unknown' and not e.value.diagnostic()['retry_safe']
    assert len(store.requests)==1 and store.current.artifacts[0]['statement']=='Changed'


def test_returned_data_and_source_inputs_are_independent():
    a,m,p=case();before=deepcopy((a,m.source_files,p.source_bytes))
    r=dry_run_change(p,m,policy=POLICY);v=r.data;v['plan']['actor']['actor_id']='tampered'
    assert (a,m.source_files,p.source_bytes)==before
    assert r.plan.data['actor']['actor_id']!='tampered'
    with pytest.raises(TypeError):bool(r)


def test_saved_plan_hash_cannot_be_bypassed():
    _,m,p=case();bad=p.data;bad['request_id']='tampered'
    object.__setattr__(p,'source_bytes',json.dumps(bad).encode())
    with pytest.raises(ModelError):dry_run_change(p,m,policy=POLICY)


def test_strict_warning_remains_warning_and_blocks_publication():
    _,m,p=case();store=Storage(m)
    warning=gate(check=lambda c:c.result([{'severity':'warning','reason':'review'}]))
    d=dry_run_change(p,m,policy=POLICY,gates=[warning],strict=True,fail_on_change=True)
    assert d.exit_code==1 and d.data['diagnostics'][0]['severity']=='warning'
    r=apply_change_plan(p,m,policy=POLICY,gates=[warning],strict=True,backend=store.backend)
    assert r.exit_code==1 and store.events==[]


def test_fail_on_change_cannot_cause_write_then_failure():
    a,m,p=case();store=Storage(m)
    with pytest.raises(ChangeExecutionError) as e:
        execute_change_request(m,[edit(a,'Changed')],dry_run=False,fail_on_change=True,
            policy=POLICY,backend=store.backend,**FIELDS)
    assert e.value.exit_code==2 and store.events==[]


def test_new_artifact_apply_keeps_bound_id_and_time():
    a=goal(revision=1,created_at=FIELDS['planned_at'],updated_at=FIELDS['planned_at'],
           created_by=FIELDS['actor'],updated_by=FIELDS['actor']);m=model([]);p=plan(m,[create(a)]);store=Storage(m)
    d=dry_run_change(p,m,policy=POLICY);r=apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert r.plan.source_bytes==d.plan.source_bytes and store.current.artifacts==[a]
