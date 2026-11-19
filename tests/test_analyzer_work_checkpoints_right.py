"""Real storage failures, mismatched resume bindings and engine fences."""
import errno

import pytest

from specroad.cli.application import dispatch_result
from specroad.analyzers._values import AnalyzerError
from specroad.work.analyzer import resume_analyzer_work, checked
from specroad.runtime.consumption import WorkConsumption, CounterSample
from support.read_only import inventory
from test_analyzer_subjects import project
from test_analyzer_cli import BUILTIN
from test_analyzer_work import early, store_at, finish


def begun(tmp_path):
    root=tmp_path/'project';project(root)
    result=early(['run','--project',str(root),'--analyzer',BUILTIN,'--work-dir',str(tmp_path/'work')],tmp_path)
    assert result.exit_code==8
    return root,store_at(result.continuation.claim.work_dir)


@pytest.mark.parametrize('expected',[{'expected_analysis_id':'foreign-analysis'},
    {'expected_snapshot_sha256':'0'*64}])
def test_wrong_resume_binding_is_conflict_and_keeps_all_persisted_bytes(tmp_path,expected):
    _,store=begun(tmp_path);resume_analyzer_work(store)
    before=inventory(tmp_path/'work')
    with pytest.raises(AnalyzerError) as error:resume_analyzer_work(store,**expected)
    assert error.value.exit_code==6 and inventory(tmp_path/'work')==before


def test_engine_change_cannot_mix_a_new_result_into_existing_subjects(tmp_path,monkeypatch):
    from specroad.work import analyzer
    _,store=begun(tmp_path);resume_analyzer_work(store,max_units=2)
    before=inventory(tmp_path/'work');original=analyzer.engines
    def changed(request):
        rows=original(request);rows[0]['reason']='different-worker';return rows
    monkeypatch.setattr(analyzer,'engines',changed)
    result=dispatch_result(['work','resume',str(tmp_path/'work')],cwd=tmp_path)
    assert result.exit_code==6 and result.continuation is None
    assert inventory(tmp_path/'work')==before


def test_no_checkpoint_space_before_snapshot_is_real_five_not_eight(tmp_path,monkeypatch):
    from specroad.work.checkpoints import CheckpointStore
    root=tmp_path/'project';project(root);before=inventory(root)
    def full(*args,**kwargs):raise OSError(errno.ENOSPC,'No space for checkpoint')
    monkeypatch.setattr(CheckpointStore,'_publish_held',full)
    result=early(['run','--project',str(root),'--analyzer',BUILTIN,'--work-dir',str(tmp_path/'work')],tmp_path)
    assert result.exit_code==5 and result.continuation is None and not result.complete
    assert inventory(root)==before and not (tmp_path/'work'/'work.json').exists()


def test_storage_failure_after_seal_can_finish_small_request_in_memory(tmp_path,monkeypatch):
    from specroad.work.checkpoints import CheckpointStore
    root=tmp_path/'project';project(root);before=inventory(root)
    samples=iter((0,0))
    def sample():
        value=next(samples,2000000);return CounterSample(value,value,1)
    def full(*args,**kwargs):raise OSError(errno.ENOSPC,'No space for checkpoint')
    monkeypatch.setattr(CheckpointStore,'_publish_held',full)
    result=dispatch_result(['analyzer','request','--project',str(root),'--analyzer',BUILTIN,
        '--step-wall-ms','1','--work-dir',str(tmp_path/'work')],cwd=tmp_path,
        consumption=WorkConsumption(sampler=sample))
    assert result.exit_code==0 and result.complete and len(result.result['subjects'])==2
    assert result.continuation is None and inventory(root)==before


def test_failed_successor_keeps_completed_subjects_and_remains_resumable(tmp_path,monkeypatch):
    from specroad.work.checkpoints import CheckpointStore
    _,store=begun(tmp_path);resume_analyzer_work(store,max_units=2)
    prior=store.read();original=CheckpointStore._publish_held
    def full(*args,**kwargs):raise OSError(errno.ENOSPC,'No space for next generation')
    with monkeypatch.context() as local:
        local.setattr(CheckpointStore,'_publish_held',full)
        result=dispatch_result(['work','resume',str(tmp_path/'work')],cwd=tmp_path)
        assert result.exit_code==5 and result.continuation is None
    assert CheckpointStore._publish_held is original
    assert store.read().raw==prior.raw
    assert finish(tmp_path/'work',tmp_path).exit_code==5
    assert store.read().entries('completed')[:2]==prior.entries('completed')


def test_completed_work_keeps_report_bytes_after_engine_change(tmp_path,monkeypatch):
    from specroad.work import analyzer
    _,store=begun(tmp_path)
    result=finish(tmp_path/'work',tmp_path);saved=store.read().raw
    def forbidden(*args):raise AssertionError('Completed output re-executed')
    monkeypatch.setattr(analyzer,'engines',forbidden)
    repeated=dispatch_result(['work','resume',str(tmp_path/'work')],cwd=tmp_path)
    assert repeated.exit_code==result.exit_code==5 and repeated.result==result.result
    assert store.read().raw==saved and checked(store.read())[1] is not None


from test_analyzer_work import recorded as recorded
__all__ = ('recorded',)
