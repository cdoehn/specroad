"""Independent current project bytes and explicit synthetic host authority."""
import json
from specroad.changes import PublicationAuthority
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.paths import artifact_path
from support.plan_sources import small_source, block, token
from support.plan_models import PLAN, ENTRY, plan, entry
from support.model import put
from test_proposal_basis import project

ACTOR = {'actor_type':'human','actor_id':'synthetic-author'}
ALLOW = PublicationAuthority('synthetic-plan-host','1',lambda request: True)


def files(root):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}


def setup(root, *, with_plan=True):
    project(root, bundled=True)
    config = json.loads((root/'specroad.json').read_bytes());config['schema_version']='0.3.0'
    put(root,'specroad.json',jcs(config))
    if with_plan:
        raw, p, e = small_source(description='Prose <!-- keep -->\n\n', entry_body='```python\n# untouched\n```\n')
        put(root,artifact_path('implementation_plan',PLAN,'SR'),raw)
    put(root,'foreign.txt',b'never edit\x00\xff\n')
    return root


def values(root):
    from specroad.authoring.project_sources import AuthoringSources
    return {v['id']:v for v in AuthoringSources(root).model.artifacts}


def call(root, command, **fields):
    from specroad.authoring.native_plan import author_plan
    options = {k:fields.pop(k) for k in ('dry_run','as_proposal','proposal_fields','request_id',
        'expected_model_root','authority','services','actor') if k in fields}
    return author_plan(root, {'command_id':command,**fields}, **{
        'actor':ACTOR,'authority':ALLOW,**options})


def proposal_input():
    return {'title':'Explicit proposal','rationale':'Review required','changes':[{
        'rationale':'Requested edit','requirement_or_issue_ids':[], 'sources':[],
        'assumptions':[],'confidence':0.5}], 'model_provenance':{
        **{k:'unknown' for k in ('provider','model_name','model_version_or_build','prompt_template_version','runner_version')},
        'unknown_reasons':{k:'Synthetic test input; no model run claimed' for k in ('provider','model_name','model_version_or_build','prompt_template_version','runner_version')}}}


def new_plan_fields():
    from support.plan_models import SCOPE
    return {'title':'New plan','display_id':'NEXT','scope':dict(SCOPE),'language':'en'}


def new_entry_fields():
    return {'title':'Build next','display_id':'B','entry_kind':'commit',
            'work_kind':'implementation','language':'en'}


def example(root, command):
    name = command.command_id
    from specroad.authoring.native_intents import SPECIAL_COMMANDS
    if name in SPECIAL_COMMANDS:
        if name in ('evidence.record', 'evidence.import') and root.exists():
            root = root / 'evidence-project'
        from support.native_authoring_cases import specialist_example
        intent=specialist_example(root,name)
        put(root,"intent.json",jcs(intent))
        return {"command_id":name,"options":{"--input":str(root/"intent.json"),"--project":str(root),
            "--actor-type":"human","--actor-id":"synthetic-author","--dry-run":True,"--format":"json"}}
    setup(root)
    request=command.protocol.example.as_dict()
    request['options']['--project']=str(root)
    request['options']['--dry-run']=True
    request['options']['--format']='json'
    if name=='change.apply':
        from specroad.authoring.native_generic import author_generic
        goal=next(v for v in values(root).values() if v['artifact_type']=='goal')
        result=author_generic(root,{'command_id':'artifact.update','target':goal['id'],
            'expected_revision':goal['revision'],'patch':[{'op':'replace','path':'/title','value':'Saved title'}]},
            actor=ACTOR,dry_run=True)
        put(root,'change-plan.json',jcs(result['plan']))
        request['arguments']={'plan_file':str(root/'change-plan.json')}
        request['options']['--actor-id']=ACTOR['actor_id']
        return request
    if name.startswith('plan.'):
        args=request.get('arguments',{})
        if args:
            args['target']=PLAN if name in ('plan.update','plan.remove','plan.entry.add') else ENTRY
        if name in ('plan.create','plan.update','plan.entry.add','plan.entry.update'):
            field = new_plan_fields() if name=='plan.create' else new_entry_fields() if name=='plan.entry.add' else {'title':'Changed'}
            put(root,'fields.json',jcs(field));request['options']['--input']=str(root/'fields.json')
        if name=='plan.remove':request['options']['--subtree']=True
        if name=='plan.entry.move':request['options'].update({'--parent':PLAN,'--target-plan':PLAN,'--position':'0'})
    else:
        from support.domain import domain_value
        from specroad.model.canonical import canonical_json_sha256
        goal=next(v for v in values(root).values() if v['artifact_type']=='goal')
        if name=='artifact.create':
            value=domain_value('goal');generated={'id','id_scheme','artifact_type','schema_version','maturity','revision','created_at','created_by','updated_at','updated_by'}
            put(root,'fields.json',jcs({k:v for k,v in value.items() if k not in generated}))
            request['options']['--input']=str(root/'fields.json')
        elif name in ('artifact.update','lifecycle.transition'):
            request['arguments']['target']=goal['id']
        else:
            request['arguments']['source']=goal['id']
            document=domain_value('goal',id='SR-GOAL-'+token(19))
            put(root,artifact_path('goal',document['id'],'SR'),jcs(document))
            if name=='relation.add':request['options'].update({'--target':document['id'],'--type':'supersedes'})
            else:
                relation={'relation_id':'REL-'+token(5),'id_scheme':'random128-v1','type':'supersedes',
                    'target':document['id'],'external_identities':[],'extensions':{}}
                goal['relations']=[relation]
                put(root,artifact_path('goal',goal['id'],'SR'),jcs(goal))
                request['options'].update({'--relation-id':relation['relation_id'],'--expected-sha256':canonical_json_sha256(relation)})
    return request
