"""Native observations, explicit arithmetic fixtures and real measured consumers."""
from copy import deepcopy
import json
import sys
from unittest.mock import patch

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.runtime.consumption import CounterSample, ConsumptionError, WorkConsumption, native_sample
from specroad.srx import EvaluationContext, SrxProgram, evaluate_with_usage
from support import run_cli
from support.model import configuration_file, put
from support.read_only import inventory
from support.srx import roots, expression_document, literal


def samples(*values):
    supplied = iter(values)
    return lambda: CounterSample(*next(supplied), 'fixture:cpu', 'fixture:wall', 'fixture:rss')


def measured(root, work=None, **options):
    return execute_request({'command_id': 'environment.check',
        'options': {'--metrics': True, **options}}, cwd=root, consumption=work).result


@pytest.mark.parametrize('route', ['cli', 'structured', 'registry'])
def test_real_environment_metrics_are_explicit_qualified_and_do_not_write(tmp_path, route):
    before = inventory(tmp_path)
    if route == 'cli':
        child = run_cli(['environment', 'check', '--metrics', '--format', 'json'], tmp_path, capture=True)
        assert child.returncode == 0, child.stderr
        document = json.loads(child.stdout)
    elif route == 'structured':
        document = measured(tmp_path).as_dict()
    else:
        registry = builtin_registry()
        document = registry.execute_result(registry.parse(['environment', 'check', '--metrics']), cwd=tmp_path).as_dict()
    report = document['summary']['runtime']
    assert document['status'] == 'success'
    values = report['invocation']['measured']
    for metric in ('cpu_ns', 'wall_ns'):
        assert type(values[metric]['value']) is int and values[metric]['value'] >= 0
        assert values[metric]['unit'] == 'ns' and values[metric]['measurement_kind'] == 'measured'
    rss = values['rss_peak_bytes']
    if sys.platform.startswith('linux'):
        assert type(rss['value']) is int and rss['value'] > 0
        assert rss['scope'] == 'current_process_lifetime_peak'
    else:
        assert rss['value'] is None and rss['measurement_kind'] == 'unknown'
    assert report['host_capacity_known'] is False and report['includes_child_processes'] is False
    assert report['includes_interpreter_start'] is False and report['includes_result_delivery'] is False
    assert report['persistent_work_available'] is False and report['checkpoint'] is None
    assert report['invocations_recorded'] == 1
    assert document['result']['resource_policy']['budget_engine_available'] is False
    assert 'runtime' not in document['result'] and inventory(tmp_path) == before


def test_without_metrics_no_sampler_runs_and_no_measurement_is_exposed(tmp_path):
    with patch('specroad.runtime.consumption.native_sample', side_effect=AssertionError('Unrequested sampling')):
        document = dispatch_result(['environment', 'check'], cwd=tmp_path).as_dict()
    assert 'runtime' not in document['summary'] and document['status'] == 'success'


def test_metrics_keep_the_same_complete_environment_payload(tmp_path):
    configuration_file(tmp_path, resource_limits={'srx_graph_steps': 1})
    baseline = dispatch_result(['environment', 'check', '--project', str(tmp_path)], cwd=tmp_path)
    current = measured(tmp_path, **{'--project': str(tmp_path)})
    assert baseline.exit_code == current.exit_code == 0
    assert baseline.result == current.result
    assert baseline.project == current.project and baseline.diagnostics == current.diagnostics
    assert current.details['runtime']['effective_budgets'] == current.result['resource_policy']['effective_budgets']
    assert current.details['runtime']['effective_budgets']['graph']['value'] == 1


