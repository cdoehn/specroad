"""Exactly saved dry-run plans publish through the same durable native writer."""
from copy import deepcopy
import pytest
from specroad.authoring.native_generic import author_generic
from specroad.authoring.native_saved import apply_saved
from specroad.changes import ChangePlan
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.cli.application import execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from support.native_plan_authoring import setup,files,values,call,ACTOR,ALLOW,PLAN,ENTRY
from support.model import put


@pytest.mark.parametrize('kind', ['json','markdown'])
def test_exact_saved_preview_is_native_write_and_replay_without_reallocation(tmp_path,kind):
    root=setup(tmp_path/'p');before=files(root)
    if kind=='markdown':
        preview=call(root,'plan.entry.update',target=ENTRY,fields={'title':'Saved title'},dry_run=True,request_id='saved-native')
    else:
        goal=next(v for v in values(root).values() if v['artifact_type']=='goal')
        preview=author_generic(root,{'command_id':'artifact.update','target':goal['id'],
            'expected_revision':goal['revision'],'patch':[{'op':'replace','path':'/title','value':'Saved title'}]},
            actor=ACTOR,dry_run=True,request_id='saved-native')
    assert files(root)==before
    raw=jcs(preview['plan']);put(root,'saved.json',raw)
    req={'command_id':'change.apply','arguments':{'plan_file':'saved.json'},'options':{
        '--actor-type':'human','--actor-id':ACTOR['actor_id'],'--request-id':'saved-native'}}
    builder=InvocationContextBuilder(publication_authority=ALLOW)
    result=execute_request(req,cwd=root,context_builder=builder).result
    assert result.exit_code==0,result
    out=result.result['outcome'];assert out['plan_sha256']==ChangePlan(raw).sha256
    assert out['completion']['commit_completed'] and out['completion']['cleanup_completed']
    assert any(v['title']=='Saved title' for v in values(root).values())
    after=files(root)
    retry=execute_request(req,cwd=root,context_builder=builder).result
    assert retry.exit_code==0 and retry.result['outcome']['replayed'] and files(root)==after


def test_saved_plan_cannot_relabel_actor_or_request_or_bypass_authority(tmp_path):
    root=setup(tmp_path/'p')
    preview=call(root,'plan.entry.update',target=ENTRY,fields={'title':'Saved'},dry_run=True,request_id='original')
    before=files(root);intent={'command_id':'change.apply','plan_bytes':jcs(preview['plan'])}
    for actor,request,authority in [(ACTOR,'different',ALLOW),({'actor_type':'human','actor_id':'other'},'original',ALLOW),(ACTOR,'original',None)]:
        with pytest.raises(ModelError) as caught:
            apply_saved(root,intent,actor=actor,request_id=request,authority=authority)
        assert caught.value.authoring_attempt['write_state']=='not_committed'
        assert files(root)==before
