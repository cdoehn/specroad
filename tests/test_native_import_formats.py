"""Public imports bind real original bytes and complete native record sets."""
from hashlib import sha256
import json
import pytest
from specroad.cli.application import execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.model.canonical import canonical_json_bytes as jcs
from support.model import put
from support.native_authoring_cases import specialist_example, store
from support.native_plan_authoring import ACTOR, ALLOW, files, values


def inputs(root, kind):
    intent=specialist_example(root,'evidence.import')
    exchange=json.loads((root/intent['source_path']).read_bytes())
    additions={}
    if kind=='junit':
        raw=b'<testsuite><testcase name="one"><failure/></testcase><testcase name="two"><error/></testcase></testsuite>'
        mapping={'format_version':'junit-mapping-v1','identity_fields':['name'],
            'bindings':[{'identity':{'name':n},'target_id':exchange['results'][i]['target_id']}
                        for i,n in enumerate(('one','two'))]}
        additions['attachments/measurement.json']=jcs(exchange)
        intent.update(measurements_path='attachments/measurement.json',
            measurements_sha256=sha256(additions['attachments/measurement.json']).hexdigest(),tool=exchange['tool'])
        path='attachments/original.xml';media='application/xml'
    else:
        raw=jcs({'version':'2.1.0','runs':[{'tool':{'driver':{'name':'explicit-analyzer'}},
            'results':[{'kind':'fail','message':{'text':'first'}},{'kind':'fail','message':{'text':'second'}}]}]})
        mapping={'format_version':'sarif-mapping-v1','source_sha256':sha256(raw).hexdigest(),
            'exchange':exchange,'bindings':[{'exchange_result_index':i,'run_index':0,'result_index':i,
                'rule_index':None,'invocation_index':None,'artifact_indices':[]} for i in range(2)]}
        path='attachments/original.sarif';media='application/json'
    additions[path]=raw;additions['attachments/mapping.json']=jcs(mapping)
    intent.update(import_format=kind,source_path=path,source_sha256=sha256(raw).hexdigest(),
        mapping_path='attachments/mapping.json',mapping_sha256=sha256(additions['attachments/mapping.json']).hexdigest())
    original=next(v for v in values(root).values() if v['artifact_type']=='evidence')
    for p,b in additions.items():
        put(root,p,b)
        original.setdefault('attachments',[]).append({'path':p,'media_type':media if p==path else 'application/json',
            'size':len(b),'sha256':sha256(b).hexdigest()})
    store(root,original)
    return intent,additions


@pytest.mark.parametrize('kind',['junit','sarif'])
def test_import_formats_publish_exact_failed_measurements_and_originals(tmp_path,kind):
    root=tmp_path/'p';intent,originals=inputs(root,kind)
    put(root,'intent.json',jcs(intent));before=files(root);prior=values(root)
    request={'command_id':'evidence.import','arguments':{'import_format':kind,'source_path':intent['source_path']},
        'options':{'--input':'intent.json','--actor-type':'human','--actor-id':ACTOR['actor_id'],
            '--request-id':'import-originals','--dry-run':True}}
    builder=InvocationContextBuilder(publication_authority=ALLOW)
    preview=execute_request(request,cwd=root,context_builder=builder).result
    assert preview.exit_code==0 and files(root)==before,preview
    ops=preview.result['outcome']['plan']['operations']
    assert len(ops)==2 and all(o['evidence']['result']=='failed' for o in ops)
    del request['options']['--dry-run']
    actual=execute_request(request,cwd=root,context_builder=builder).result
    assert actual.exit_code==0,actual
    current=values(root)
    assert all(current[i]==v for i,v in prior.items())
    assert all(files(root)[p]==raw for p,raw in before.items())
    evidence=[v for i,v in current.items() if i not in prior and v['artifact_type']=='evidence']
    assert len(evidence)==2
    for value in evidence:
        assert value['result']=='failed' and value['origin']=='imported_'+kind
        assert {p:files(root)[p] for p in originals}==originals
        attached={a['path']:a['sha256'] for a in value['attachments']}
        assert all(attached[p]==sha256(b).hexdigest() for p,b in originals.items())
    after=files(root)
    replay=execute_request(request,cwd=root,context_builder=builder).result
    assert replay.exit_code==0 and replay.result['outcome']['replayed'] and files(root)==after,replay


@pytest.mark.parametrize('kind',['junit','sarif'])
@pytest.mark.parametrize('field',['mapping_sha256','source_sha256','run_context'])
def test_import_original_or_context_mismatch_never_publishes(tmp_path,kind,field):
    root=tmp_path/'p';intent,_=inputs(root,kind)
    intent[field]={} if field=='run_context' else '0'*64
    put(root,'intent.json',jcs(intent));before=files(root)
    request={'command_id':'evidence.import','options':{'--input':'intent.json','--actor-type':'human',
        '--actor-id':ACTOR['actor_id'],'--request-id':'invalid-import'}}
    result=execute_request(request,cwd=root,context_builder=InvocationContextBuilder(publication_authority=ALLOW)).result
    assert result.exit_code!=0 and files(root)==before,result
