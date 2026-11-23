"""Real CLI request pipeline and native writer; no terminal/layout assertions."""
import json
import pytest
from specroad.cli.application import execute, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.requests import CommandRequest
from specroad.model.canonical import canonical_json_bytes as jcs
from support.native_plan_authoring import setup, files, values, ALLOW, ACTOR, example
from specroad.authoring.native_intents import COMMANDS
from specroad.model.plan_command_ids import COMMANDS as PLAN_COMMANDS


@pytest.mark.parametrize('name',(*COMMANDS,*PLAN_COMMANDS))
def test_registered_raw_command_and_structured_dry_run_share_real_pipeline(tmp_path,name):
    command=builtin_registry().resolve(name)
    if name == 'artifact.create':
        from specroad.model.authoring_command_ids import CREATE_FIELDS, CREATE_KINDS
        from specroad.authoring._input_fields import _schema
        from test_authoring_inputs import DOMAIN, RECORD
        assert set(CREATE_KINDS) == set(DOMAIN) | set(RECORD)
        assert set(CREATE_FIELDS) == {field for kind in (*DOMAIN, *RECORD) for field in _schema(kind)['properties']}
    request=example(tmp_path/'project',command);root=tmp_path/'project';before=files(root)
    structured=execute_request(request,cwd=root).result
    assert structured.exit_code==0, structured
    assert files(root)==before
    argv=list(command.words)+list(request.get('arguments',{}).values())
    for flag,value in request['options'].items():
        for item in value if isinstance(value,list) else [value]:
            argv += [flag] if item is True else [flag,item]
    raw=execute(argv,cwd=root).result
    assert raw.exit_code==0, raw
    assert raw.result['command_id']==name and files(root)==before
    assert raw.result['outcome']['audit']['write_state']=='not_committed'


def run(root,args,*,authority=ALLOW):
    return execute([*args,'--actor-type','human','--actor-id','synthetic-author','--format','json'],cwd=root,
                   context_builder=InvocationContextBuilder(publication_authority=authority)).result


def test_raw_create_update_lifecycle_and_relation_effects_with_retry(tmp_path):
    root=setup(tmp_path/'project',with_plan=False)
    from support.domain import domain_value
    original=domain_value('goal');generated={'schema_version','id','id_scheme','artifact_type','revision','maturity','created_at','created_by','updated_at','updated_by'}
    (root/'create.json').write_bytes(jcs({k:v for k,v in original.items() if k not in generated}))
    result=run(root,['artifact','create','goal','--input','create.json','--request-id','create'])
    assert result.exit_code==0,result
    identity=result.result['outcome']['audit']['created_ids'][0]
    update=['artifact','update',identity,'--set','/extensions/temporary=1','--unset','/extensions/temporary',
            '--set','/title="Changed"','--expected-revision','1','--request-id','update']
    result=run(root,update);assert result.exit_code==0,result
    assert values(root)[identity]['title']=='Changed' and values(root)[identity]['extensions']=={}
    before=files(root);retry=run(root,update)
    assert retry.exit_code==0 and retry.result['outcome']['replayed'] and files(root)==before
    result=run(root,['lifecycle','transition',identity,'--to','proposed','--reason','Explicit','--request-id','transition'])
    assert result.exit_code==0,result
    assert values(root)[identity]['maturity']=='proposed'
    target=next(v['id'] for v in values(root).values() if v['artifact_type']=='goal' and v['id']!=identity)
    result=run(root,['relation','add',identity,'--type','supersedes','--target',target,'--request-id','relation'])
    assert result.exit_code==0,result
    relation=values(root)[identity]['relations'][0]
    from specroad.model.canonical import canonical_json_sha256
    result=run(root,['relation','remove',identity,'--relation-id',relation['relation_id'],
        '--expected-sha256',canonical_json_sha256(relation),'--reason','Explicit removal'])
    assert result.exit_code==0,result
    assert values(root)[identity]['relations']==[]
    assert files(root)['foreign.txt']==b'never edit\x00\xff\n'


def test_registered_cli_never_treats_actor_label_as_authority(tmp_path):
    root=setup(tmp_path/'project');before=files(root)
    identity=next(v['id'] for v in values(root).values() if v['artifact_type']=='goal')
    result=run(root,['artifact','update',identity,'--set','/title="Denied"','--expected-revision','1'],authority=None)
    assert result.exit_code==7 and files(root)==before


def test_raw_option_order_is_preserved_through_registry_execute(tmp_path):
    root=setup(tmp_path/'project');registry=builtin_registry()
    identity=next(v['id'] for v in values(root).values() if v['artifact_type']=='goal')
    before=files(root)
    # SR-REQ-0018: surviving extension keys require a namespace.
    argv=['artifact','update',identity,'--set','/extensions/test.a=1','--unset','/extensions/test.a',
          '--set','/extensions/test.b=2','--expected-revision','1','--dry-run','--actor-type','human','--actor-id','synthetic']
    result=registry.execute_result(registry.parse(argv),cwd=root)
    assert result.exit_code==0,result.as_dict()
    assert [op['path'] for op in result.result['outcome']['plan']['operations'][0]['patch']]==['/extensions/test.a','/extensions/test.a','/extensions/test.b']
    assert files(root)==before
