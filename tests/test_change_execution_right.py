"""Read-only boundary, fresh state and non-fabricated publication results."""
import json
from pathlib import Path
from contextlib import contextmanager
from dataclasses import replace
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import builtins
import pytest
from specroad.changes import (dry_run_change, apply_change_plan, execute_change_request,
    execute_change_plan_bytes, ChangeBackend, ChangeExecutionError,
    PublicationRequest, PublicationReceipt, ChangeExecutionResult, ChangePlan)
from specroad.validation import ModelDocument
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.errors import ModelError
from support.folds import goal, edit
from support.targets import model, plan, gate, POLICY
from support.execution import Storage, FIELDS, rebuild


def case():
    a=goal();m=model([a]);p=plan(m,[edit(a,'Changed')]);return a,m,p


def test_arbitrary_plan_whitespace_survives_dryrun_and_apply():
    _,m,p=case();raw=json.dumps(p.data,indent=3,ensure_ascii=False).encode()+b'\n'
    d=execute_change_plan_bytes(raw,m,dry_run=True,policy=POLICY)
    r=execute_change_plan_bytes(raw,m,dry_run=False,policy=POLICY,backend=Storage(m).backend)
    assert d.plan.source_bytes==r.plan.source_bytes==raw and d.plan.sha256==p.sha256


@pytest.mark.parametrize('raw',[b'{} {}',b'\xff',b'{"op":1,"op":2}',b'{}\x00',b'{"x":NaN}'])
def test_invalid_raw_plan_never_opens_backend(raw):
    _,m,_=case();store=Storage(m)
    with pytest.raises(ModelError):execute_change_plan_bytes(raw,m,dry_run=False,policy=POLICY,backend=store.backend)
    assert not store.events


@pytest.mark.parametrize('raw',['plan.json',Path('/not/to/be/opened'),'https://host/plan',{},bytearray(b'{}')])
def test_nonbytes_are_not_opened_or_converted(raw):
    _,m,_=case()
    with patch.object(builtins,'open',side_effect=AssertionError('open forbidden')):
        with pytest.raises(ChangeExecutionError) as e:execute_change_plan_bytes(raw,m,dry_run=True,policy=POLICY)
    assert e.value.exit_code==2


@pytest.mark.parametrize('option,value',[('strict',1),('strict',None),('fail_on_change','yes'),('fail_on_change',0)])
def test_boolean_modes_are_strict(option,value):
    _,m,p=case()
    with pytest.raises(ChangeExecutionError) as e:dry_run_change(p,m,policy=POLICY,**{option:value})
    assert e.value.exit_code==2


def test_dry_run_of_readonly_files_leaves_modes_and_inventory_unchanged(tmp_path):
    a,m,p=case();Storage(m,tmp_path)
    files=[q for q in tmp_path.rglob('*') if q.is_file()]
    for q in files:q.chmod(0o444)
    before={str(q.relative_to(tmp_path)):(q.read_bytes(),q.stat().st_mode) for q in files}
    with patch.object(Path,'open',side_effect=AssertionError('no I/O expected')):
        d=execute_change_plan_bytes(p.source_bytes,m,dry_run=True,policy=POLICY,fail_on_change=True)
    assert d.exit_code==1 and d.data['backend_receipt'] is None
    assert {str(q.relative_to(tmp_path)):(q.read_bytes(),q.stat().st_mode) for q in tmp_path.rglob('*') if q.is_file()}==before


def test_optional_extra_plan_keys_and_missing_keys_are_usage_errors():
    a,m,_=case()
    for fields in ({**FIELDS,'foreign':1},{k:v for k,v in FIELDS.items() if k!='planned_at'}):
        with pytest.raises(ChangeExecutionError) as e:
            execute_change_request(m,[edit(a,'Changed')],dry_run=True,policy=POLICY,**fields)
        assert e.value.exit_code==2


def test_different_local_root_cannot_reuse_publication_binding():
    _,m,p=case();other=rebuild(m,binding=ProjectReadBinding('sample','/other',(9,9)));store=Storage(other)
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert e.value.reason=='publication_base_changed' and 'publish' not in store.events


def test_same_semantic_root_with_changed_bytes_still_rejects_stale_handoff():
    _,m,p=case();d=m.documents[0]
    formatted=ModelDocument(d.path,json.dumps(json.loads(d.content),indent=4).encode())
    store=Storage(rebuild(m,documents=[formatted]))
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert e.value.reason=='publication_base_changed' and 'publish' not in store.events


