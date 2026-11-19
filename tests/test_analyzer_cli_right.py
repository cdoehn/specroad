"""Immutable publication, denied options, malformed selections and native races."""
from dataclasses import replace
import json
import os

import pytest

from specroad.cli.application import execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandUsageError, PositionalSpec
from specroad.cli.request_schema import request_schema
from specroad.cli.requests import CommandRequest
from specroad.cli.results import thaw
from specroad.model._schema import validate_builtin
from specroad.model.errors import ModelError
from specroad.analyzers.requests import AnalyzerRequest
from specroad.analyzers.files import InputFile
from support.read_only import inventory, no_write_attempts
from test_analyzer_cli import call, observation_files, outputs, BUILTIN


def test_identical_file_is_noop_without_any_write_or_inode_mode_timestamp_change(tmp_path):
    observation_files(tmp_path); target=outputs(tmp_path)/'copy.json'
    args=['import','report.json','--project',str(tmp_path),'--output','copy.json']
    assert call(args,tmp_path).exit_code == 0
    target.chmod(0o640); before=target.stat(); tree=inventory(tmp_path)
    with no_write_attempts(): result=call(args,tmp_path)
    after=target.stat()
    assert result.exit_code == 0 and not result.details['publication']['changed']
    assert (before.st_ino,before.st_mode,before.st_mtime_ns,before.st_ctime_ns)==(after.st_ino,after.st_mode,after.st_mtime_ns,after.st_ctime_ns)
    assert inventory(tmp_path)==tree


def test_different_output_never_overwrites_or_leaves_temporary_files(tmp_path):
    observation_files(tmp_path); target=outputs(tmp_path)/'copy.json'; target.write_bytes(b'keep this')
    before=inventory(tmp_path)
    with no_write_attempts(): result=call(['import','report.json','--project',str(tmp_path),'--output','copy.json'],tmp_path)
    assert result.exit_code == 6 and inventory(tmp_path)==before


@pytest.mark.parametrize('option,value',[('--actor-type','human'),('--actor-id','operator'),('--request-id','write-id'),
    ('--dry-run',None),('--as-proposal',None)])
@pytest.mark.parametrize('command',['list','describe','request','run','import','show','evaluate'])
def test_normative_write_options_are_usage_errors_before_handlers(tmp_path,command,option,value):
    positions={'describe':[BUILTIN],'import':['missing.json'],'show':['missing.json'],'evaluate':['missing.json']}.get(command,[])
    with no_write_attempts(): result=call([command,*positions,option,*([] if value is None else [value])],tmp_path)
    assert result.exit_code == 2


@pytest.mark.parametrize('option,value',[('--analyzer',BUILTIN),('--subject','SR-REQ-0001'),('--field','/statement'),
    ('--analysis-id','new-id'),('--inputs','inputs.json'),('--configuration','SR-CONF-0001')])
def test_request_execution_has_no_selection_or_settings_overrides(tmp_path,option,value):
    with no_write_attempts(): result=call(['run','--request','does-not-exist',option,value],tmp_path)
    assert result.exit_code == 2


@pytest.mark.parametrize('value',['bad id','-bad','x'*129,'é'])
def test_invalid_analysis_id_is_rejected_before_missing_project_preflight(tmp_path,value):
    with no_write_attempts(): result=call(['request','--analyzer',BUILTIN,'--analysis-id',value,'--project','missing'],tmp_path)
    assert result.exit_code == 2


@pytest.mark.parametrize('value',[[], 'report.json', [True], [1], [''], ['report.json',False]])
def test_variadic_array_contract_rejects_bad_structured_values(tmp_path,value):
    request={'command_id':'analyzer.evaluate','arguments':{'files':value}}
    result=execute_request(request,cwd=tmp_path).result
    assert result.exit_code == 2


def test_variadic_binding_does_not_change_scalar_contract_or_allow_nonfinal_repeat():
    registry=builtin_registry(); scalar=registry.resolve('analyzer.show')
    with pytest.raises(CommandUsageError):
        registry.bind_request(CommandRequest('analyzer.show',arguments={'file':['one.json']}))
    with pytest.raises(CommandUsageError):
        replace(scalar,positionals=(PositionalSpec('a',repeatable=True),PositionalSpec('b')))
    command=registry.resolve('analyzer.evaluate')
    request={'command_id':'analyzer.evaluate','arguments':{'files':['a.json','b.json']}}
    validate_builtin(request,request_schema(command))
    with pytest.raises(ModelError):validate_builtin({**request,'arguments':{'files':'a.json'}},request_schema(command))


