"""Write policy behavior: no authentication, CLI wording or documentation oracle."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from unittest.mock import patch
import pytest
from specroad.changes import (AuthoringError, NormativeRequestId, AuthoringRequest,
    normalize_request_id, normalize_authoring_actor, prepare_authoring_request,
    bind_plan_authoring, apply_change_plan, execute_change_request,
    execute_change_plan_bytes, dry_run_change)
from specroad.model.audit_values import Actor
from support.targets import model, plan, POLICY, gate
from support.folds import goal, edit
from support.execution import FIELDS, Storage


def actor(kind='human'):
    return {'actor_type':kind, 'actor_id':'caller'}


def request(**options):
    values=dict(command_id='artifact update', actor=actor(), operations=[], request_id='Run-1')
    values.update(options)
    return prepare_authoring_request(**values)


def case(kind='human', request_id='Run-1'):
    a=goal();m=model([a]);fields={**FIELDS,'actor':actor(kind),'request_id':request_id}
    preview=execute_change_request(m,[edit(a,'Changed')],dry_run=True,policy=POLICY,**fields)
    return m,preview.plan


@pytest.mark.parametrize('kind',['human','ai','ci','tool'])
def test_actor_declaration_is_explicit_not_authenticated(kind):
    a=normalize_authoring_actor(actor(kind));assert a.as_fields()==actor(kind)
    r=request(actor=a, dry_run=True)
    assert r.data['actor']==actor(kind) and r.data['actor_authenticated'] is False
    assert not r.data['write_authorized']


@pytest.mark.parametrize('value',['a','A','0','run:branch_1.2-3','x'*128])
def test_normative_id_preserves_exact_characters(value):
    n=normalize_request_id(value)
    assert n.value==value and n.namespace=='normative_write'
    assert normalize_request_id(n)==n


@pytest.mark.parametrize('value',['',' a','a ','-a','x'*129,'ä','a/b','a\n',1,True])
def test_invalid_ids_are_usage_errors(value):
    with pytest.raises(AuthoringError) as e:normalize_request_id(value)
    assert e.value.exit_code==2


def test_human_request_is_bound_to_command_actor_and_operation():
    a=goal();x=request(operations=[edit(a,'one')]);y=request(operations=[edit(a,'two')])
    assert x.sha256!=y.sha256
    assert x.data['operation_sequence_sha256']!=y.data['operation_sequence_sha256']
    assert x.sha256!=request(operations=[edit(a,'one')],actor=actor('tool')).sha256
    assert x.sha256!=request(operations=[edit(a,'one')],command_id='change apply').sha256


def test_objects_and_input_lists_are_detached():
    a=goal();ops=[edit(a,'one')];who=actor();r=request(operations=ops,actor=who)
    snapshot=r.data;ops.clear();who['actor_id']='other';snapshot['operations'].clear()
    assert r.data['operations'] and r.data['actor']['actor_id']=='caller'
    with pytest.raises(FrozenInstanceError):r._encoded=b'{}'
    with pytest.raises(TypeError):bool(r)


@pytest.mark.parametrize('kind',['human','tool'])
def test_optional_id_not_automatically_generated(kind):
    r=request(actor=actor(kind),request_id=None)
    assert r.data['request_id'] is None and r.data['request_id_required'] is False
    assert r.data['receipt_checked'] is False and r.data['idempotency_guaranteed'] is False


@pytest.mark.parametrize('kind',['ai','ci'])
def test_actual_agent_write_requires_id(kind):
    with pytest.raises(AuthoringError) as e:request(actor=actor(kind),request_id=None)
    assert e.value.exit_code==2


def test_ai_direct_write_rejected_with_permission_code():
    with pytest.raises(AuthoringError) as e:request(actor=actor('ai'))
    assert e.value.exit_code==7 and e.value.reason=='ai_requires_proposal'


def test_ai_as_proposal_is_not_a_direct_permission():
    r=request(actor=actor('ai'),as_proposal=True)
    assert r.data['route']=='proposal_authoring' and r.data['specialist_required']
    assert not r.data['write_authorized']


@pytest.mark.parametrize('command',['proposal create','proposal change add','proposal review start','proposal apply'])
def test_ai_proposal_exceptions_require_specialist(command):
    r=request(actor=actor('ai'),command_id=command)
    assert r.data['route'] in ['proposal_management','approved_proposal_apply']
    assert r.data['specialist_required'] and not r.data['write_authorized']


@pytest.mark.parametrize('command',['relation review','proposal review'])
def test_ai_cannot_make_human_review(command):
    with pytest.raises(AuthoringError) as e:request(actor=actor('ai'),command_id=command)
    assert e.value.exit_code==7


def test_ai_dry_run_is_only_a_preview_without_request_receipt():
    r=request(actor=actor('ai'),request_id=None,dry_run=True)
    assert r.data['route']=='preview' and not r.data['write_authorized']


def test_human_apply_binds_exact_plan_in_backend_request():
    m,p=case();store=Storage(m);r=apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert r.write_state=='committed'
    binding=store.requests[0].data['authoring_binding']
    assert binding==bind_plan_authoring(p).data and binding['plan_sha256']==p.sha256
    assert binding['request_id']=='Run-1' and binding['operations']==p.data['operations']


def test_ci_apply_with_id_uses_same_backend_boundary():
    m,p=case('ci');store=Storage(m)
    r=apply_change_plan(p,m,policy=POLICY,backend=store.backend)
    assert r.write_state=='committed' and store.requests[0].data['authoring_binding']['actor']['actor_type']=='ci'


def test_denial_precedes_gate_and_transaction_and_creates_no_files(tmp_path):
    m,p=case('ai');store=Storage(m,tmp_path)
    before={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    def forbidden(c):raise AssertionError('not reached')
    with pytest.raises(AuthoringError) as e:
        apply_change_plan(p,m,policy=POLICY,gates=[gate(check=forbidden)],backend=store.backend)
    assert e.value.exit_code==7 and store.events==[]
    assert before=={p.relative_to(tmp_path):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_as_proposal_does_not_route_through_generic_writer():
    m,p=case('ai');store=Storage(m)
    with pytest.raises(AuthoringError) as e:apply_change_plan(p,m,policy=POLICY,as_proposal=True,backend=store.backend)
    assert e.value.reason=='proposal_workflow_required' and store.events==[]


def test_raw_plan_cannot_bypass_actor_policy():
    m,p=case('ai');store=Storage(m)
    with pytest.raises(AuthoringError):execute_change_plan_bytes(p.source_bytes,m,policy=POLICY,dry_run=False,backend=store.backend)
    assert store.events==[] and dry_run_change(p,m,policy=POLICY).write_state=='not_committed'


def test_analyzer_like_identifiers_do_not_supply_write_context():
    class AnalysisId:
        def __str__(self):raise AssertionError('must not convert')
    with pytest.raises(AuthoringError):normalize_request_id(AnalysisId())
    with pytest.raises(TypeError):request(analysis_id='same')


def test_policy_and_bindings_need_no_external_state():
    from support.io_guards import block_imports_and_open
    with block_imports_and_open():
        r=request(operations=[])
    assert r.data['route']=='direct' and not r.data['actor_authenticated']
