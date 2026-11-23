"""Public raw specialists publish real files and replay original intentions."""
import json
import pytest
from specroad.authoring.native_specialists import COMMANDS
from specroad.cli.application import execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.model.paths import artifact_path
from specroad.model.canonical import canonical_json_bytes as jcs
from support.native_authoring_cases import specialist_example
from support.native_plan_authoring import ACTOR, ALLOW, files, values
from support.model import put


@pytest.mark.parametrize('name',COMMANDS)
def test_raw_specialist_publishes_declared_semantics_and_exact_retry(tmp_path,name):
    root=tmp_path/'project';intent=specialist_example(root,name)
    put(root,'input.json',jcs(intent));put(root,'foreign.raw',b'not normative\0\xff')
    before=files(root);original=values(root)
    request={'command_id':name,'options':{'--input':'input.json','--actor-type':'human',
        '--actor-id':ACTOR['actor_id'],'--request-id':'raw-specialist'}}
    builder=InvocationContextBuilder(publication_authority=ALLOW)
    result=execute_request(request,cwd=root,context_builder=builder).result
    assert result.exit_code==0,result
    outcome=result.result['outcome'];current=values(root)
    assert outcome['completion']['commit_completed'] and outcome['completion']['cleanup_completed']
    assert not outcome['approval_granted']
    created={i:v for i,v in current.items() if i not in original}
    if name in ('view.create','document.create','section.add','block.add'):
        kind={'view.create':'view','document.create':'document','section.add':'section','block.add':'content_block'}[name]
        assert len(created)==1
        value=next(iter(created.values()));assert value['artifact_type']==kind
        assert all(value[k]==v for k,v in intent['fields'].items())
        assert value['revision']==1 and value['maturity']=='draft'
        if name not in ('document.create','view.create'):
            assert any(e['type']=='contains' and e['target']==value['id'] and e['position']==intent['position']
                       for e in current[intent['parent_id']]['relations'])
    elif name=='section.move':
        edges=[e for v in current.values() for e in v['relations'] if e['type']=='contains' and e['target']==intent['target']]
        assert len(edges)==1 and edges[0]['position']==9 and not created
        assert current[intent['target']]==original[intent['target']]
    elif name in ('section.remove','block.remove'):
        assert current[intent['target']]['maturity']=='retired' and not created
        assert current[intent['target']]['revision']==original[intent['target']]['revision']+1
    elif name=='block.update':
        assert current[intent['target']]['title']=='New explicit block title' and not created
    elif name=='relation.review':
        value=next(iter(created.values()));assert len(created)==1
        assert value['decision']=='confirmed' and value['reviewer']==ACTOR
        assert value['source_id']==intent['source'] and value['relation_id']==intent['relation_id']
        assert value['review_state']=='recorded' and value['maturity']=='approved'
    elif name=='baseline.create':
        value=next(iter(created.values()));assert len(created)==1
        assert value['title']==intent['name'] and value['baseline_state']=='sealed'
        assert all((root/row['object_path']).is_file() for row in value['manifest'])
    elif name=='evidence.record':
        assert created=={intent['record']['id']:intent['record']}
    else:
        assert len(created)==2
        assert {v['produced_at'] for v in created.values()}=={'2026-10-19T21:00:00Z','2026-10-19T21:01:00Z'}
        assert all(v['origin']=='imported_generic' and v['result']=='failed' for v in created.values())
        assert all(any(a['sha256']==intent['source_sha256'] for a in v['attachments']) for v in created.values())
    for identity,value in created.items():
        assert (root/artifact_path(value['artifact_type'],identity,'SR')).read_bytes()==jcs(value)
    assert files(root)['foreign.raw']==before['foreign.raw']
    after=files(root)
    retry=execute_request(request,cwd=root,context_builder=builder).result
    assert retry.exit_code==0 and retry.result['outcome']['replayed'],retry
    assert files(root)==after
    intent['unexpected']=True;put(root,'input.json',jcs(intent));unchanged=files(root)
    refused=execute_request(request,cwd=root,context_builder=builder).result
    assert refused.exit_code!=0 and files(root)==unchanged


@pytest.mark.parametrize('name',['relation.review','baseline.create'])
def test_documented_positional_syntax_and_conflicting_envelope(tmp_path,name):
    root=tmp_path/'p';intent=specialist_example(root,name)
    options={'--actor-type':'human','--actor-id':ACTOR['actor_id'],'--dry-run':True}
    if name=='relation.review':
        arguments={'source':intent['source']}
        options.update({'--'+k.replace('_','-'):str(v) for k,v in intent.items() if k!='source'})
    else:arguments={'name':intent['name']}
    request={'command_id':name,'arguments':arguments,'options':options}
    before=files(root)
    result=execute_request(request,cwd=root).result
    assert result.exit_code==0 and files(root)==before,result
    key='source' if name=='relation.review' else 'name'
    put(root,'input.json',jcs({**intent,key:'conflicting'}));options['--input']='input.json';before=files(root)
    result=execute_request(request,cwd=root).result
    assert result.exit_code==2 and files(root)==before