def test_reused_work_adds_real_command_windows_without_cumulative_budget_refusal(tmp_path):
    work = WorkConsumption(sampler=samples((100, 1000, 8), (3000100, 9001000, 12),
                                          (9000000, 99000000, 12), (14000000, 106000000, 20)))
    first_result = measured(tmp_path, work, **{'--cpu-budget-ms': '1', '--step-cpu-ms': '1'})
    second_result = measured(tmp_path, work, **{'--resource-profile': 'standard', '--cpu-budget-ms': '1'})
    first, second = first_result.as_dict(), second_result.as_dict()
    one, two = first['summary']['runtime'], second['summary']['runtime']
    assert first_result.exit_code == second_result.exit_code == 0
    assert one['invocation']['measured']['cpu_ns']['value'] == 3000000
    assert two['invocation']['measured']['cpu_ns']['value'] == 5000000
    assert two['cumulative']['measured']['cpu_ns']['value'] == 8000000
    assert two['cumulative']['measured']['wall_ns']['value'] == 16000000
    assert two['cumulative']['measured']['rss_peak_bytes']['value'] == 20
    assert one['invocations_recorded'] == 1 and two['invocations_recorded'] == 2
    assert one['soft_budget_exceeded'] and two['soft_budget_exceeded']
    assert one['profile'] == 'constrained' and two['profile'] == 'standard'
    assert two['cumulative']['measured']['cpu_ns']['source'] == 'fixture:cpu'


@pytest.mark.parametrize('kind', ['memory', 'scratch'])
def test_registered_byte_peaks_survive_calls_and_are_not_measured_rss(kind):
    work = WorkConsumption(sampler=samples((0, 0, 100), (1, 2, 200), (4, 8, 200), (5, 10, 250)))
    first = work.begin({'--memory-budget-mib': 1, '--scratch-budget-mib': 1})
    first.account_bytes(kind, 2000000)
    first.account_bytes(kind, 1000000, release=True)
    before = first.finish()
    second = work.begin()
    second.account_bytes(kind, 1000000, release=True)
    after = second.finish()
    key = kind + '_peak_bytes'
    assert before['invocation']['accounted'][key]['value'] == 2000000
    assert after['invocation']['accounted'][key]['value'] == 1000000
    assert after['cumulative']['accounted'][key]['value'] == 2000000
    assert after['cumulative']['accounted'][key]['measurement_kind'] == 'accounted'
    assert after['cumulative']['measured']['rss_peak_bytes']['value'] == 250
    assert before['soft_budget_exceeded'] and any(e['metric'] == kind for e in before['events'])


@pytest.mark.parametrize('bad', [-1, True, 1.5, '1', None])
def test_invalid_byte_registrations_do_not_change_accounted_state(bad):
    call = WorkConsumption(sampler=samples((0, 0, 10), (1, 1, 10))).begin()
    with pytest.raises(ConsumptionError):
        call.account_bytes('memory', bad)
    assert call.finish()['invocation']['accounted']['memory_peak_bytes']['value'] == 0


def test_releasing_unregistered_bytes_cannot_create_negative_consumption():
    call = WorkConsumption(sampler=samples((0, 0, 1), (1, 2, 3))).begin()
    call.account_bytes('scratch', 3)
    with pytest.raises(ConsumptionError):
        call.account_bytes('scratch', 4, release=True)
    call.account_bytes('scratch', 3, release=True)
    assert call.finish()['invocation']['accounted']['scratch_peak_bytes']['value'] == 3


def test_overlapping_or_repeated_completion_cannot_double_count_a_window():
    work = WorkConsumption(sampler=samples((0, 0, 1), (2, 3, 4), (5, 6, 7), (8, 9, 10)))
    call = work.begin()
    with pytest.raises(ConsumptionError):
        work.begin()
    first = call.finish()
    with pytest.raises(ConsumptionError):
        call.finish()
    with pytest.raises(ConsumptionError):
        call.account_bytes('memory', 1)
    second = work.begin().finish()
    assert first['invocations_recorded'] == 1 and second['invocations_recorded'] == 2
    assert second['cumulative']['measured']['cpu_ns']['value'] == 5


