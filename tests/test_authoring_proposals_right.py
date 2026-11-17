"""Refusals preserve real source bytes, authority, scope and native receipts."""
from copy import deepcopy
import pytest
from specroad.authoring.execution import apply_authoring_plan
from specroad.authoring.proposals import prepare_authoring_proposal
from specroad.changes import ChangeOperation, PublicationAuthority, prepare_change_plan
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.proposal_fields import MODEL_FIELDS
from support.authoring_proposals import planned, metadata
from support.read_only import inventory, no_write_attempts

ALLOW = PublicationAuthority('owned-host', '1', lambda request: True)


def options(plan, gates):
    return dict(command_id='artifact.update', gates=gates, proposal_fields=metadata(plan),
                transaction_id='txn-route', authority=ALLOW, as_proposal=True)


def test_ai_direct_write_refused_but_actual_draft_write_keeps_ai_actor(tmp_path):
    root=tmp_path/'project'; model,plan,gates=planned(root,actor='ai'); before=inventory(root)
    with pytest.raises(ModelError) as caught:
        apply_authoring_plan(plan, model, command_id='artifact.update', gates=gates,
                            transaction_id='txn-direct', authority=ALLOW)
    assert caught.value.exit_code == 7 and inventory(root) == before
    args=options(plan,gates)
    args['proposal_fields']['model_provenance']={**{key:'unknown' for key in MODEL_FIELDS},
        'unknown_reasons':{key:'Synthetic test does not claim a model observation.' for key in MODEL_FIELDS}}
    for row in args['proposal_fields']['changes']: row['confidence']=0.5
    result=apply_authoring_plan(plan,model,**args)
    assert result['proposal']['created_by'] == plan.data['actor']
    assert result['proposal']['reviews'] == [] and not result['approval_granted']
    for path,raw in model.source_files.items(): assert (root/path).read_bytes() == raw


@pytest.mark.parametrize('bad', ['authority','metadata','scope','actor','collision'])
def test_native_refusals_cannot_be_bypassed_by_proposal_metadata(tmp_path,bad):
    root=tmp_path/'project'; model,plan,gates=planned(root); args=options(plan,gates)
    if bad == 'authority': args['authority']=PublicationAuthority('deny','1',lambda request:False)
    elif bad == 'metadata': args['proposal_fields']['authority']=True
    elif bad == 'scope': args['proposal_fields']['scope_descriptor']={'scope_kind':'project'}
    elif bad == 'actor': args['proposal_fields']['actor']={'actor_type':'human','actor_id':'forged'}
    else:
        proposal=prepare_authoring_proposal(plan,model,command_id='artifact.update',
            proposal_fields=args['proposal_fields'],gates=gates)
        path=root/proposal.original.path;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(proposal.source_bytes)
    before=inventory(root)
    with pytest.raises(ModelError): apply_authoring_plan(plan,model,**args)
    # Native lock directories may have existed already; normative inputs stay exact.
    for path,raw in model.source_files.items(): assert (root/path).read_bytes() == raw
    assert {p:r for p,*r in inventory(root) if not p.startswith('.specroad/')} == {
        p:r for p,*r in before if not p.startswith('.specroad/')}


def test_changed_request_binding_does_not_reuse_original_receipt(tmp_path):
    root=tmp_path/'project'; model,plan,gates=planned(root); args=options(plan,gates)
    apply_authoring_plan(plan,model,**args); before=inventory(root)
    args['proposal_fields']['rationale']='A different publication request'
    args['transaction_id']='txn-conflict'
    with pytest.raises(ModelError) as caught: apply_authoring_plan(plan,model,**args)
    assert caught.value.exit_code == 6 and inventory(root) == before


def test_missing_ai_request_id_refused_before_authority_or_publication(tmp_path):
    root=tmp_path/'project'; model,plan,gates=planned(root,actor='ai')
    value=plan.data;value.pop('change_plan_sha256');value['request_id']=None
    plan=prepare_change_plan(value); calls=[];args=options(plan,gates)
    args['authority']=PublicationAuthority('observe','1',lambda request:calls.append(request) or True)
    before=inventory(root)
    with pytest.raises(ModelError) as caught: apply_authoring_plan(plan,model,**args)
    assert caught.value.exit_code == 2 and not calls and inventory(root) == before


