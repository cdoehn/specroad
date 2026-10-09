"""Real cooperative SRX/graph/payload boundaries and incomplete native windows."""
from contextlib import ExitStack
from copy import deepcopy
from hashlib import sha256
import io
import json
import sys
from unittest.mock import patch

import pytest

from specroad.runtime.consumption import CounterSample, ConsumptionError, WorkConsumption
from specroad.runtime.control_points import ControlPoint, ControlIntervals, PhaseBoundary
from specroad.runtime.controlled import evaluate_srx, fingerprint_file
from specroad.srx import EvaluationContext, SrxError, SrxProgram, evaluate_with_usage
from specroad.srx.evaluation import evaluation_steps
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.storage.byte_binding import fingerprint_reader, fingerprint_steps
from support.srx import roots, expression_document, field, literal, quantifier
from support.srx_graph import graph, count, reach, has
from support.relations import artifact, edge, aid
from support.read_only import inventory


def program(node, data=None, loaded=None):
    return (SrxProgram(expression_document(node), rule_id='controls'),
            EvaluationContext(roots() if data is None else data, rule_id='controls', graph=loaded))


def sequence(*values):
    records = iter(values)
    return lambda: CounterSample(*next(records), 'fixture:cpu', 'fixture:wall', 'fixture:rss')


def consume(steps):
    points = []
    while True:
        try:
            points.append(next(steps))
        except StopIteration as result:
            return result.value, points


def star(size):
    first = artifact(number=1, relations=[edge('depends_on', aid(number=n+2), number=n+1) for n in range(size)])
    return [first, *(artifact(number=n+2) for n in range(size))]


@pytest.mark.parametrize('size', [509, 510, 511, 1022, 1023])
def test_actual_srx_dispatch_boundaries_preserve_complete_value_and_usage(size):
    inputs = program(quantifier('all', literal([True] * size), field('', context='item')))
    baseline = evaluate_with_usage(*inputs)
    observed, points = consume(evaluation_steps(*inputs))
    controls = [p.completed for p in points if type(p) is ControlPoint and p.metric == 'srx_steps']
    assert controls == list(range(512, size + 3, 512))
    assert observed.value is baseline.value is True
    assert observed.usage.data == baseline.usage.data
    assert observed.usage.evaluation_steps == size + 2
    phases = [(p.phase, p.edge) for p in points if type(p) is PhaseBoundary]
    assert phases == [(name, side) for name in ('srx_validation', 'srx_evaluation', 'srx_result')
                      for side in ('start', 'end')]


def test_srx_control_is_yielded_before_later_real_failure_and_cannot_claim_completion():
    inputs = program(quantifier('all', literal([True] * 600 + [None]), field('', context='item')))
    steps = evaluation_steps(*inputs)
    before = []
    for point in steps:
        before.append(point)
        if type(point) is ControlPoint:
            assert point == ControlPoint('srx_steps', 512)
            break
    with pytest.raises(SrxError) as caught:
        list(steps)
    with pytest.raises(SrxError) as baseline:
        evaluate_with_usage(*inputs)
    assert caught.value.reason == baseline.value.reason
    assert caught.value.resource_usage.data == baseline.value.resource_usage.data
    assert caught.value.resource_usage.evaluation_completed is False
    assert PhaseBoundary('srx_evaluation', 'end') not in before


@pytest.mark.parametrize('size', [127, 128, 129, 256])
def test_graph_edge_controls_happen_inside_real_adjacency_processing(size):
    values = star(size); loaded = graph(values)
    inputs = program(count(), roots(values[0]), loaded)
    baseline = evaluate_with_usage(*inputs)
    actual, points = consume(evaluation_steps(*inputs))
    controls = [p.completed for p in points if type(p) is ControlPoint and p.metric == 'graph_steps']
    assert controls == list(range(128, size + 1, 128))
    assert actual.value == baseline.value == size and actual.usage.data == baseline.usage.data
    assert PhaseBoundary('graph_views', 'start') in points and PhaseBoundary('graph_views', 'end') in points


@pytest.mark.parametrize('operation', ['reach', 'filtered_has'])
def test_graph_controls_cover_candidate_roots_and_filtered_edges_without_result_changes(operation):
    values = star(129); loaded = graph(values)
    node = reach(aid(number=131), depth=1) if operation == 'reach' else has(types=['references'])
    inputs = program(node, roots(values[0]), loaded)
    baseline = evaluate_with_usage(*inputs)
    actual, points = consume(evaluation_steps(*inputs))
    controls = [p.completed for p in points if type(p) is ControlPoint and p.metric == 'graph_steps']
    assert actual.value is baseline.value is False and actual.usage.data == baseline.usage.data
    assert controls == list(range(128, actual.usage.graph_steps + 1, 128))


