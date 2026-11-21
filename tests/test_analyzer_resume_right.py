"""Concrete worker/host failures retain real completed units and native bindings."""
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.analyzers._values import AnalyzerError, encoded
from specroad.analyzers._work_values import check_unit
from specroad.analyzers._work_worker import WorkWorker
from specroad.work.analyzer import checked, advance
from support.analyzer_acceptance import native_request
from support.analyzer_work_process import invoke, runtime_factory as runtime_factory
from support.read_only import inventory
from test_analyzer_resume import CASES


__all__ = ('runtime_factory',)

@pytest.mark.parametrize('fault', ['crash','malformed','wrong_unit','oom','missing_engine','changed_engine','full_scratch'])
def test_actual_failed_resume_preserves_durable_subjects_without_code_eight(tmp_path, runtime_factory, fault):
    runtime=runtime_factory(); request=native_request(tmp_path/'project',CASES)
    source=tmp_path/'request.json';source.write_bytes(request.canonical_bytes)
    work,trace=tmp_path/'work',tmp_path/'events'
    invoke(runtime,'start',source,work,trace,tmp_path)
    invoke(runtime,'one',source,work,trace,tmp_path)
    saved=invoke(runtime,'one',source,work,trace,tmp_path)
    pointer=(work/'work.json').read_bytes()
    result=invoke(runtime,'fail:'+fault,source,work,trace,tmp_path)
    assert result['exit_code']==5 and not result['complete'],result
    assert result.get('continuation') is None
    assert (work/'work.json').read_bytes()==pointer
    result=invoke(runtime,'finish',source,work,trace,tmp_path)
    assert result['exit_code']==1 and result['complete'],result
    # Publication failure may repeat its uncommitted subject, never the saved one.
    saved_unit=next(v for k,v in saved['done'].items() if k.startswith('subject:'))
    original=next(s['value'] for s in request.data['subjects'] if s['subject_key']==saved_unit['pair']['subject_key'])
    assert trace.read_text().splitlines().count('score:'+sha256(original.encode()).hexdigest())==1


def test_missing_native_work_object_is_concrete_and_does_not_start_worker(tmp_path,runtime_factory):
    runtime=runtime_factory(); request=native_request(tmp_path/'project',CASES)
    source=tmp_path/'request.json';source.write_bytes(request.canonical_bytes)
    work,trace=tmp_path/'work',tmp_path/'events'
    invoke(runtime,'start',source,work,trace,tmp_path)
    invoke(runtime,'one',source,work,trace,tmp_path)
    saved=invoke(runtime,'one',source,work,trace,tmp_path)
    digest=saved['completed'][-1]['evidence']['sha256']
    # Locate the content-addressed object by its full byte hash, independent of
    # the storage layout. Exactly this required object is made unavailable.
    objects=[p for p in work.rglob('*') if p.is_file() and sha256(p.read_bytes()).hexdigest()==digest]
    assert len(objects)==1
    raw=objects[0].read_bytes(); original_mode=objects[0].stat().st_mode
    retained=tmp_path/'retained-work-object'
    # Keep the original private file; recreating it would inherit the host umask.
    objects[0].rename(retained)
    before=inventory(work);events=trace.read_bytes()
    result=invoke(runtime,'finish',source,work,trace,tmp_path)
    assert result['exit_code']==5 and result.get('continuation') is None
    assert inventory(work)==before and trace.read_bytes()==events
    retained.rename(objects[0])
    assert objects[0].read_bytes()==raw and objects[0].stat().st_mode==original_mode
    result=invoke(runtime,'finish',source,work,trace,tmp_path)
    assert result['exit_code']==1, result


@pytest.mark.parametrize('fault',['binding','pair','engine','status','original','finding','score','comparison'])
def test_retained_unit_never_changes_request_policy_engine_or_original(tmp_path, fault):
    request=native_request(tmp_path/'project',[('en','short')])
    pair=dict(analyzer_id=request.data['analyzers'][0]['descriptor']['analyzer_id'],
        descriptor_sha256=request.data['analyzers'][0]['descriptor_sha256'],
        subject_key=request.data['subjects'][0]['subject_key'])
    with WorkWorker() as worker:
        rows=worker.engines(request);unit=worker.subject(request,pair)
    value=json.loads(encoded(unit))
    if fault=='binding':value['binding']['request_id']='foreign'
    elif fault=='pair':value['pair']['subject_key']='0'*64
    elif fault=='engine':value['engine_sha256']='0'*64
    elif fault=='status':value['subject']['status']='done'
    elif fault=='original':value['subject']['declared_language']='fr'
    elif fault=='finding':value['findings']=[]
    elif fault=='score':value['subject']['payload']['specroad.language_detection']['decision']['scores']=[{'language':'en','score':'NaN'}]
    else:value['subject']['payload']['specroad.language_detection']['comparison']={'status':'compatible'}
    with pytest.raises(AnalyzerError):check_unit(request,pair,rows,value)


def test_short_subjects_abstain_without_dependency_and_keep_complete_coverage(tmp_path):
    from specroad.analyzers._work_engine import WorkEngine
    request=native_request(tmp_path/'project',[('en','short'),('de','kurz')])
    with patch('specroad.analyzers._model_session.load_reference_model',side_effect=AssertionError('short text loaded model')):
        with WorkEngine(request) as engine:
            for original in request.data['subjects']:
                entry=request.data['analyzers'][0]
                pair=dict(analyzer_id=entry['descriptor']['analyzer_id'],descriptor_sha256=entry['descriptor_sha256'],subject_key=original['subject_key'])
                value=engine.subject(pair)
                check_unit(request,pair,engine.rows,value)
                assert value['subject']['status']=='undetermined'
                assert value['subject']['payload']['specroad.language_detection']['decision']['reason']=='insufficient_text'


def test_v1_work_retains_its_original_unavailable_contract(tmp_path,monkeypatch):
    from specroad.cli.commands import builtin_registry
    from specroad.work._analyzer_request import AnalyzerWorkRequest
    from specroad.work.manifest import _create_manifest
    from specroad.work.analyzer import units, outcome
    from specroad.work.resume import _runtime_build
    from test_analyzer_work_checkpoints_right import begun
    from specroad import _build
    monkeypatch.setattr(_build,'BUILD_METADATA',dict(format_version=1,hash_algorithm='specroad-dev-payload-v1',build_sha256='7'*64))
    _,store=begun(tmp_path)
    initial=store.read();args=initial.as_dict()['normalized_arguments']
    args['construction']['format_version']='analyzer-work-request-v1';args['construction'].pop('fail_on')
    registry=builtin_registry()
    binding=AnalyzerWorkRequest(registry,'analyzer.run',args).binding
    current=_create_manifest(registry,binding,tool_build=_runtime_build(),
        source_bindings=dict(project_id=None,scope=[],model_root_sha256=None),
        inputs=[dict(root_id='analyzer',path='construction.json',raw=encoded(args['construction']))],units=units(None,'analyzer.run'))
    with patch('subprocess.Popen',side_effect=AssertionError('legacy work executed a new engine')):
        for _ in range(6):
            if current.as_dict()['state']=='completed':break
            current=advance(current)
    assert current.as_dict()['state']=='completed'
    document,code=outcome(current)
    assert code==5 and all(r['run_status']=='unavailable' for r in document['reports'])
    assert checked(current)[0]['format_version']=='analyzer-work-request-v1'