def test_create_operation_cannot_grant_generic_or_nested_control_writes(tmp_path):
    from specroad.changes import prepare_authoring_request
    model,plan,gates=planned(tmp_path/'project')
    proposal=prepare_authoring_proposal(plan,model,command_id='artifact.update',
        proposal_fields=metadata(plan),gates=gates)
    op={'op':'proposal_create','record':proposal.data}
    for command in ('change apply','artifact create','proposal apply'):
        with pytest.raises(ModelError):
            prepare_authoring_request(command_id=command,actor=plan.data['actor'],
                request_id=plan.data['request_id'],operations=[op])
    with pytest.raises(ModelError):
        ChangeOperation({'op':'create','artifact':proposal.data,'result_id':proposal.data['id']})
    altered=deepcopy(op);altered['record']['proposal_status']='approved'
    with pytest.raises(ModelError): ChangeOperation(altered)


@pytest.mark.parametrize('case', ['first_document','supporting_document','root_section','nested_section',
                                 'move_document','move_section','reorder','promote'])
def test_complete_document_authoring_plans_keep_all_defaults_and_operations(tmp_path,case):
    from test_document_authoring import document_project,preview_case,saved
    model=document_project(tmp_path/'project',first=case=='first_document')
    report=preview_case(model,case);plan=saved(report)
    with no_write_attempts():
        proposal=prepare_authoring_proposal(plan,model,command_id=report['command_id'],
                                            proposal_fields=metadata(plan))
    for key in ('operations','result_artifacts','preconditions'):
        assert proposal.data['change_plan'][key] == plan.data[key]


@pytest.mark.parametrize('case',['update','block_remove','empty','cascade','move'])
def test_composite_document_mutations_keep_the_entire_native_plan(tmp_path,case):
    from test_document_mutations import mutation_project,mutation
    from specroad.changes import ChangePlan
    model=mutation_project(tmp_path/'project');report=mutation(model,case);plan=ChangePlan(jcs(report['plan']))
    proposal=prepare_authoring_proposal(plan,model,command_id=report['command_id'],proposal_fields=metadata(plan))
    assert proposal.data['change_plan']['operations'] == plan.data['operations']
    assert proposal.data['change_plan']['result_artifacts'] == plan.data['result_artifacts']


@pytest.mark.parametrize('family',['record','import'])
def test_evidence_redirect_preserves_all_measured_inputs_without_inventing_results(tmp_path,family):
    from specroad.changes import ChangePlan
    if family=='record':
        from test_evidence_recording import project,measurement,preview
        model=project(tmp_path/'project');report=preview(model,measurement(model))
    else:
        from test_evidence_import_transaction import import_project,preview
        model=import_project(tmp_path/'project');report=preview(model)
    plan=ChangePlan(jcs(report['plan']))
    proposal=prepare_authoring_proposal(plan,model,command_id=report['command_id'],proposal_fields=metadata(plan))
    assert proposal.data['change_plan']['operations'] == plan.data['operations']
    assert proposal.data['change_plan']['result_artifacts'] == plan.data['result_artifacts']


def test_confirmed_retry_never_replans_or_reauthorizes_the_current_target(tmp_path,monkeypatch):
    import specroad.authoring.proposals as publication
    root=tmp_path/'project';model,plan,gates=planned(root);args=options(plan,gates)
    original=apply_authoring_plan(plan,model,**args);before=inventory(root)
    def forbidden(*args,**kwargs): raise AssertionError('No current target evaluation on confirmed replay')
    monkeypatch.setattr(publication,'prepare_authoring_proposal',forbidden)
    args['authority']=PublicationAuthority('unused-replay-authority','1',forbidden)
    args['transaction_id']='txn-confirmed-retry'
    with no_write_attempts(): repeated=apply_authoring_plan(plan,model,**args)
    assert repeated['replayed'] and not repeated['completion']['current_target_verified']
    assert repeated['completion']['receipts'] == original['completion']['receipts']
    assert inventory(root) == before
    # A receipt does not make malformed call options or transaction IDs valid.
    for invalid in ({'transaction_id':'../invalid'}, {'strict':'true'}, {'gates':object()}):
        with no_write_attempts(), pytest.raises(ModelError):
            apply_authoring_plan(plan,model,**{**args,**invalid})
        assert inventory(root) == before