def test_pure_control_generator_reads_no_native_clock_or_sampler():
    values = star(128); loaded = graph(values)
    inputs = program(reach(aid(number=130), depth=1), roots(values[0]), loaded)
    def forbidden(*args, **kwargs):
        raise AssertionError('Pure evaluation accessed a host observer')
    with ExitStack() as stack:
        for name in ('time.time', 'time.monotonic', 'time.monotonic_ns', 'time.process_time_ns',
                     'specroad.runtime.consumption.native_sample', 'builtins.open', 'os.open',
                     'os.getenv', 'os.urandom', 'subprocess.Popen'):
            stack.enter_context(patch(name, forbidden))
        result, points = consume(evaluation_steps(*inputs))
    assert result.value is False and any(type(p) is ControlPoint for p in points)


@pytest.mark.parametrize('size', [0, 65535, 65536, 65537, 131072])
def test_payload_controls_are_actual_byte_boundaries_including_short_reads(size):
    raw = b'x' * size; source = io.BytesIO(raw); requests = []
    def read(limit):
        requests.append(limit)
        return source.read(min(limit, 10003))
    steps = fingerprint_steps(read, len(raw), block_size=1048576)
    points, positions = [], []
    while True:
        try:
            point = next(steps); points.append(point)
            if type(point) is ControlPoint:
                positions.append((point.completed, source.tell()))
        except StopIteration as done:
            result = done.value
            break
    assert positions == [(n, n) for n in range(65536, size+1, 65536)]
    assert max(requests) <= 65536
    assert result == fingerprint_reader(io.BytesIO(raw).read, len(raw))
    assert result.size == size and result.sha256 == sha256(raw).hexdigest()
    assert points[0] == PhaseBoundary('payload_hash', 'start') and points[-1] == PhaseBoundary('payload_hash', 'end')


def test_real_guarded_payload_driver_keeps_bytes_and_hash_and_samples_each_signal(tmp_path):
    raw = bytes(range(256)) * 513
    (tmp_path / 'attachments').mkdir(); target = tmp_path / 'attachments/payload.bin'; target.write_bytes(raw)
    before = inventory(tmp_path); samples = []
    def sample():
        n = len(samples); samples.append(n)
        return CounterSample(n, n * 2, 100)
    call = WorkConsumption(sampler=sample).begin()
    result = fingerprint_file(ProjectBoundary(tmp_path), 'attachments/payload.bin', call, block_size=1048576)
    report = call.finish(); controls = report['invocation']['controls']
    assert result.size == len(raw) and result.sha256 == sha256(raw).hexdigest()
    assert controls['intervals']['payload_bytes'] == {'checks': 2, 'interval': 65536, 'last_completed': 131072}
    assert controls['phases']['payload_hash'] == {'start': 1, 'end': 1}
    assert controls['checks'] == 4 and len(samples) == 6
    assert report['cumulative']['control_checks'] == 4 and inventory(tmp_path) == before


@pytest.mark.parametrize('problem', ['short', 'growing', 'oversized_block'])
def test_payload_failures_preserve_error_and_never_emit_successful_phase_end(problem):
    points = []
    if problem == 'short':
        steps = fingerprint_steps(io.BytesIO(b'x').read, 2)
    elif problem == 'growing':
        steps = fingerprint_steps(io.BytesIO(b'xx').read, 1)
    else:
        steps = fingerprint_steps(lambda n: b'x' * (n+1), 100000)
    with pytest.raises(SafetyViolation):
        for point in steps:
            points.append(point)
    assert points == [PhaseBoundary('payload_hash', 'start')]


def test_guarded_measured_reader_does_not_follow_symlink_or_remove_source(tmp_path):
    (tmp_path / 'attachments').mkdir(); (tmp_path / 'outside.bin').write_bytes(b'untouched')
    (tmp_path / 'attachments/link.bin').symlink_to(tmp_path / 'outside.bin')
    before = inventory(tmp_path); call = WorkConsumption().begin()
    with pytest.raises(SafetyViolation):
        fingerprint_file(ProjectBoundary(tmp_path), 'attachments/link.bin', call)
    report = call.finish()
    assert report['invocation']['controls']['checks'] == 0 and inventory(tmp_path) == before


