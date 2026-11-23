"""A real isolated approval retains native type gates and human host authority."""
import pytest
from specroad.authoring.native_generic import author_generic
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.paths import artifact_path
from specroad.model.errors import ModelError
from support.native_plan_authoring import setup,values,files,ACTOR,ALLOW
from support.model import put


def goal(root,*,eligible=True):
    setup(root,with_plan=False)
    value=next(v for v in values(root).values() if v['artifact_type']=='goal')
    value['maturity']='in_review'
    if eligible:value['success_criterion']=['A measurable synthetic criterion.']
    else:value.pop('success_criterion',None)
    put(root,artifact_path('goal',value['id'],'SR'),jcs(value))
    return value


def call(root,value,**kwargs):
    return author_generic(root,{'command_id':'lifecycle.transition','target':value['id'],
        'to':'approved','reason':'Explicit synthetic human decision'},actor=ACTOR,request_id='approval',**kwargs)


def test_native_standard_approval_requires_target_fields_and_replays(tmp_path):
    root=tmp_path/'project';original=goal(root)
    result=call(root,original,authority=ALLOW)
    updated=values(root)[original['id']]
    assert updated['maturity']=='approved' and updated['revision']==original['revision']+1
    assert {k:v for k,v in updated.items() if k not in ('maturity','revision','updated_at','updated_by')}=={
        k:v for k,v in original.items() if k not in ('maturity','revision','updated_at','updated_by')}
    assert result['completion']['commit_completed']
    after=files(root);retry=call(root,original,authority=ALLOW)
    assert retry['replayed'] and files(root)==after


def test_incomplete_gate_and_untrusted_actor_label_do_not_approve(tmp_path):
    root=tmp_path/'project';original=goal(root,eligible=False);before=files(root)
    with pytest.raises(ModelError):call(root,original,authority=ALLOW)
    assert values(root)[original['id']]==original
    assert all(files(root)[p]==b for p,b in before.items())
    with pytest.raises(ModelError):call(root,original,authority=None)
