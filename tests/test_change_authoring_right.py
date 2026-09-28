"""Robustness at the actual authoring gate; no output snapshots."""
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from specroad.changes import (AuthoringError, NormativeRequestId, normalize_request_id,
    normalize_authoring_actor, prepare_authoring_request, bind_plan_authoring,
    apply_change_plan, execute_change_request, execute_change_plan_bytes,
    ChangePlan, ChangePlanError, change_plan_schema, PublicationReceipt)
from specroad.model.audit_values import Actor
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from support.targets import model, plan, POLICY, gate
from support.folds import goal, edit
from support.execution import Storage, FIELDS
from test_change_authoring import case, request, actor


@pytest.mark.parametrize('kind',['ai','ci'])
@pytest.mark.parametrize('entry',['direct','saved','bytes'])
def test_missing_agent_request_id_denied_before_any_publication(kind,entry,tmp_path):
    m,p=case(kind,request_id=None);store=Storage(m,tmp_path)
    original={q.relative_to(tmp_path):q.read_bytes() for q in tmp_path.rglob('*') if q.is_file()}
    def check(_):raise AssertionError('no checker invocation on usage error')
    kw=dict(policy=POLICY,backend=store.backend,gates=[gate(check=check)])
    with pytest.raises(AuthoringError) as e:
        if entry=='saved':apply_change_plan(p,m,**kw)
        elif entry=='bytes':execute_change_plan_bytes(p.source_bytes,m,dry_run=False,**kw)
        else:
            fields={**FIELDS,'actor':actor(kind)};fields.pop('request_id')
            execute_change_request(m,[edit(m.artifacts[0],'Changed')],dry_run=False,**fields,**kw)
    assert e.value.exit_code==2 and e.value.reason=='normative_request_id_required'
    assert store.events==[] and original=={q.relative_to(tmp_path):q.read_bytes() for q in tmp_path.rglob('*') if q.is_file()}


@pytest.mark.parametrize('kind',['human','tool'])
def test_optional_request_id_is_null_through_plan_and_real_test_receipt(kind,tmp_path):
    a=goal();m=model([a]);store=Storage(m,tmp_path);fields={**FIELDS,'actor':actor(kind)};fields.pop('request_id')
    r=execute_change_request(m,[edit(a,'New')],dry_run=False,policy=POLICY,backend=store.backend,**fields)
    assert r.write_state=='committed' and r.plan.data['request_id'] is None
    assert r.data['backend_receipt']['request_id'] is None
    assert json.loads((tmp_path/m.documents[0].path).read_bytes())['statement']=='New'
    assert not (tmp_path/'.specroad/requests').exists()


@pytest.mark.parametrize('value',['bad id','../other','é',False,[],{},'x'*129])
def test_saved_plan_invalid_request_does_not_become_valid_after_resigning(value):
    _,p=case();d=p.data;d['request_id']=value;d.pop('change_plan_sha256')
    d['change_plan_sha256']=canonical_json_sha256(d)
    with pytest.raises(ChangePlanError):ChangePlan(canonical_json_bytes(d))


def test_missing_saved_request_field_still_is_not_silently_defaulted():
    _,p=case();d=p.data;d.pop('request_id');d.pop('change_plan_sha256');d['change_plan_sha256']=canonical_json_sha256(d)
    with pytest.raises(ChangePlanError):ChangePlan(canonical_json_bytes(d))


def test_schema_and_parser_agree_on_absent_and_invalid_request_values():
    from specroad.model._schema import validate_builtin
    m,p=case(request_id=None);validate_builtin(p.data,change_plan_schema())
    bad=p.data;bad['request_id']='not valid'
    with pytest.raises(ChangePlanError):ChangePlan(canonical_json_bytes(bad))


def test_typed_request_and_actor_are_normalized_before_plan_construction():
    a=goal();m=model([a]);kw={**FIELDS,'actor':Actor('human','Case Sensitive'), 'request_id':NormativeRequestId('Run:One')}
    r=execute_change_request(m,[],dry_run=True,policy=POLICY,**kw)
    assert r.plan.data['actor']['actor_id']=='Case Sensitive' and r.plan.data['request_id']=='Run:One'


def test_same_request_string_does_not_mask_different_operations():
    a=goal();m=model([a]);x=bind_plan_authoring(plan(m,[edit(a,'one')],request_id='same'))
    y=bind_plan_authoring(plan(m,[edit(a,'two')],request_id='same'))
    assert x.data['request_id']==y.data['request_id'] and x.sha256!=y.sha256
    assert not x.data['receipt_checked'] and not x.data['idempotency_guaranteed']


def test_normalized_hash_ignores_object_key_order_not_array_order():
    a=goal();ops=[edit(a,'a'),edit(a,'b')]
    x=request(operations=ops);y=request(operations=[dict(reversed(list(o.items()))) for o in ops])
    assert x.sha256==y.sha256
    assert x.sha256!=request(operations=list(reversed(ops))).sha256


def test_same_saved_plan_formatting_retains_semantic_authoring_binding():
    m,p=case();q=ChangePlan(json.dumps(p.data,ensure_ascii=False,indent=3).encode())
    assert q.source_bytes!=p.source_bytes and bind_plan_authoring(p).sha256==bind_plan_authoring(q).sha256