def test_real_runtime_driver_samples_controls_without_changing_srx_inputs_or_policy():
    inputs = program(quantifier('all', literal([True] * 1025), field('', context='item')))
    original = deepcopy(inputs[1].data); baseline = evaluate_with_usage(*inputs)
    work = WorkConsumption()
    for profile in ('constrained', 'standard'):
        call = work.begin({'--resource-profile': profile, '--cpu-budget-ms': 1})
        measured = evaluate_srx(*inputs, call)
        report = call.finish(); controls = report['invocation']['controls']
        assert measured.value == baseline.value and measured.usage.data == baseline.usage.data
        assert controls['intervals']['srx_steps'] == {'interval': 512, 'checks': 2, 'last_completed': 1024}
        assert controls['checks'] == 8 and inputs[1].data == original
    assert report['invocations_recorded'] == 2 and report['cumulative']['control_checks'] == 16


@pytest.mark.parametrize('metric', ['cpu_ns', 'wall_ns', 'rss_peak_bytes'])
@pytest.mark.parametrize('problem', ['unknown', 'regression', 'source_change'])
def test_incomplete_intermediate_samples_stay_unknown_after_later_valid_finish(metric, problem):
    names = ('cpu_ns', 'wall_ns', 'rss_peak_bytes'); sources = dict(zip(names, ('cpu_source','wall_source','rss_source')))
    middle = dict(zip(names, (20, 20, 20)))
    if problem == 'unknown': middle[metric] = None
    elif problem == 'regression': middle[metric] = 9
    else: middle[sources[metric]] = 'different source'
    samples = iter([CounterSample(10, 10, 10), CounterSample(**middle), CounterSample(30, 30, 30)])
    work = WorkConsumption(sampler=lambda: next(samples)); call = work.begin()
    current = call.control(ControlPoint('srx_steps', 512)); report = call.finish()
    assert current['measured'][metric]['value'] is None
    assert report['invocation']['measured'][metric]['value'] is None
    assert report['cumulative']['measured'][metric]['measurement_kind'] == 'unknown'
    assert all(v['value'] is not None for k,v in report['invocation']['measured'].items() if k != metric)


def test_known_soft_overrun_is_retained_if_later_observation_becomes_unavailable():
    call = WorkConsumption(sampler=sequence((0, 0, 1), (2000000, 3000000, 2), (None, None, None))).begin(
        {'--cpu-budget-ms': 1, '--wall-budget-ms': 1})
    point = call.control(ControlPoint('graph_steps', 128)); report = call.finish()
    assert point['measured']['rss_peak_bytes']['scope'] == 'current_process_lifetime_peak'
    assert point['soft_budget_exceeded'] and report['soft_budget_exceeded']
    assert {e['metric'] for e in report['events']} >= {'cpu', 'wall'}
    assert report['invocation']['measured']['cpu_ns']['value'] is None


def test_srx_failure_leaves_partial_controls_and_allows_explicit_completion_and_next_call():
    inputs = program(quantifier('all', literal([True] * 600 + [None]), field('', context='item')))
    work = WorkConsumption(); call = work.begin()
    with pytest.raises(SrxError): evaluate_srx(*inputs, call)
    report = call.finish()
    assert report['invocation']['controls']['phases']['srx_evaluation'] == {'start': 1, 'end': 0}
    assert report['invocation']['controls']['intervals']['srx_steps']['checks'] == 1
    assert work.begin().finish()['invocations_recorded'] == 2


@pytest.mark.parametrize('point', [None, {'metric':'srx_steps','completed':512}, 'control'])
def test_untyped_control_cannot_invoke_native_sampling_or_change_counts(point):
    seen = []
    def sample(): seen.append(1); return CounterSample(1, 1, 1)
    call = WorkConsumption(sampler=sample).begin()
    with pytest.raises(ConsumptionError): call.control(point)
    assert len(seen) == 1 and call.finish()['invocation']['controls']['checks'] == 0


def test_closed_invocation_cannot_execute_another_real_srx_or_payload_operation(tmp_path):
    call = WorkConsumption().begin(); call.finish()
    with pytest.raises(ConsumptionError): evaluate_srx(*program(literal(True)), call)
    with pytest.raises(ConsumptionError): fingerprint_file(ProjectBoundary(tmp_path), 'attachments/missing.bin', call)


