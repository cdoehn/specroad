"""Native plan writes: independently authored files, actual gates and receipts."""
import json
import pytest
from specroad.model.canonical import canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.changes.receipt_values import transaction_receipt_path
from specroad.changes.write_guard_values import validate_transaction
from specroad.model.errors import ModelError
from support.native_plan_authoring import (setup, files, values, call, ACTOR, ALLOW,
    PLAN, ENTRY, new_plan_fields, new_entry_fields, proposal_input)


def test_create_and_entry_add_publish_real_md_and_native_receipt(tmp_path):
    root=setup(tmp_path/'project',with_plan=False);before=files(root)
    created=call(root,'plan.create',fields=new_plan_fields(),request_id='create-plan')
    plan_id=created['audit']['created_ids'][0]
    path=artifact_path('implementation_plan',plan_id,'SR')
    assert path.endswith('.md') and files(root)[path].startswith(b'# [NEXT] New plan\n')
    assert not any(p.startswith('spec/plan-entries/') for p in files(root))
    added=call(root,'plan.entry.add',target=plan_id,fields=new_entry_fields(),request_id='entry-add')
    current=values(root);entry_id=next(i for i in added['audit']['created_ids'] if '-PENTRY-' in i)
    assert current[plan_id]['children']==[entry_id] and current[plan_id]['revision']==2
    assert current[entry_id]['revision']==1 and current[entry_id]['implemented'] is False
    assert current[entry_id]['plan_id']==plan_id and current[entry_id]['parent_id']==plan_id
    assert added['commit_messages']==[{'entry_id':entry_id,'message':'B Build next'}]
    assert all(files(root)[p]==raw for p,raw in before.items())
    tx=added['completion']['transaction_id']
    receipt=validate_transaction((root/transaction_receipt_path(tx)).read_bytes())
    assert receipt['operations'][0]['op']=='plan_edit'
    assert receipt['files']==[{'path':path,
        'before':{'size':len(created['audit']['operations'][0]['sources'][0]['after'].encode()),
                  'sha256':__import__('hashlib').sha256(created['audit']['operations'][0]['sources'][0]['after'].encode()).hexdigest()},
        'after':{'size':len(files(root)[path]),'sha256':__import__('hashlib').sha256(files(root)[path]).hexdigest()}}]


def test_update_only_own_projection_and_preserves_all_other_bytes(tmp_path):
    root=setup(tmp_path/'project');before=files(root);old=values(root)
    result=call(root,'plan.entry.update',target=ENTRY,fields={'title':'Explicit new title'},request_id='update-entry')
    current=values(root);path=artifact_path('implementation_plan',PLAN,'SR');raw=files(root)[path]
    assert current[PLAN]==old[PLAN] and current[ENTRY]['revision']==old[ENTRY]['revision']+1
    assert current[ENTRY]['title']=='Explicit new title'
    assert b'Prose <!-- keep -->\n\n' in raw and b'```python\n# untouched\n```\n' in raw
    op=result['audit']['operations'][0]
    assert op['sources']==[{'path':path,'before':before[path].decode(),'after':raw.decode()}]
    assert op['result_ids']==[ENTRY]
    assert all(files(root)[p]==content for p,content in before.items() if p!=path)
    assert 'Explicit new title' in result['commit_messages'][0]['message']


@pytest.mark.parametrize('command,fields',[
    ('plan.create',{'fields':new_plan_fields()}),
    ('plan.update',{'target':PLAN,'fields':{'title':'Changed'}}),
    ('plan.remove',{'target':PLAN,'subtree':True}),
    ('plan.entry.add',{'target':PLAN,'fields':new_entry_fields()}),
    ('plan.entry.update',{'target':ENTRY,'fields':{'title':'Changed'}}),
    ('plan.entry.move',{'target':ENTRY,'target_plan_id':PLAN,'parent_id':PLAN,'position':0}),
    ('plan.entry.remove',{'target':ENTRY}),
    ('plan.entry.check',{'target':ENTRY}),('plan.entry.uncheck',{'target':ENTRY})])
def test_every_dry_run_returns_bound_plan_and_has_no_writes(tmp_path,command,fields):
    root=setup(tmp_path/'project');before=files(root)
    result=call(root,command,**fields,dry_run=True,authority=None)
    assert result['audit']['dry_run'] and result['audit']['write_state']=='not_committed'
    assert result['plan']['operations'][0]['op']=='plan_edit'
    assert result['plan']['base']['model_root_sha256']==result['audit']['base_model_root_sha256']
    assert files(root)==before


