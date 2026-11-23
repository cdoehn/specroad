"""Actual public AI redirection cannot grant direct authority or a review."""
import pytest
from specroad.authoring.native_intents import COMMANDS
from specroad.cli.commands import builtin_registry
from specroad.cli.application import execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.model.canonical import canonical_json_bytes as jcs
from support.model import put
from support.native_plan_authoring import example, files, values, ALLOW, proposal_input


@pytest.mark.parametrize('name',COMMANDS)
def test_public_ai_authoring_refuses_direct_write_before_any_effect(tmp_path,name):
    root=tmp_path/'p';request=example(root,builtin_registry().resolve(name))
    request['options'].pop('--dry-run',None)
    request['options'].update({'--actor-type':'ai','--request-id':'ai-direct'})
    before=files(root)
    response=execute_request(request,cwd=root,context_builder=InvocationContextBuilder(publication_authority=ALLOW)).result
    assert response.exit_code==7 and files(root)==before,response


@pytest.mark.parametrize('name',['artifact.create','artifact.update','relation.add','document.create',
    'section.add','block.add','view.create','baseline.create','evidence.import'])
def test_public_ai_redirect_publishes_only_an_explicit_proposal_and_replays(tmp_path,name):
    root=tmp_path/'p';request=example(root,builtin_registry().resolve(name))
    request['options'].pop('--dry-run',None)
    put(root,'proposal-input.json',jcs(proposal_input()))
    request['options'].update({'--actor-type':'ai','--request-id':'ai-proposal',
        '--as-proposal':True,'--proposal-input':'proposal-input.json'})
    before=files(root);original=values(root)
    builder=InvocationContextBuilder(publication_authority=ALLOW)
    response=execute_request(request,cwd=root,context_builder=builder).result
    if name=='baseline.create':
        # 10.8.1 permanently excludes baseline targets from Proposals.
        # Retain this case and ID as an explicit refusal oracle.
        assert response.exit_code==3,response.as_dict()
        assert response.details['diagnostic']['reason']=='proposal_control_target_forbidden'
        attempt=response.details['authoring_attempt']
        assert attempt['write_state']=='not_committed'
        assert attempt['recovery_required'] is False and attempt['approval_granted'] is False
        assert files(root)==before and values(root)==original
        retry=execute_request(request,cwd=root,context_builder=builder).result
        assert retry.exit_code==3,retry.as_dict()
        assert retry.details['diagnostic']['reason']=='proposal_control_target_forbidden'
        assert files(root)==before
        return
    assert response.exit_code==0,response.as_dict()
    # Read the new immutable draft directly: loading its future review inputs
    # is intentionally a separate native service, not fabricated by this test.
    import json
    drafts=[v for p,raw in files(root).items() if p.endswith('.json') and p not in before
        for v in [json.loads(raw)] if type(v) is dict and v.get('artifact_type')=='proposal']
    assert len(drafts)==1
    value=drafts[0]
    assert value['proposal_status']=='draft' and value['maturity']=='draft'
    assert not value['reviews'] and value['change_plan']['actor']['actor_type']=='ai'
    assert all(files(root)[p]==raw for p,raw in before.items())
    after=files(root)
    retry=execute_request(request,cwd=root,context_builder=builder).result
    assert retry.exit_code==0 and retry.result['outcome']['replayed'],retry
    assert files(root)==after
