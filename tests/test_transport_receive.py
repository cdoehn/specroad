"""18.r.W: actual guarded PH Apply creates only a native local draft."""
import pytest
from build_core import build_core

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.proposals import ProposalContext, ProposalOriginal
from specroad.proposals.project_validation import validate_proposal_project
from specroad.proposals.check import check_proposal_project
from specroad.proposals.apply import apply_project
from specroad.model.errors import ModelError
from support.transport_outbound import ROOT
from support.transport_receive import returned, receive


@pytest.fixture(scope='module')
def distribution(tmp_path_factory):
    return build_core(ROOT/'src',tmp_path_factory.mktemp('receive-core')/'build')


@pytest.mark.parametrize('route', ('module','pyz'))
@pytest.mark.parametrize('subproject', (False,True))
def test_receive_preserves_all_fachbytes_and_requires_later_local_review(tmp_path,distribution,route,subproject):
    handoff,package,proposal=returned(tmp_path,distribution,subproject=subproject)
    before=InspectionSnapshot(handoff['origin'],None).model.source_files
    outcome=receive(handoff,package,distribution[route=='pyz'])
    assert outcome['status']=='proposal_received',outcome
    assert outcome['patchharbor']['success'],outcome
    assert outcome['patchharbor']['result_status']=='created'
    assert not (handoff['repository']/'PATCHHARBOR_META').exists()
    assert not outcome['applied'] and not outcome['approval_granted']
    now=InspectionSnapshot(handoff['origin'],None).model.source_files
    assert {k:v for k,v in now.items() if k!=proposal.original.path}==before
    original=ProposalOriginal(now[proposal.original.path],path=proposal.original.path)
    assert original.binding.content_sha256==proposal.binding.content_sha256
    assert original.data['revision']==original.data['content_revision']==1
    assert original.data['proposal_status']==original.data['maturity']=='draft'
    assert original.data['reviews']==original.data['control_history']==[]
    assert outcome['draft_completion']['completion'] is not None
    assert validate_proposal_project(handoff['origin'],original.data['id']).exit_code==0
    checked=check_proposal_project(handoff['origin'],original.data['id'])
    assert checked.exit_code==0,checked.as_dict()
    from specroad.changes import PublicationAuthority
    with pytest.raises(ModelError):
        apply_project(handoff['origin'],original.data['id'],expected_revision=1,
            actor={'actor_type':'human','actor_id':'synthetic-applier'},planned_at='2026-11-18T00:00:00Z',
            change_plan_id='before-review',request_id='before-review',transaction_id='before-review',
            authority=PublicationAuthority('synthetic-test','1',lambda request:True))
    assert InspectionSnapshot(handoff['origin'],None).model.source_files==now


def test_native_roundtrip_then_separate_actual_fixture_review_and_apply(tmp_path,distribution):
    from support.proposal_decisions import ReviewCase
    from specroad.changes import PublicationAuthority
    from specroad.proposals.review_start import review_start_project
    handoff,package,proposal=returned(tmp_path,distribution)
    result=receive(handoff,package,distribution[0])
    assert result['status']=='proposal_received' and result['patchharbor']['success'],result
    root=handoff['origin']; model=InspectionSnapshot(root,None).model
    original=ProposalOriginal(model.source_files[proposal.original.path],path=proposal.original.path)
    # Use actual received originals; constructing a synthetic review host does
    # not create or replace any project files or fabricate review observations.
    case=ReviewCase.__new__(ReviewCase)
    case.root=root;case.originals=[original];case.contexts=[ProposalContext(original,model)]
    case.reviews=[];case.controls=[];case.current_decisions=True
    case.authority=PublicationAuthority('synthetic-roundtrip-review','1',lambda request:True)
    review_start_project(root,original.data['id'],expected_revision=1,
        actor={'actor_type':'human','actor_id':'synthetic-author'},planned_at='2026-11-18T01:00:00Z',
        change_plan_id='roundtrip-start',transaction_id='roundtrip-start',authority=case.authority)
    case.capture(start=True)
    case.decide(planned_at='2026-11-18T01:30:00Z')
    result=apply_project(root,original.data['id'],expected_revision=case.original.data['revision'],
        actor={'actor_type':'human','actor_id':'synthetic-applier'},planned_at='2026-11-18T02:00:00Z',
        change_plan_id='roundtrip-apply',transaction_id='roundtrip-apply',request_id='roundtrip-apply',
        authority=case.authority,services=case.services)
    assert result['proposal_status']=='applied' and result['completion'] is not None,result
    final=InspectionSnapshot(root,None).model
    from specroad.proposals.scope import specification_manifest
    assert specification_manifest(final).sha256 == proposal.data['change_plan']['expected_result']['model_root_sha256']
    assert next(a for a in final.artifacts if a['artifact_type']=='goal')['statement']=='Native proposed change'
    assert next(a for a in final.artifacts if a['id']==original.data['id'])['proposal_status']=='applied'


def test_receiver_never_supplies_missing_host_authority(tmp_path,distribution):
    handoff,package,_=returned(tmp_path,distribution)
    before=InspectionSnapshot(handoff['origin'],None).model.source_files
    result=receive(handoff,package,distribution[1],allow=False)
    assert result['status']=='failed' and not result['patchharbor']['success'],result
    assert result['draft_completion'] is None
    assert InspectionSnapshot(handoff['origin'],None).model.source_files==before


def test_explicit_transport_refusal_precedes_all_native_payload_writes(tmp_path,distribution):
    from support.transport_outbound import tree
    handoff,package,_=returned(tmp_path,distribution)
    before=tree(handoff['repository'])
    result=receive(handoff,package,distribution[0],transport_allow=False)
    assert result['status']=='failed' and not result['patchharbor']['success'],result
    assert not (handoff['repository']/'.specroad-return').exists()
    assert tree(handoff['repository'])==before