def test_noop_and_check_uncheck_keep_parent_checkbox_separate(tmp_path):
    root=setup(tmp_path/'project');before=files(root);original=values(root)
    result=call(root,'plan.entry.uncheck',target=ENTRY,request_id='noop')
    assert result['no_change'] and result['completion'] is None and files(root)==before
    call(root,'plan.entry.check',target=ENTRY,request_id='check')
    now=values(root)
    assert now[ENTRY]['implemented'] and now[PLAN]==original[PLAN]
    call(root,'plan.entry.uncheck',target=ENTRY,request_id='uncheck')
    assert not values(root)[ENTRY]['implemented'] and values(root)[ENTRY]['revision']==3


def test_removal_is_explicit_and_reserves_historical_identity(tmp_path):
    root=setup(tmp_path/'project');before=files(root)
    with pytest.raises(ModelError):call(root,'plan.remove',target=PLAN)
    assert files(root)==before
    result=call(root,'plan.remove',target=PLAN,subtree=True,request_id='remove-plan')
    path=artifact_path('implementation_plan',PLAN,'SR')
    assert not (root/path).exists() and result['write_state']=='committed'
    assert all(files(root)[p]==raw for p,raw in before.items() if p!=path)
    from specroad.authoring.project_sources import AuthoringSources
    sources=AuthoringSources(root)
    assert {PLAN,ENTRY} <= sources.identities.reserved_ids | sources.identities.archived_ids
    assert original_parent_relation() in sources.relations.reserved_ids | sources.relations.archived_ids


def original_parent_relation():return 'REL-'+'0'*25+'2'


def test_exact_retry_and_different_intent_conflict(tmp_path):
    root=setup(tmp_path/'project')
    first=call(root,'plan.entry.update',target=ENTRY,fields={'title':'Saved'},request_id='same')
    before=files(root)
    retry=call(root,'plan.entry.update',target=ENTRY,fields={'title':'Saved'},request_id='same')
    assert retry['replayed'] and retry['plan_sha256']==first['plan_sha256']
    assert files(root)==before
    with pytest.raises(ModelError):call(root,'plan.entry.update',target=ENTRY,fields={'title':'Different'},request_id='same')
    assert files(root)==before


def test_ai_redirect_publishes_only_proposal_and_replays_original_ids(tmp_path):
    root=setup(tmp_path/'project');before=files(root)
    kwargs=dict(target=ENTRY,fields={'title':'Proposed'},request_id='ai-proposal',as_proposal=True,
        proposal_fields=proposal_input(),actor={'actor_type':'ai','actor_id':'synthetic-ai'})
    result=call(root,'plan.entry.update',**kwargs)
    assert result['publication_kind']=='proposal_draft'
    assert result['proposal']['maturity']=='draft' and result['proposal']['reviews']==[]
    assert all(files(root)[p]==raw for p,raw in before.items())
    after=files(root);retry=call(root,'plan.entry.update',**kwargs)
    assert retry['replayed'] and retry['proposal']==result['proposal'] and files(root)==after


@pytest.mark.parametrize('variant',['missing-authority','denied-authority','ai-direct','wrong-base','controlled-field','hidden-option'])
def test_fail_closed_before_product_publication(tmp_path,variant):
    root=setup(tmp_path/'project');before=files(root)
    kwargs=dict(target=ENTRY,fields={'title':'Changed'})
    if variant=='missing-authority':kwargs['authority']=None
    if variant=='denied-authority':
        from specroad.changes import PublicationAuthority
        kwargs['authority']=PublicationAuthority('synthetic-denied','1',lambda request:False)
    if variant=='ai-direct':kwargs.update(actor={'actor_type':'ai','actor_id':'synthetic-ai'},request_id='ai-direct')
    if variant=='wrong-base':kwargs['expected_model_root']='0'*64
    if variant=='controlled-field':kwargs['fields']={'id':ENTRY}
    if variant=='hidden-option':kwargs['position']=0
    with pytest.raises(ModelError):call(root,'plan.entry.update',**kwargs)
    assert all(files(root).get(p)==raw for p,raw in before.items())
    assert values(root)[ENTRY]['title']=='Build feature'
