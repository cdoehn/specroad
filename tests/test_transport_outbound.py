"""15.n.W: native public export, closed byte bindings and unchanged host input."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from build_core import build_core

from specroad.bundles import prepare_project_bundle
from specroad.cli.application import dispatch_result
from specroad.cli.commands import builtin_registry
from specroad.cli.requests import CommandRequest
from specroad.cli.result_schemas import validate_result_document
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes
from support.transport_outbound import ROOT, child, register, request, run_request, tree
from support.read_only import no_write_attempts
from test_project_bundle import project


@pytest.fixture(scope='module')
def distribution(tmp_path_factory):
    module, pyz = build_core(ROOT/'src',tmp_path_factory.mktemp('outbound-distribution')/'build')
    return module,pyz


@pytest.mark.parametrize('route', ('source','module','pyz'))
@pytest.mark.parametrize('subproject', (False,True))
def test_native_outbound_binds_exact_project_runtime_and_reference(tmp_path,distribution,route,subproject):
    repository=tmp_path/'repo'; repository.mkdir()
    root=repository/'project' if subproject else repository
    project(root)
    native=prepare_project_bundle(root)
    registered=register(tmp_path,repository)
    value=request(tmp_path,root,distribution[1]); before=tree(repository)
    source={'source':ROOT/'src','module':distribution[0],'pyz':distribution[1]}[route]
    result=run_request(tmp_path,value,source=source)
    assert result['code']==0,result
    assert tree(repository)==before
    path=tmp_path/'output/handoff.zip'; raw=path.read_bytes()
    result=result['outcome']['result']
    with ZipFile(BytesIO(raw)) as z:
        assert z.namelist()==['handoff.json','project/project.zip','reference/result.zip','runtime/specroad.pyz']
        manifest=json.loads(z.read('handoff.json'))
        assert z.read('handoff.json')==canonical_json_bytes(manifest)
        assert z.read('project/project.zip')==native.source_bytes
        assert z.read('runtime/specroad.pyz')==distribution[1].read_bytes()
        for item in manifest['entries']:
            member=z.read(item['path'])
            assert set(item)=={'path','size','sha256'}
            assert len(member)==item['size'] and sha256(member).hexdigest()==item['sha256']
        assert manifest['project_path']==('project' if subproject else '.')
        assert manifest['project_id']==native.manifest['project_id']
        assert manifest['model_root_sha256']==native.manifest['bundle_model_root_sha256']
        assert manifest['scope_descriptor']==native.manifest['scope_descriptor']
        assert manifest['reference']['repo_id']==registered['repo_id']
        assert manifest['reference']['base_commit']==registered['base_commit']
        frozen={k:v for k,v in manifest.items() if k!='package_id'}
        assert manifest['package_id']==sha256(b'specroad-ai-handoff-v1\0'+canonical_json_bytes(frozen)).hexdigest()
        assert manifest['runtimes']['patchharbor']['tool_version']=='1.8.0'
        assert manifest['runtimes']['patchharbor']['artifact_sha256']=='050cc2d1dc3ecbb1478f6a40c9a5123d1d34d350215d5cc0303025ea08dc4f1e'
        assert z.read('reference/result.zip')==Path(result['transport']['reference_published']).read_bytes()
        with ZipFile(BytesIO(z.read('reference/result.zip'))) as reference:
            member=manifest['runtimes']['patchharbor']['member_path']
            assert member=='runtime/patchharbor-1.8.0.pyz'
            assert sha256(reference.read(member)).hexdigest()==manifest['runtimes']['patchharbor']['artifact_sha256']
    assert result['file']['sha256']==sha256(raw).hexdigest()
    assert result['approval_granted'] is result['write_authorized'] is False
    assert result['transport']['maintenance_enabled'] is False
    assert len(result['transport']['lock_paths'])==2


def test_public_variant_and_metadata_do_not_export(tmp_path):
    registry=builtin_registry()
    described=dispatch_result(['command','describe','bundle.create'])
    assert described.exit_code==0,described.as_dict()
    variant=described.as_dict()['result']['variants'][0]
    assert variant['command_class']=='transport_operational'
    invocation=registry.bind_request(CommandRequest.from_mapping(variant['example']))
    assert invocation.command.command_class.value=='transport_operational'
    assert registry.resolve('bundle.create').command_class.value=='generated_output'
    assert variant['budget_policy_version'] == 'runtime-budget-v2'
    assert variant['result_schema'] == invocation.command.protocol.result_schema
    assert variant['required_write_paths'] == list(invocation.command.requires_write_paths)
    document = described.as_dict()['result']
    with no_write_attempts():
        validate_result_document('command-description-v1', document)
        for field, value in (('result_schema', ''), ('required_write_paths', False),
                ('budget_policy_version', 3), ('undeclared_authority', True)):
            invalid = deepcopy(document)
            invalid['variants'][0][field] = value
            with pytest.raises(ModelError):
                validate_result_document('command-description-v1', invalid)
        assert dispatch_result(['environment','check','--for-command','bundle.create']).exit_code==0


@pytest.mark.parametrize('change', ('missing_hash','bad_hash','python_bundled','return','scope','exclude','relative'))
def test_invalid_requests_precede_all_transport_effects(tmp_path,distribution,change):
    root=tmp_path/'project';project(root)
    value=request(tmp_path,root,distribution[1]);options=value['options']
    if change=='missing_hash':del options['--patchharbor-pyz-sha256']
    if change=='bad_hash':options['--specroad-pyz-sha256']='short'
    if change=='python_bundled':options['--runtime-profile']='python-bundled'
    if change=='return':options['--direction']='return'
    if change=='scope':options['--scope']='release'
    if change=='exclude':options['--exclude-operational-receipts']=True
    if change=='relative':options['--project']='project'
    before=tree(tmp_path)
    result=run_request(tmp_path,value)
    assert result['code']==2,result
    assert tree(tmp_path)==before


@pytest.mark.parametrize('route', ('module','pyz'))
def test_work_resumes_same_source_across_processes_without_second_reference(tmp_path, distribution, route):
    root=tmp_path/'repo'; project(root); register(tmp_path,root)
    value=request(tmp_path,root,distribution[1]); value['options']['--work-dir']=str(tmp_path/'work')
    source={'source':ROOT/'src','module':distribution[0],'pyz':distribution[1]}[route]
    before=tree(root)
    first=run_request(tmp_path,value,source=source)
    assert first['code']==8, first
    assert not list((tmp_path/'output').glob('*Result*.zip'))
    resume={'command_id':'work.resume','arguments':{'work_dir':str(tmp_path/'work')}}
    second=run_request(tmp_path,resume,source=source)
    assert second['code']==8,second
    references=list((tmp_path/'output').glob('*.zip'))
    assert len(references)==1
    third=run_request(tmp_path,resume,source=source)
    assert third['code']==0,third
    assert len(list((tmp_path/'output').glob('*.zip')))==2
    assert tree(root)==before
    unchanged=tree(tmp_path/'output')
    repeated=run_request(tmp_path,resume,source=source)
    assert repeated['code']==0,repeated
    assert repeated['outcome']['result']==third['outcome']['result']
    assert tree(tmp_path/'output')==unchanged


def test_work_refuses_changed_source_without_rebinding(tmp_path,distribution):
    root=tmp_path/'repo'; project(root); register(tmp_path,root)
    value=request(tmp_path,root,distribution[1]); value['options']['--work-dir']=str(tmp_path/'work')
    assert run_request(tmp_path,value,source=distribution[0])['code']==8
    (root/'new.bin').write_bytes(b'changed source')
    result=run_request(tmp_path,{'command_id':'work.resume','arguments':{'work_dir':str(tmp_path/'work')}},source=distribution[0])
    assert result['code']==6,result
    assert not list((tmp_path/'output').glob('*.zip'))


def test_source_work_requires_recorded_build_before_writes(tmp_path,distribution):
    root=tmp_path/'repo';project(root);register(tmp_path,root)
    value=request(tmp_path,root,distribution[1]); value['options']['--work-dir']=str(tmp_path/'work')
    before=tree(tmp_path)
    result=run_request(tmp_path,value)
    assert result['code']==5,result
    assert tree(tmp_path)==before


def test_real_argv_uses_same_transport_variant(tmp_path,distribution):
    root=tmp_path/'repo';project(root);register(tmp_path,root)
    value=request(tmp_path,root,distribution[1]);args=['bundle','create']
    for flag,v in value['options'].items():
        for item in v if isinstance(v,list) else [v]:args.extend([flag,item])
    result=child(tmp_path,'from specroad.cli.application import dispatch_result\nimport json\n'
        +'r=dispatch_result('+repr(args)+')\nprint(json.dumps({"code":r.exit_code,"result":r.as_dict()}))')
    assert result['code']==0,result
    assert result['result']['summary']['command_class']=='transport_operational'


@pytest.mark.parametrize('operation', ('status','prompt','cancel','export'))
def test_pending_work_controls_preserve_original_request(tmp_path,distribution,operation):
    root=tmp_path/'repo';project(root);register(tmp_path,root)
    value=request(tmp_path,root,distribution[1]);value['options']['--work-dir']=str(tmp_path/'work')
    assert run_request(tmp_path,value,source=distribution[0])['code']==8
    req={'command_id':'work.'+operation,'arguments':{'work_dir':str(tmp_path/'work')}}
    if operation=='cancel':req['options']={'--reason':'Caller cancelled before export'}
    if operation=='export':
        (tmp_path/'work-export').mkdir()
        req['options']={'--output':str(tmp_path/'work-export/saved-work.zip')}
    result=run_request(tmp_path,req,source=distribution[0])
    assert result['code']==0,result
    assert not list((tmp_path/'output').glob('*.zip'))
    if operation=='export':
        restored=tmp_path/'restored-work'
        result=run_request(tmp_path,{'command_id':'work.restore',
            'arguments':{'file':str(tmp_path/'work-export/saved-work.zip')},'options':{'--output':str(restored)}},source=distribution[0])
        assert result['code']==0,result
        assert run_request(tmp_path,{'command_id':'work.resume','arguments':{'work_dir':str(restored)}},source=distribution[0])['code']==8


@pytest.mark.parametrize('point', ('capture_intent','after_publish'))
def test_work_process_death_does_not_repeat_reference_export(tmp_path,distribution,point):
    root=tmp_path/'repo';project(root);register(tmp_path,root)
    value=request(tmp_path,root,distribution[1]);value['options']['--work-dir']=str(tmp_path/'work')
    assert run_request(tmp_path,value,source=distribution[0])['code']==8
    resume={'command_id':'work.resume','arguments':{'work_dir':str(tmp_path/'work')}}
    if point=='after_publish':assert run_request(tmp_path,resume,source=distribution[0])['code']==8
    # The nested child genuinely dies. Its native orphan Work lease is retained;
    # the enclosing observer records its code without treating it as a result.
    body='''
import os
from specroad.transport.outbound import OutboundExport
'''+('OutboundExport.capture=lambda self:os._exit(91)\n' if point=='capture_intent' else '''
original=OutboundExport.publish
def dead(self,*args,**kwargs):
    original(self,*args,**kwargs)
    os._exit(91)
OutboundExport.publish=dead
''')+'''\nfrom specroad.cli.application import execute_request
execute_request('''+repr(resume)+''')
'''
    result=child(tmp_path,'''import subprocess,json
body='''+repr('import sys;sys.path.insert(0,'+repr(str(distribution[0]))+');\n'+body)+'''
r=subprocess.run([sys.executable,'-I','-S','-B','-c',body],capture_output=True)
print(json.dumps({'code':r.returncode}))''')
    assert result['code']==91,result
    preserved=tree(tmp_path/'output')
    refused=run_request(tmp_path,resume,source=distribution[0])
    assert refused['code']==7,refused
    assert refused['outcome']['diagnostics'][0]['code']=='CORE_SECURITY'
    assert tree(tmp_path/'output')==preserved
    assert (tmp_path/'output/handoff.zip').exists()==(point=='after_publish')
    assert len(list((tmp_path/'output').glob('*.zip')))==(2 if point=='after_publish' else 0)


@pytest.mark.parametrize('mixed', (False,True))
def test_legacy_runtime_result_options_are_not_aliases(tmp_path,distribution,mixed):
    root=tmp_path/'repo';project(root)
    value=request(tmp_path,root,distribution[1]);options=value['options']
    for new,old in (('--patchharbor-pyz','--runtime-reference'),
                    ('--patchharbor-pyz-sha256','--runtime-reference-sha256')):
        options[old]=options[new]
        if not mixed:del options[new]
    before=tree(tmp_path)
    result=run_request(tmp_path,value)
    assert result['code']==2,result
    assert tree(tmp_path)==before


@pytest.mark.parametrize('change', ('options','source','tasks','digest'))
def test_old_or_mixed_work_runtime_bindings_are_not_reinterpreted(tmp_path,distribution,change):
    root=tmp_path/'repo';project(root);register(tmp_path,root)
    value=request(tmp_path,root,distribution[1]);value['options']['--work-dir']=str(tmp_path/'work')
    body='''
import json
from hashlib import sha256
from pathlib import Path
from specroad.cli.application import execute_request
from specroad.model.canonical import canonical_json_bytes
from specroad.transport import TransportFailure
import specroad.work.transport as transport
original=transport._create_manifest
observed=[]
def capture(*args,**kwargs):
    value=original(*args,**kwargs);observed.append(value);return value
transport._create_manifest=capture
result=execute_request('''+repr(value)+''').result
assert result.exit_code==8
initial=observed[0]
value=initial.as_dict();objects=dict(initial.objects)
inputs=[dict(row) for row in initial.entries('inputs')]
tasks=[dict(row) for row in initial.entries('tasks')]
def files():
    return {str(p):p.read_bytes() for p in (Path.cwd()/'work').rglob('*') if p.is_file()}
before=files()
change='''+repr(change)+'''
if change=='options':
    options=value['normalized_arguments']['options']
    options['--runtime-reference']=options.pop('--patchharbor-pyz')
    options['--runtime-reference-sha256']=options.pop('--patchharbor-pyz-sha256')
elif change=='tasks':
    tasks[0]['range']={'adapter':'source-safe-outbound-v1'}
else:
    bound=json.loads(objects[inputs[0]['sha256']])
    if change=='source':bound['runtime_reference_sha256']=bound.pop('patchharbor_pyz_sha256')
    else:bound['patchharbor_pyz_sha256']='0'*64
    raw=canonical_json_bytes(bound);digest=sha256(raw).hexdigest();objects[digest]=raw
    inputs[0].update(sha256=digest,size=len(raw))
try:transport._checked(value,objects,inputs,tasks,[])
except TransportFailure as error:
    print(json.dumps({'code':error.exit_code,'reason':error.reason,'preserved':files()==before,
        'references':len(list((Path.cwd()/'output').glob('*.zip')))}))
else:raise AssertionError('old runtime binding was reinterpreted')
'''
    result=child(tmp_path,body,source=distribution[0])
    reasons={'options':'outbound_work_runtime_contract_invalid','source':'outbound_work_source_invalid',
             'tasks':'outbound_work_units_invalid','digest':'outbound_work_runtime_binding_invalid'}
    assert result=={'code':7,'reason':reasons[change],'preserved':True,'references':0}