def test_selected_missing_file_is_preserved_next_to_complete_readable_reports(tmp_path):
    observation_files(tmp_path)
    result=call(['evaluate','missing.json','report.json'],tmp_path)
    assert result.exit_code == 5
    data=thaw(result.result); rows=data['evaluation']['reports']
    assert len(rows)==3 and rows[0]['currentness']=='unavailable' and rows[0]['failure_code']==5
    assert rows[0]['source_sha256'] is None and data['sources'][0]['sha256'] is None
    assert [r['input_index'] for r in rows]==[0,1,1]


@pytest.mark.parametrize('method',['absolute','explicit_root'])
def test_projectless_import_has_explicit_external_output_root(tmp_path,method):
    source=tmp_path/'source'; observation_files(source)
    target=tmp_path/'out'; target.mkdir()
    args=['import',str(source/'report.json'),'--output']
    args += [str(target/'copy.json')] if method=='absolute' else ['copy.json','--output-root',str(target)]
    result=call(args,tmp_path)
    assert result.exit_code==0 and (target/'copy.json').read_bytes()==(source/'report.json').read_bytes()


@pytest.mark.parametrize('kind',['leaf_link','parent_link','hardlink','fifo','model','escape','external_project'])
def test_generated_output_cannot_cross_native_security_boundaries(tmp_path,kind):
    root=tmp_path/'project'; observation_files(root); target=outputs(root)
    out='out.json'; extra=[]
    if kind=='leaf_link':(target/out).symlink_to(root/'report.json')
    elif kind=='parent_link':
        (target/'linked').symlink_to(root,target_is_directory=True);out='linked/out.json'
    elif kind=='hardlink':os.link(root/'report.json',target/out)
    elif kind=='fifo':os.mkfifo(target/out)
    elif kind=='model':out=str(root/'specroad.json')
    elif kind=='escape':out='../outside.json'
    elif kind=='external_project':extra=['--output-root',str(root)]
    # Do not use inventory's read_bytes on a FIFO.
    original=(root/'report.json').read_bytes(); config=(root/'specroad.json').read_bytes()
    result=call(['import','report.json','--project',str(root),'--output',out,*extra],root)
    assert result.exit_code==7
    assert (root/'report.json').read_bytes()==original and (root/'specroad.json').read_bytes()==config
    assert not (root/'outside.json').exists()


def test_source_change_before_publication_is_conflict_and_leaves_no_output(tmp_path,monkeypatch):
    observation_files(tmp_path); target=outputs(tmp_path)
    original=InputFile.current
    def changed(self):
        if self.path.name=='report.json':self.path.write_bytes(self.raw+b' ')
        return original(self)
    monkeypatch.setattr(InputFile,'current',changed)
    result=call(['import','report.json','--project',str(tmp_path),'--output','out.json'],tmp_path)
    assert result.exit_code==6 and list(target.iterdir())==[]


def test_failed_publication_removes_only_its_private_image(tmp_path,monkeypatch):
    import specroad.analyzers.files as files
    observation_files(tmp_path); target=outputs(tmp_path)
    def fail(*args,**kwargs):raise OSError('simulated failed publication')
    monkeypatch.setattr(files,'replace_bound_image',fail)
    result=call(['import','report.json','--project',str(tmp_path),'--output','out.json'],tmp_path)
    assert result.exit_code==5 and list(target.iterdir())==[]


def test_fail_on_warning_and_strict_only_change_threshold_not_analysis(tmp_path):
    observation_files(tmp_path); before=inventory(tmp_path)
    common=['evaluate','report.json','--project',str(tmp_path),'--inputs','inputs.json']
    with no_write_attempts():
        normal=call(common,tmp_path); strict=call([*common,'--strict'],tmp_path)
        warning=call([*common,'--fail-on','warning'],tmp_path)
    assert normal.exit_code==0 and strict.exit_code==warning.exit_code==1
    assert thaw(normal.result)['evaluation']==thaw(strict.result)['evaluation']
    assert inventory(tmp_path)==before


def test_native_partial_request_exports_only_verified_members(tmp_path):
    from test_partial_read_commands import extracted
    root,_,_,members,_=extracted(tmp_path)
    selected=[v for v in members if v.get('artifact_type')=='requirement']
    before=inventory(root)
    with no_write_attempts():result=call(['request','--analyzer',BUILTIN,'--project',str(root)],tmp_path)
    assert result.exit_code==0
    request=AnalyzerRequest(json.dumps(thaw(result.result)).encode())
    assert {s['artifact_id'] for s in request.data['subjects']}=={v['id'] for v in selected}
    assert inventory(root)==before
