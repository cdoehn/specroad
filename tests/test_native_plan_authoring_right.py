"""Independent cross-carrier, history, conflict and actual crash boundaries."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.paths import artifact_path
from specroad.model.errors import ModelError
from specroad.changes.normal_access import require_normal_access
from support.model import put
from support.plan_sources import block, token
from support.plan_models import plan, entry
from support.native_plan_authoring import setup,files,values,call,ACTOR,ALLOW,PLAN,ENTRY,proposal_input

B='SR-IPLAN-'+token(10); C='SR-IPLAN-'+token(20)
EB='SR-PENTRY-'+token(11); EC='SR-PENTRY-'+token(21)


def carriers(root):
    setup(root)
    for identity, child, label, relation in ((B,EB,'B',12),(C,EC,'C',22)):
        p=plan();p.update(id=identity,children=[child],display_id=label)
        e=entry();e.update(id=child,plan_id=identity,parent_id=identity,
            parent_relation_id='REL-'+token(relation),display_id='one')
        raw=block('# ['+label+'] Independent plan',p,'Body of '+label+'.\n\n')
        raw+=block('## [ ] [one] Independent entry',e,'Keep this body.\n')
        put(root,artifact_path('implementation_plan',identity,'SR'),raw)
    return root


def reference(plan_id,entry_id,number):
    return {'relation_id':'REL-'+token(number),'plan_id':plan_id,'entry_id':entry_id}


def test_cross_plan_move_updates_all_owners_and_qualified_references_atomically(tmp_path):
    root=carriers(tmp_path/'p')
    call(root,'plan.entry.update',target=EC,fields={'prerequisites':[reference(PLAN,ENTRY,31)]},request_id='dependency')
    before=files(root);old=values(root)
    result=call(root,'plan.entry.move',target=ENTRY,target_plan_id=B,parent_id=B,position=1,request_id='cross-move')
    after=values(root)
    assert after[PLAN]['children']==[] and after[B]['children']==[EB,ENTRY]
    assert after[ENTRY]['parent_id']==B and after[ENTRY]['plan_id']==B
    assert after[ENTRY]['parent_relation_id']==old[ENTRY]['parent_relation_id']
    assert after[EC]['prerequisites']==[reference(B,ENTRY,31)]
    assert after[ENTRY]['description']==old[ENTRY]['description']
    assert after[EC]['revision']==old[EC]['revision']+1
    sources=result['audit']['operations'][0]['sources']
    assert len(sources)==3 and all(s['before']!=s['after'] for s in sources)
    assert files(root)['foreign.txt']==before['foreign.txt']
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    saved=files(root);retry=call(root,'plan.entry.move',target=ENTRY,target_plan_id=B,parent_id=B,position=1,request_id='cross-move')
    assert retry['replayed'] and files(root)==saved


def test_complete_removal_impact_and_explicit_child_retention(tmp_path):
    root=carriers(tmp_path/'p')
    call(root,'plan.entry.update',target=EC,fields={'prerequisites':[reference(PLAN,ENTRY,31)]})
    before=files(root)
    with pytest.raises(ModelError) as caught:call(root,'plan.remove',target=PLAN,subtree=True)
    assert caught.value.reason=='plan_remove_open_impact' and caught.value.impact
    assert all(files(root)[p]==b for p,b in before.items())
    call(root,'plan.entry.update',target=EC,fields={'prerequisites':[]})
    with pytest.raises(ModelError):call(root,'plan.remove',target=PLAN,subtree=False)
    call(root,'plan.entry.remove',target=ENTRY)
    assert PLAN in values(root) and values(root)[PLAN]['children']==[] and ENTRY not in values(root)


def test_plan_inheritance_and_parent_cycles_do_not_publish(tmp_path):
    root=carriers(tmp_path/'p')
    call(root,'plan.update',target=B,fields={'prerequisites':[reference(PLAN,ENTRY,31)]})
    before=files(root)
    with pytest.raises(ModelError):call(root,'plan.entry.check',target=EB)
    assert all(files(root)[p]==b for p,b in before.items())
    call(root,'plan.entry.check',target='A',plan_id=PLAN)
    call(root,'plan.entry.check',target=EB)
    assert values(root)[ENTRY]['implemented'] and values(root)[EB]['implemented']
    before=files(root)
    with pytest.raises(ModelError):
        call(root,'plan.update',target=PLAN,fields={'prerequisites':[reference(B,EB,32)]})
    assert all(files(root)[p]==b for p,b in before.items())


@pytest.mark.parametrize('proposal',[False,True])
def test_retry_checks_original_explicit_root_before_new_allocations(tmp_path,proposal):
    root=setup(tmp_path/'p')
    options={'target':ENTRY,'fields':{'title':'Bound retry'},'request_id':'bound-root'}
    if proposal:options.update(as_proposal=True,proposal_fields=proposal_input())
    result=call(root,'plan.entry.update',**options)
    before=files(root)
    with pytest.raises(ModelError) as caught:
        call(root,'plan.entry.update',**options,expected_model_root='f'*64)
    assert caught.value.reason=='request_base_root_conflict' and files(root)==before
    retry=call(root,'plan.entry.update',**options,expected_model_root=result['audit']['base_model_root_sha256'])
    assert retry['replayed'] and files(root)==before


def test_native_authority_cannot_publish_after_a_concurrent_carrier_edit(tmp_path):
    from specroad.changes import PublicationAuthority
    root=setup(tmp_path/'p');path=root/artifact_path('implementation_plan',PLAN,'SR')
    original=path.read_bytes();modified=False
    def concurrent(request):
        nonlocal modified
        if not modified:
            path.write_bytes(original.replace(b'Build feature',b'Concurrent author'));modified=True
        return True
    authority=PublicationAuthority('synthetic-concurrent-host','1',concurrent)
    with pytest.raises(ModelError):
        call(root,'plan.entry.update',target=ENTRY,fields={'title':'Must not overwrite'},authority=authority)
    assert modified and b'Concurrent author' in path.read_bytes() and b'Must not overwrite' not in path.read_bytes()


CRASHES=('marker_synced','staged:0','effect_replaced:0','effect_synced:0',
         'receipt:transaction.json','receipts_synced','before_marker_unlink','marker_unlinked')


def _crash(root,event):
    import os
    from specroad.changes import guarded_write
    def stop(boundary):
        if boundary==event:os._exit(71)
    guarded_write._checkpoint=stop
    call(Path(root),'plan.entry.update',target=ENTRY,fields={'title':'Crash target'},request_id='crash')
    raise AssertionError('Native publication boundary not reached')


@pytest.mark.parametrize('event',CRASHES)
def test_actual_process_loss_keeps_native_barrier_and_foreign_bytes(tmp_path,event):
    from support.processes import run_python
    root=setup(tmp_path/'p');before=files(root);tree=Path(__file__).resolve().parents[1]
    body='import sys;sys.path[:0]='+repr([str(tree/n) for n in ('src','tests','tools')])+'\n'
    body+='from test_native_plan_authoring_right import _crash\n_crash(*'+repr((str(root),event))+')\n'
    result=run_python(['-I','-B','-c',body],root)
    assert result.returncode==71,result
    path=artifact_path('implementation_plan',PLAN,'SR')
    raw=(root/path).read_bytes()
    if event in ('marker_synced','staged:0'):assert raw==before[path]
    else:assert b'Crash target' in raw
    assert files(root)['foreign.txt']==before['foreign.txt']
    with pytest.raises(ModelError):require_normal_access(root)
    frozen=files(root)
    with pytest.raises(ModelError):call(root,'plan.entry.update',target=ENTRY,fields={'title':'No blind retry'},request_id='other')
    assert files(root)==frozen
