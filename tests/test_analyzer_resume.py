"""Real offline engines and durable Work across every boundary in new processes."""
from hashlib import sha256

import pytest

from specroad.analyzers.packages import ReportPackage
from specroad.analyzers._values import encoded
from specroad.analyzers.language_policy import execution_outcome
from support.analyzer_acceptance import native_request
from support.analyzer_work_process import invoke, runtime_factory as runtime_factory
from support.read_only import inventory

__all__ = ('runtime_factory',)

CASES = (
    ('en', 'The system shall preserve the complete original requirement and its declared language during every operation.'),
    ('de', 'Das System muss den vollständigen ursprünglichen Anforderungstext und seine deklarierte Sprache unverändert erhalten.'),
    ('fr', 'The application shall preserve every original character and every explicit normative value without silently changing the requirement.'),
)


@pytest.mark.parametrize('minor', ['3.10','3.11','3.12','3.13','3.14'])
def test_real_analysis_survives_every_checkpoint_in_a_fresh_process(tmp_path, runtime_factory, minor):
    runtime = runtime_factory(minor)
    request = native_request(tmp_path/'project', CASES)
    source = tmp_path/'request.json'; source.write_bytes(request.canonical_bytes)
    before = inventory(tmp_path/'project')
    work, trace = tmp_path/'work', tmp_path/'worker-events.txt'
    baseline = ReportPackage(encoded(invoke(runtime,'single',source,work,trace,tmp_path)['package']))
    assert all(r.data['run_status'] == 'complete' for r in baseline.reports)
    begin = invoke(runtime,'start',source,work,trace,tmp_path)
    assert begin == {'code':8,'identity':request.data['request_id']}
    previous = []
    # Snapshot, each actual subject, finalize, completion: each durable edge is
    # crossed by a different interpreter process using the same original build.
    for generation in range(1, len(CASES)+4):
        value = invoke(runtime,'one',source,work,trace,tmp_path)
        assert value['generation'] == generation
        assert value['completed'][:len(previous)] == previous
        previous = value['completed']
        assert value['request'] == request.data and value['fail_on'] == 'warning'
        assert len(value['remaining']) == max(0, len(CASES)+2-generation)
        if generation <= len(CASES)+2:
            assert value['state'] == 'running'
        else:
            assert value['state'] == 'completed'
    actual = ReportPackage(encoded(value['package']), request=request)
    assert [r.data['result_sha256'] for r in actual.reports] == [r.data['result_sha256'] for r in baseline.reports]
    assert value['code'] == execution_outcome(actual.reports, fail_on='warning')['exit_code'] == 1
    lines = trace.read_text().splitlines()
    assert sorted(v for v in lines if v.startswith('score:')) == sorted(
        'score:'+sha256(text.encode()).hexdigest() for _,text in CASES)
    assert lines.count('load') == len(CASES)+1
    saved = inventory(work)
    repeated = invoke(runtime,'repeat',source,work,trace,tmp_path)
    assert repeated['exit_code'] == 1 and repeated['result']['data'] == value['package']
    assert trace.read_text().splitlines() == lines and inventory(work) == saved
    assert inventory(tmp_path/'project') == before


def test_one_resume_owns_one_model_and_reuses_all_retained_units(tmp_path, runtime_factory):
    runtime = runtime_factory()
    request = native_request(tmp_path/'project', CASES)
    source = tmp_path/'request.json'; source.write_bytes(request.canonical_bytes)
    work, trace = tmp_path/'work', tmp_path/'events'
    invoke(runtime,'start',source,work,trace,tmp_path)
    result = invoke(runtime,'finish',source,work,trace,tmp_path)
    metrics = result['summary']['runtime']
    assert metrics['soft_budget_exceeded'] is False
    for metric, source_name in (('cpu_ns', 'test_fixed_cpu'), ('wall_ns', 'test_fixed_wall')):
        observed = metrics['invocation']['measured'][metric]
        assert observed['source'] == source_name and observed['value'] == 0
    assert metrics['invocation']['controls']['phases']['work_unit']['end'] > 0
    assert result['exit_code'] == 1 and result['complete'] is True, result
    package = ReportPackage(encoded(result['result']['data']),request=request)
    assert package.reports[0].data['coverage']['counts']['done'] == len(CASES)
    assert trace.read_text().splitlines().count('load') == 1
    assert len([s for s in trace.read_text().splitlines() if s.startswith('score:')]) == len(CASES)