@pytest.mark.parametrize('kind',['ai','ci','tool'])
@pytest.mark.parametrize('command',['relation review','proposal review'])
def test_nonhuman_review_is_not_enabled_by_proposal_flag(kind,command):
    with pytest.raises(AuthoringError) as e:request(actor=actor(kind),command_id=command,as_proposal=True)
    assert e.value.exit_code==7


@pytest.mark.parametrize('command',['proposal change update','proposal change remove','proposal change move'])
def test_other_proposal_management_exceptions_never_authorize_generic_writes(command):
    r=request(actor=actor('ai'),command_id=command)
    assert r.data['specialist_required'] and not r.data['write_authorized']


@pytest.mark.parametrize('command',['proposal create','proposal apply','proposal review start'])
def test_specialist_commands_cannot_recursively_wrap_themselves(command):
    with pytest.raises(AuthoringError) as e:request(command_id=command,as_proposal=True)
    assert e.value.exit_code==2


@pytest.mark.parametrize('kind',['human','ci','tool'])
def test_as_proposal_is_never_ordinary_write_for_any_actor(kind):
    m,p=case(kind);store=Storage(m)
    with pytest.raises(AuthoringError) as e:apply_change_plan(p,m,policy=POLICY,backend=store.backend,as_proposal=True)
    assert e.value.reason=='proposal_workflow_required' and store.events==[]


@pytest.mark.parametrize('command',['analysis run','version','artifact update; echo bad','change apply ','proposal'])
def test_unknown_or_analysis_commands_have_no_normative_route(command):
    with pytest.raises(AuthoringError):request(command_id=command)


@pytest.mark.parametrize('bad',[None,True,{}, {'actor_type':'human'}, {'actor_type':'human','actor_id':'','token':'secret'}])
def test_actor_errors_do_not_guess_from_environment(bad):
    with patch.dict('os.environ',{'USER':'human','ACTOR_ID':'guessed'}):
        with pytest.raises(AuthoringError):request(actor=bad)


def test_foreign_id_object_is_not_converted_even_when_value_would_match():
    @dataclass
    class AnalysisId: value: str
    with pytest.raises(AuthoringError):normalize_request_id(AnalysisId('same'))
    assert normalize_request_id('same').namespace=='normative_write'


def test_subclass_conversion_hooks_are_never_executed():
    class Text(str):
        def __str__(self):raise AssertionError('bad')
    with pytest.raises(AuthoringError):normalize_request_id(Text('good'))
    with pytest.raises(AuthoringError):request(actor={'actor_type':Text('human'),'actor_id':'x'})


def test_diagnostic_does_not_leak_invalid_identity():
    secret='private bad request token'
    with pytest.raises(AuthoringError) as e:normalize_request_id(secret)
    assert secret not in json.dumps(e.value.diagnostic())
    assert e.value.diagnostic()['write_state']=='not_committed'


def test_many_operations_remain_complete_and_independent():
    a=goal();ops=[edit(a,str(i)) for i in range(151)];r=request(operations=ops)
    assert len(r.data['operations'])==151
    ops[100]['patch'][0]['value']='tampered'
    assert r.data['operations'][100]['patch'][0]['value']=='100'


def test_noop_agent_request_is_still_a_normative_write():
    a=goal();m=model([a]);kw={**FIELDS,'actor':actor('ci')};kw.pop('request_id')
    with pytest.raises(AuthoringError) as e:execute_change_request(m,[],dry_run=False,policy=POLICY,**kw)
    assert e.value.exit_code==2


def test_actor_identity_bytes_are_not_trimmed_or_unicode_normalized():
    who={'actor_type':'human','actor_id':' A\u0308 '}
    assert normalize_authoring_actor(who).as_fields()==who


def test_repeated_preview_cannot_change_to_ai_write_permission():
    m,p=case('ai');store=Storage(m)
    preview=bind_plan_authoring(p,dry_run=True)
    assert preview.data['route']=='preview'
    with pytest.raises(AuthoringError):apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert store.events==[]


def test_shifted_module_and_zipapp_keep_request_namespace_and_policy(tmp_path):
    from support.portable import build_distribution
    from support.processes import run_python
    module,archive=build_distribution(tmp_path/'delivery')
    moved=tmp_path/'moved';module.rename(moved);z=tmp_path/'moved.pyz';archive.rename(z)
    body="""import sys
sys.path.insert(0,sys.argv[1])
from specroad.changes import NormativeRequestId, prepare_authoring_request, AuthoringError
id=NormativeRequestId('Req:One')
r=prepare_authoring_request(command_id='artifact create',actor={'actor_type':'human','actor_id':'H'},operations=[],request_id=id)
assert r.data['request_id']=='Req:One' and r.data['namespace']=='normative_write'
assert r.data['write_authorized'] is False
try:
 prepare_authoring_request(command_id='artifact create',actor={'actor_type':'ai','actor_id':'A'},operations=[],request_id=id)
except AuthoringError as e:
 assert e.exit_code==7
else: raise AssertionError('AI direct write passed')
"""
    for location in (moved,z):
        result=run_python(['-I','-S','-B','-c',body,str(location)],tmp_path,capture=True)
        assert result.returncode==0,result.stderr
