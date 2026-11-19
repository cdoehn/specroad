"""Binding, namespace and private-storage refusal cases for early analysis Work."""

import pytest

from specroad.cli.application import dispatch_result
from specroad.cli.commands import builtin_registry
from specroad.cli.results import thaw
from specroad.work.manifest import read_work_manifest, read_work_successor, _seal
from specroad.work._data_contract import WorkManifestError
from specroad.work.analyzer import advance
from specroad.analyzers._values import AnalyzerError
from support.read_only import inventory
from test_analyzer_subjects import project
from test_analyzer_cli import BUILTIN, call, json_file
from test_analyzer_work import early, finish, store_at


def begin(tmp_path):
    root=tmp_path/'project';project(root)
    result=early(['request','--project',str(root),'--analyzer',BUILTIN,
        '--analysis-id','same-id','--work-dir',str(tmp_path/'work')],tmp_path)
    assert result.exit_code==8
    return root,store_at(result.continuation.claim.work_dir)


@pytest.mark.parametrize('key,value',[('actor',{'id':'person'}),('request_id','same-id'),
    ('operations_sha256','0'*64),('plan_binding',{})])
def test_analysis_never_becomes_a_normative_work_request(tmp_path,key,value):
    _,store=begin(tmp_path);manifest=store.read(); changed=manifest.as_dict();changed[key]=value
    with pytest.raises(WorkManifestError):
        read_work_manifest(_seal(changed),manifest.objects,registry=builtin_registry(),
            expected_tool_build=changed['tool_build'])
    assert store.read().raw==manifest.raw


def test_renamed_analysis_cannot_be_a_successor_even_with_resealed_hash(tmp_path):
    _,store=begin(tmp_path);original=store.read();changed=advance(original)
    value=changed.as_dict();value['normalized_arguments']['analysis_id']='different-id'
    with pytest.raises((WorkManifestError,AnalyzerError)):
        read_work_successor(_seal(value),changed.objects,previous=original,
            registry=builtin_registry(),expected_tool_build=value['tool_build'])
    assert store.read().raw==original.raw


@pytest.mark.parametrize('change',['bytes','replace_root'])
def test_changed_construction_source_is_a_conflict_without_replacing_checkpoint(tmp_path,change):
    root,store=begin(tmp_path);before=inventory(tmp_path/'work')
    if change=='bytes':
        path=root/'specroad.json';path.write_bytes(path.read_bytes()+b' ')
    else:
        moved=tmp_path/'old-project';root.rename(moved);project(root)
    result=dispatch_result(['work','resume',str(tmp_path/'work')],cwd=tmp_path)
    assert result.exit_code==6 and result.continuation is None
    assert inventory(tmp_path/'work')==before


@pytest.mark.parametrize('options',[['--actor-id','x'],['--request-id','same-id'],
    ['--as-proposal'],['--dry-run'],['--analysis-id','bad id']])
def test_normative_options_and_bad_identity_are_rejected_before_work(tmp_path,options):
    root=tmp_path/'project';project(root)
    result=early(['request','--project',str(root),'--analyzer',BUILTIN,
        '--work-dir',str(tmp_path/'work'),*options],tmp_path)
    assert result.exit_code==2 and not (tmp_path/'work').exists()


@pytest.mark.parametrize('mode',['inside','symlink'])
def test_work_root_cannot_alias_or_enter_project(tmp_path,mode):
    root=tmp_path/'project';project(root);before=inventory(root)
    target=root/'work'
    if mode=='symlink':
        alias=tmp_path/'alias';alias.symlink_to(root,target_is_directory=True);target=alias/'work'
    result=early(['request','--project',str(root),'--analyzer',BUILTIN,'--work-dir',str(target)],tmp_path)
    assert result.exit_code==7 and result.continuation is None and inventory(root)==before


def test_unfinished_and_sealed_snapshots_export_restore_with_identity(tmp_path):
    root,store=begin(tmp_path)
    for stage in ('unsealed','sealed'):
        if stage=='sealed':store._update(advance)
        packages=tmp_path/('packages-'+stage);packages.mkdir()
        target=packages/'work.zip'
        exported=dispatch_result(['work','export',str(tmp_path/'work'),'--output',str(target)],cwd=tmp_path)
        assert exported.exit_code==0 and target.is_file()
        restored=tmp_path/('restored-'+stage)
        result=dispatch_result(['work','restore',str(target),'--output',str(restored)],cwd=tmp_path)
        assert result.exit_code==0
        assert store_at(restored).read().raw==store.read().raw
        complete=finish(restored,tmp_path)
        assert complete.exit_code==0 and thaw(complete.result)['data']['request_id']=='same-id'
    assert not (root/'.specroad'/'requests').exists()


def test_override_of_projectless_request_and_missing_id_keep_usage_data_split(tmp_path):
    root=tmp_path/'project';project(root)
    request=thaw(call(['request','--analyzer',BUILTIN],root).result)
    filename=tmp_path/'request.json';json_file(filename,request)
    result=early(['run','--request',str(filename),'--analysis-id','override'],tmp_path)
    assert result.exit_code==2
    del request['request_id'];json_file(filename,request)
    result=early(['run','--request',str(filename)],tmp_path)
    assert result.exit_code==3 and result.continuation is None


from test_analyzer_work import recorded as recorded
__all__ = ('recorded',)