def test_control_reports_are_detached_and_retain_constant_size_aggregate_fields():
    call = WorkConsumption(sampler=lambda: CounterSample(1, 1, 1)).begin()
    for position in range(128, 128001, 128):
        report = call.control(ControlPoint('graph_steps', position))
        report['measured']['cpu_ns']['value'] = -1
    final = call.finish(); controls = final['invocation']['controls']
    assert controls['checks'] == 1000 and len(controls['intervals']) == 1 and controls['phases'] == {}
    assert final['invocation']['measured']['cpu_ns']['value'] == 0
    assert len(json.dumps(controls)) < 400 and controls['durable_checkpoint'] is False


def test_malformed_sources_are_usage_errors_and_unknown_optional_observations():
    with pytest.raises(ConsumptionError): CounterSample(0, 0, 0, '\ud800')
    def invalid_sample(): return CounterSample(0, 0, 0, '\ud800')
    call = WorkConsumption(sampler=invalid_sample).begin(); report = call.finish()
    assert all(m['value'] is None for m in report['invocation']['measured'].values())


def test_control_intervals_reject_a_jump_over_an_unobserved_boundary():
    controls = ControlIntervals()
    assert controls.advance('payload_bytes', 65535) is None
    with pytest.raises(ValueError): controls.advance('payload_bytes', 2)
    assert controls.advance('payload_bytes', 1) == ControlPoint('payload_bytes', 65536)


def test_real_graph_loading_has_observed_phase_edges_and_identical_loaded_records():
    from support.srx_graph import records
    from specroad.runtime.controlled import load_srx_graph
    values = star(2); call = WorkConsumption().begin()
    loaded = load_srx_graph(records(values), call, rule_id='controls')
    report = call.finish()
    assert loaded.artifact_ids == graph(values).artifact_ids
    assert all(loaded.artifact(v['id'], rule_id='controls') == v for v in values)
    assert report['invocation']['controls']['phases']['graph_load'] == {'start': 1, 'end': 1}


def test_measured_native_publication_retains_exact_targets_and_incomplete_receipt_state(tmp_path):
    from specroad.runtime.controlled import publish_prepared
    from support.committing import staged
    from support.publication import ALLOW, files
    with staged(tmp_path) as (model, plan, preflight, held, journal):
        original = files(tmp_path)
        call = WorkConsumption(sampler=sequence((0, 0, 1), (2000000, 2000000, 2),
                                                (4000000, 4000000, 3), (5000000, 5000000, 4))).begin(
            {'--cpu-budget-ms': 1, '--wall-budget-ms': 1})
        result = publish_prepared(preflight, journal, call, held_lock=held, authority=ALLOW)
        report = call.finish()
        assert files(tmp_path) == {**original, **{d.path:d.content for d in preflight.request.documents}}
        assert result.data['target_model_root_sha256'] == preflight.request.data['target_root_sha256']
        assert result.data['state'] == 'committing' and result.data['finalization_required']
        assert not result.data['commit_completed'] and not result.data['receipt_written']
        assert report['soft_budget_exceeded'] and held.check()
        assert report['invocation']['controls']['phases']['publication'] == {'start': 1, 'end': 1}


def test_measured_publication_keeps_native_authority_refusal_and_all_existing_bytes(tmp_path):
    from specroad.changes import PublicationAuthority, CommitPublicationError
    from specroad.runtime.controlled import publish_prepared
    from support.committing import staged
    with staged(tmp_path) as (model, plan, preflight, held, journal):
        before = inventory(tmp_path); call = WorkConsumption().begin()
        deny = PublicationAuthority('test-deny', '1', lambda request: False)
        with pytest.raises(CommitPublicationError) as error:
            publish_prepared(preflight, journal, call, held_lock=held, authority=deny)
        report = call.finish()
        assert error.value.exit_code == 7 and inventory(tmp_path) == before and held.check()
        assert report['invocation']['controls']['phases']['publication'] == {'start': 1, 'end': 0}


def test_unrepresentable_accumulated_cpu_remains_unknown_instead_of_breaking_json_report():
    digits = sys.get_int_max_str_digits() if hasattr(sys, 'get_int_max_str_digits') else 0
    huge = 10 ** digits - 1 if digits else 10 ** 20
    work = WorkConsumption(sampler=sequence((0, 0, 1), (huge, 1, 1), (0, 2, 1), (huge, 3, 1)))
    work.begin().finish(); report = work.begin().finish()
    assert report['invocation']['measured']['cpu_ns']['value'] == huge
    assert report['cumulative']['measured']['cpu_ns']['value'] == (None if digits else huge * 2)
    assert json.loads(json.dumps(report)) == report