def test_reservation_change_is_not_hidden_by_same_model_hash():
    _,m,p=case();store=Storage(rebuild(m,reserved_artifact_ids=[goal(2)['id']]))
    with pytest.raises(ChangeExecutionError):apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert 'publish' not in store.events


def test_change_during_second_gate_is_caught_before_publish():
    a,m,p=case();store=Storage(m);calls=[]
    def check(c):
        calls.append(1)
        if len(calls)==2:
            a['statement']='concurrent';store.current=model([a])
        return c.result()
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,gates=[gate(check=check)],backend=store.backend)
    assert e.value.reason=='publication_base_changed' and 'publish' not in store.events


def test_gate_turning_red_under_lock_is_not_published():
    _,m,p=case();store=Storage(m);calls=[]
    def check(c):
        calls.append(1)
        return c.result([] if len(calls)==1 else [{'reason':'denied','severity':'error'}])
    r=apply_change_plan(p,m,policy=POLICY,gates=[gate(check=check)],backend=store.backend)
    assert r.exit_code!=0 and r.write_state=='not_committed' and 'publish' not in store.events


def test_internal_gate_exception_beats_fail_on_change():
    _,m,p=case()
    def check(c):raise RuntimeError('no')
    d=dry_run_change(p,m,policy=POLICY,gates=[gate(check=check)],fail_on_change=True)
    assert d.exit_code==4 and d.data['would_change'] and not d.data['target_validated']


def test_mutated_factory_handoff_is_rejected():
    _,m,p=case();store=Storage(m)
    @contextmanager
    def factory(r):
        object.__setattr__(r,'_encoded',b'{}')
        yield store
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=ChangeBackend('test','1',factory))
    assert e.value.reason=='publication_request_changed' and 'publish' not in store.events


def test_mutated_publisher_handoff_is_not_success():
    _,m,p=case();store=Storage(m);original=store.publish
    def publish(r):
        out=original(r);object.__setattr__(r,'_plan_bytes',b'{}');return out
    store.publish=publish
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert e.value.reason=='publication_request_changed' and e.value.write_state=='unknown'


@pytest.mark.parametrize('field,value',[('request_sha256','b'*64),('request_id','other'),('published_paths',()),('published_paths',('other.json',))])
def test_receipt_is_bound_to_complete_request_not_only_target(field,value):
    _,m,p=case();store=Storage(m);original=store.publish
    def publish(r):return replace(original(r),**{field:value})
    store.publish=publish
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert e.value.reason=='publication_receipt_mismatch'


def test_boolean_receipt_is_not_a_committed_result():
    _,m,p=case();store=Storage(m);store.publish=lambda _:True
    with pytest.raises(ChangeExecutionError):apply_change_plan(p,m,policy=POLICY,backend=store.backend)


def test_exit_failure_after_successful_publish_is_not_hidden():
    _,m,p=case();store=Storage(m)
    @contextmanager
    def factory(r):
        yield store
        raise OSError('cannot complete durable phase')
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=ChangeBackend('test','1',factory))
    assert e.value.write_state=='unknown' and store.current.artifacts[0]['statement']=='Changed'


def test_suppressed_backend_exception_cannot_turn_into_success():
    _,m,p=case();store=Storage(m)
    @contextmanager
    def factory(r):
        try:yield store
        except Exception:pass
    store.publish=lambda r:(_ for _ in ()).throw(OSError('failed'))
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=ChangeBackend('test','1',factory))
    assert e.value.reason=='publication_not_confirmed' and e.value.write_state=='unknown'


def test_partial_actual_write_is_preserved_without_automatic_rollback(tmp_path):
    a,b=goal(),goal(1);m=model([a,b]);p=plan(m,[edit(a,'A'),edit(b,'B')]);store=Storage(m,tmp_path)
    calls=[]
    def publish(r):
        calls.append(1);d=r.documents[0];(tmp_path/d.path).write_bytes(d.content);raise OSError('interrupted')
    store.publish=publish
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert calls==[1] and e.value.write_state=='unknown'
    assert json.loads((tmp_path/m.documents[0].path).read_bytes())['statement']=='A'
    assert (tmp_path/m.documents[1].path).read_bytes()==m.documents[1].content