@pytest.mark.parametrize('state,code', [('invalid', 3), ('pending', 5), ('clean', 0)])
def test_metrics_preserve_real_project_outcomes_and_source_bytes(tmp_path, state, code):
    if state == 'invalid':
        put(tmp_path, 'specroad.json', b'{')
    else:
        configuration_file(tmp_path)
        if state == 'pending':
            put(tmp_path, '.specroad/transactions/pending/journal.json', b'Uninspected pending journal')
    before = inventory(tmp_path)
    result = measured(tmp_path, **{'--project': str(tmp_path)})
    assert result.exit_code == code
    assert result.details['runtime']['invocations_recorded'] == 1
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('metric', ['cpu_ns', 'wall_ns', 'rss_peak_bytes'])
def test_unknown_sample_does_not_become_zero_in_cumulative_measurement(metric):
    first = {'cpu_ns': 0, 'wall_ns': 0, 'rss_peak_bytes': 1}
    second = {'cpu_ns': 10, 'wall_ns': 20, 'rss_peak_bytes': 30, metric: None}
    sequence = iter([CounterSample(**first), CounterSample(**second),
                     CounterSample(40, 50, 60), CounterSample(70, 80, 90)])
    work = WorkConsumption(sampler=lambda: next(sequence))
    one = work.begin().finish(); two = work.begin().finish()
    assert one['invocation']['measured'][metric]['value'] is None
    assert two['cumulative']['measured'][metric]['value'] is None
    assert two['cumulative']['measured'][metric]['measurement_kind'] == 'unknown'


def test_failed_optional_sampler_preserves_command_result_and_reports_unknown(tmp_path):
    def unavailable():
        raise OSError('Observer unavailable')
    work = WorkConsumption(sampler=unavailable)
    document = measured(tmp_path, work).as_dict()
    assert document['status'] == 'success'
    assert all(m['value'] is None and m['measurement_kind'] == 'unknown'
               for m in document['summary']['runtime']['invocation']['measured'].values())


def test_explicit_window_can_wrap_real_srx_without_changing_semantic_inputs_or_output():
    document = roots(); original = deepcopy(document)
    program = SrxProgram(expression_document(literal(True)), rule_id='measured')
    context = EvaluationContext(document, rule_id='measured')
    baseline = evaluate_with_usage(program, context)
    work = WorkConsumption()
    for profile in ('constrained', 'standard'):
        call = work.begin({'--resource-profile': profile})
        result = evaluate_with_usage(program, context)
        report = call.finish()
        assert result.value == baseline.value and result.usage.data == baseline.usage.data
        assert report['profile'] == profile
    assert document == original and context.data == original


def test_reports_and_input_options_do_not_mutate_the_ledger_or_previous_result():
    options = {'--cpu-budget-ms': 1}
    work = WorkConsumption(sampler=samples((0, 0, 1), (1, 2, 3), (4, 5, 6), (7, 8, 9)))
    call = work.begin(options); options['--cpu-budget-ms'] = 99
    first = call.finish(); first['cumulative']['measured']['cpu_ns']['value'] = -100
    assert first['effective_budgets']['cpu']['value'] == 1
    second = work.begin().finish()
    assert second['cumulative']['measured']['cpu_ns']['value'] == 4


def test_native_sample_uses_read_only_in_process_sources_without_external_monitor():
    with patch('subprocess.Popen', side_effect=AssertionError('External monitor')):
        first = native_sample(); second = native_sample()
    assert first.cpu_source == second.cpu_source == 'time.process_time_ns'
    assert second.cpu_ns >= first.cpu_ns and second.wall_ns >= first.wall_ns
    if sys.platform.startswith('linux'):
        assert second.rss_peak_bytes >= first.rss_peak_bytes > 0


def test_linux_rss_bytes_are_bounded_by_native_kernel_peak_observations():
    if not sys.platform.startswith('linux'):
        assert native_sample().rss_peak_bytes is None
        return
    import resource
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    sampled = native_sample()
    after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    assert before <= sampled.rss_peak_bytes <= after
