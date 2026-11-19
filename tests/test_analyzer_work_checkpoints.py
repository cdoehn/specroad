"""Native durable subject units, immutable results and lazy external storage."""
import json
from pathlib import Path

import pytest

from specroad.cli.application import dispatch_result
from specroad.cli.results import thaw
from specroad.analyzers.packages import ReportPackage
from specroad.work.analyzer import checked, resume_analyzer_work
from support.read_only import inventory, no_write_attempts
from test_analyzer_subjects import project
from test_analyzer_cli import BUILTIN, call
from test_analyzer_work import early, store_at, finish


@pytest.mark.parametrize('name',['request','run'])
def test_small_finished_analysis_does_not_allocate_even_declared_work_dir(tmp_path,name):
    root=tmp_path/'project';project(root);before=inventory(root)
    with no_write_attempts():
        result=call([name,'--project',str(root),'--analyzer',BUILTIN,
            '--work-dir',str(tmp_path/'unused')],tmp_path)
    assert result.exit_code==(0 if name=='request' else 5) and result.complete
    assert not (tmp_path/'unused').exists() and inventory(root)==before


def test_completed_subject_units_are_reused_by_fresh_openers(tmp_path,monkeypatch):
    from specroad.work import _analyzer_results as execution
    root=tmp_path/'project';project(root,texts=tuple(f'Complete subject {i}.' for i in range(7)))
    result=early(['run','--project',str(root),'--analyzer',BUILTIN,'--work-dir',str(tmp_path/'work')],tmp_path)
    assert result.exit_code==8
    path=Path(result.continuation.claim.work_dir)
    calls=[];original=execution.prepare_subject
    def counted(request, task):
        calls.append(task['key']);return original(request,task)
    monkeypatch.setattr(execution,'prepare_subject',counted)
    store=store_at(path);snapshot=resume_analyzer_work(store)
    assert len(snapshot.entries('remaining'))==8
    first=resume_analyzer_work(store)
    saved=first.entries('completed')
    assert len(calls)==1 and len(saved)==2
    # Live project changes after sealing cannot replace the owned request.
    (root/'private.txt').write_text('changed unselected live file')
    complete=finish(path,tmp_path)
    assert complete.exit_code==5 and len(calls)==len(set(calls))==7
    final=store_at(path).read();assert final.entries('completed')[:2]==saved
    package=ReportPackage(json.dumps(thaw(complete.result)['data']).encode())
    assert len(package.request.data['subjects'])==7
    _,sealed_request,_=checked(snapshot)
    assert package.request.canonical_bytes==sealed_request.canonical_bytes
    expected_keys=sorted(subject['subject_key'] for subject in sealed_request.data['subjects'])
    assert len(expected_keys)==7 and len(package.reports)==1
    assert package.reports[0].data['coverage']=={
        'expected':expected_keys, 'open':expected_keys,
        'done':[], 'undetermined':[], 'failed':[],
        'counts':{'expected':7, 'open':7, 'done':0, 'undetermined':0, 'failed':0}}
    assert [subject['subject_key'] for subject in package.reports[0].data['subjects']]==expected_keys
    assert all(subject['status']=='open' for subject in package.reports[0].data['subjects'])
    assert package.reports[0].data['run_status']=='unavailable'
    repeated=dispatch_result(['work','resume',str(path)],cwd=tmp_path)
    assert repeated.exit_code==5 and thaw(repeated.result)==thaw(complete.result)
    assert len(calls)==7 and store_at(path).read().raw==final.raw


def test_sealed_work_is_self_contained_after_export_and_source_removal(tmp_path):
    root=tmp_path/'project';project(root)
    result=early(['run','--project',str(root),'--analyzer',BUILTIN,'--work-dir',str(tmp_path/'work')],tmp_path)
    store=store_at(result.continuation.claim.work_dir);resume_analyzer_work(store,max_units=2)
    old=store.read();assert checked(old)[1] is not None
    packages=tmp_path/'packages';packages.mkdir();target=packages/'portable.zip'
    exported=dispatch_result(['work','export',str(tmp_path/'work'),'--output',str(target)],cwd=tmp_path)
    assert exported.exit_code==0
    root.rename(tmp_path/'moved-project')
    restored=tmp_path/'restored'
    result=dispatch_result(['work','restore',str(target),'--output',str(restored)],cwd=tmp_path)
    assert result.exit_code==0 and store_at(restored).read().raw==old.raw
    done=finish(restored,tmp_path)
    assert done.exit_code==5 and len(thaw(done.result)['data']['request']['subjects'])==2


def test_snapshot_binds_all_selected_values_before_any_subject_result(tmp_path):
    root=tmp_path/'project';values=project(root)
    result=early(['run','--project',str(root),'--analyzer',BUILTIN,'--field','/statement',
        '--field','/title','--work-dir',str(tmp_path/'work')],tmp_path)
    store=store_at(result.continuation.claim.work_dir);current=resume_analyzer_work(store)
    _,request,done=checked(current)
    assert list(done)==['snapshot'] and len(request.data['subjects'])==4
    assert current.as_dict()['source_bindings']['model_root_sha256'] is None
    inputs={row['path']:row for row in current.entries('inputs')}
    from hashlib import sha256
    assert inputs['request.json']['sha256']==sha256(request.canonical_bytes).hexdigest()
    assert {s['artifact_id'] for s in request.data['subjects']}=={v['id'] for v in values}
    remaining=current.entries('remaining')
    assert len(remaining)==5 and {u['range']['subject_key'] for u in remaining[:-1]}=={
        s['subject_key'] for s in request.data['subjects']}


from test_analyzer_work import recorded as recorded
__all__ = ('recorded',)