def test_readback_missing_unchanged_artifact_is_rejected():
    a,b=goal(),goal(1);m=model([a,b]);p=plan(m,[edit(a,'A')]);store=Storage(m);original=store.publish
    def publish(r):
        out=original(r);store.current=rebuild(store.current,documents=store.current.documents[:1]);return out
    store.publish=publish
    with pytest.raises(ChangeExecutionError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert e.value.reason=='publication_target_mismatch'


def test_readback_must_preserve_original_bytes_of_unchanged_files():
    a,b=goal(),goal(1);m=model([a,b]);p=plan(m,[edit(a,'A')]);store=Storage(m);original=store.publish
    def publish(r):
        out=original(r);ds=list(store.current.documents);d=ds[1]
        ds[1]=ModelDocument(d.path,json.dumps(json.loads(d.content),indent=4).encode())
        store.current=rebuild(store.current,documents=ds);return out
    store.publish=publish
    with pytest.raises(ChangeExecutionError):apply_change_plan(p,m,policy=POLICY,backend=store.backend)


def test_large_complete_diff_is_not_truncated():
    originals=[goal(i) for i in range(151)];m=model(originals);p=plan(m,[edit(a,'Changed') for a in originals])
    d=dry_run_change(p,m,policy=POLICY,fail_on_change=True)
    store=Storage(m);r=apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert len(d.data['diff']['changes'])==151 and len(r.data['backend_receipt']['published_paths'])==151
    assert r.data['expected_model_root']==d.data['expected_model_root']


def test_reused_dryrun_inputs_have_no_shared_state_between_calls():
    _,m,p=case()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:dry_run_change(p,m,policy=POLICY).data,range(12)))
    assert all(r==results[0] for r in results)


def test_changed_then_restored_value_is_noop_not_rewritten_metadata():
    a=goal();m=model([a]);p=plan(m,[edit(a,'Temporary'),edit(a,a['statement'])])
    d=dry_run_change(p,m,policy=POLICY,fail_on_change=True)
    assert d.exit_code==0 and not d.data['would_change']


def test_registered_gate_observes_all_target_artifacts_for_each_check():
    a,b=goal(),goal(1);m=model([a,b]);p=plan(m,[edit(a,'Changed')]);seen=[]
    def check(c):seen.append(c.subjects);return c.result()
    apply_change_plan(p,m,policy=POLICY,backend=Storage(m).backend,gates=[gate(check=check)])
    assert len(seen)==2 and all(set(s)=={a['id'],b['id']} for s in seen)


def test_normal_python_data_cannot_forge_an_execution_result():
    for cls in (PublicationRequest,ChangeExecutionResult):
        with pytest.raises(TypeError):cls({'write_state':'committed'})


def test_saved_dryrun_does_not_invoke_clock_environment_or_file_access():
    import time,os
    _,m,p=case()
    with patch.object(time,'time',side_effect=AssertionError('clock')), \
        patch.object(os,'getenv',side_effect=AssertionError('environment')), \
        patch.object(builtins,'open',side_effect=AssertionError('file')):
        assert dry_run_change(p,m,policy=POLICY).exit_code==0


def test_shifted_module_and_zipapp_support_saved_dry_run(tmp_path):
    from support.portable import build_distribution
    from support.processes import run_python
    module,archive=build_distribution(tmp_path/'delivery')
    moved=tmp_path/'moved';module.rename(moved);movedzip=tmp_path/'moved.pyz';archive.rename(movedzip)
    _,m,p=case()
    body="""import sys
sys.path.insert(0,sys.argv[1])
from specroad.changes import TargetModel,TargetPolicy,execute_change_plan_bytes
from specroad.validation import ModelDocument
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource,compose_profiles
p=ProfileResource(%r)
m=TargetModel(%r,ProjectReadBinding('sample','/provided',(1,2)),[ModelDocument(%r,%r)],
profile=compose_profiles([p],core_key=p.key),resource_files=[ModelDocument('profiles/core.json',p.source_bytes)])
r=execute_change_plan_bytes(%r,m,dry_run=True,policy=TargetPolicy('ordinary-change','1',()),fail_on_change=True)
assert r.exit_code==1 and r.write_state=='not_committed'
assert r.plan.sha256==%r and r.data['expected_model_root']==%r
"""%(m.resource_files[0].content,m.configuration_bytes,m.documents[0].path,m.documents[0].content,
       p.source_bytes,p.sha256,p.data['expected_result']['model_root_sha256'])
    for location in (moved,movedzip):
        result=run_python(['-I','-S','-B','-c',body,str(location)],tmp_path,capture=True)
        assert result.returncode==0,result.stderr
