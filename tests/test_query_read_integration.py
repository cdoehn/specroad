"""Six real project readers, retained phases and exact results without writes."""
from pathlib import Path
from unittest.mock import patch
import json

import pytest

from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.result_schemas import validate_result_document
from specroad.model.paths import artifact_path
from specroad.query import (NormalizedQuery, ReadCommandWork, diff_project,
                            impact_artifact, query_project, show_artifact,
                            trace_artifact, why_artifact)
from specroad.runtime.consumption import CounterSample, WorkConsumption
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.git_objects import GitFixture
from support.model import configuration_value, put
from support.portable import build_distribution
from support.processes import run_cli, run_python
from support.read_only import inventory, no_write_attempts
from support.relations import aid, edge
from support.srx import binary, expression_document, field, literal

COMMANDS = ('artifact.show', 'query', 'trace', 'why', 'impact', 'diff')


def project_pair(parent):
    """Actual same-project normative sources with one independently known delta."""
    configuration = configuration_value(resource_limits={
        'trace_depth': 3, 'query_default_limit': 1, 'query_result_count': 1})
    files = {'specroad.json': artifact_bytes(configuration)}
    requirement = domain_value('requirement', id=aid(), title='Requirement', owner='one',
        relations=[edge('addresses', aid('goal'))])
    goal = domain_value('goal', id=aid('goal'), title='Old goal', owner='two')
    for value in (requirement, goal):
        files[artifact_path(value['artifact_type'], value['id'], 'SR')] = artifact_bytes(value)
    before, current = parent / 'before', parent / 'current'
    for root in (before, current):
        root.mkdir()
        for path, raw in files.items():
            put(root, path, raw)
    put(current, artifact_path('goal', aid('goal'), 'SR'), artifact_bytes({**goal, 'title': 'New goal'}))
    return current, before, files


def inputs(command, before):
    if command == 'query':
        return {'query': NormalizedQuery(limit=100)}
    if command == 'diff':
        return {'against': str(before), 'against_kind': 'local'}
    return {'artifact_id': aid(), **({'direction': 'out', 'depth': 3} if command == 'trace' else {})}


def direct(command, root, before):
    handler = {'artifact.show': show_artifact, 'query': query_project, 'trace': trace_artifact,
               'why': why_artifact, 'impact': impact_artifact, 'diff': diff_project}[command]
    return handler(root, **inputs(command, before))


def request(command, root, before, **extra):
    options = {'--project': str(root), **extra}
    if command == 'query':
        options['--limit'] = '100'
    elif command == 'diff':
        options.update({'--against': str(before), '--against-kind': 'local'})
    elif command == 'trace':
        options.update({'--direction': 'out', '--depth': '3'})
    return {'command_id': command, 'arguments': {} if command in ('query', 'diff') else {'id': aid()},
            'options': options}


def arguments(command, root, before):
    value = request(command, root, before)
    result = ['artifact', 'show'] if command == 'artifact.show' else [command]
    result += list(value['arguments'].values())
    for key, item in value['options'].items():
        result += [key, item]
    return result + ['--format=json']


def ticking():
    value = 0
    def sample():
        nonlocal value
        value += 10_000_000
        return CounterSample(value, value, None, 'fixture:cpu', 'fixture:wall', 'unknown')
    return sample


@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('units', [1, 2, 100])
def test_all_retained_readers_equal_the_complete_direct_result(tmp_path, command, units):
    root, before, _ = project_pair(tmp_path)
    expected = direct(command, root, before)
    assert expected.exit_code == 0 and expected.complete
    protected = inventory(tmp_path)
    with ReadCommandWork(command, root, **inputs(command, before)) as work:
        with pytest.raises(ValueError):
            work.result
        while not work.advance(units):
            assert not work.state['finished'] and work.state['command_exit_code'] is None
            with pytest.raises(ValueError):
                work.result
        assert work.result.as_dict() == expected.as_dict()
        assert work.state['units_completed'] == 3
        assert work.advance(1) and work.state['units_completed'] == 3
        assert not work.state['durable_checkpoint'] and not work.state['project_write_authorized']
    assert inventory(tmp_path) == protected


@pytest.mark.parametrize('command', COMMANDS)
def test_new_tiny_windows_retain_all_three_phases_and_full_scope(tmp_path, command):
    root, before, _ = project_pair(tmp_path)
    expected = direct(command, root, before).as_dict()
    ledger = WorkConsumption(sampler=ticking())
    with ReadCommandWork(command, root, **inputs(command, before)) as work:
        for index, phase in enumerate(('loaded', 'evaluated', 'finished'), 1):
            call = ledger.begin({'--step-cpu-ms': 1, '--step-wall-ms': 1})
            try:
                finished = work.advance(100, call=call)
            finally:
                report = call.finish()
            assert finished == (index == 3)
            assert work.state['phase'] == phase and work.state['units_completed'] == index
            assert report['soft_budget_exceeded']
            assert report['invocation']['controls']['phases']['work_unit'] == {'start': 1, 'end': 1}
        assert work.result.as_dict() == expected


@pytest.mark.parametrize('command', COMMANDS)
def test_every_public_reader_works_in_a_read_only_project_without_attempted_writes(tmp_path, command):
    root, before, _ = project_pair(tmp_path)
    protected_paths = [*root.rglob('*'), root, *before.rglob('*'), before]
    modes = {p: p.stat().st_mode & 0o777 for p in protected_paths}
    try:
        for path in protected_paths:
            path.chmod(0o555 if path.is_dir() else 0o444)
        protected = inventory(tmp_path)
        with no_write_attempts(), patch('builtins.input', side_effect=AssertionError('stdin')), \
                patch('secrets.token_bytes', side_effect=AssertionError('entropy')), \
                patch('specroad.changes.locking.LockFiles.acquire', side_effect=AssertionError('lock')):
            expected = direct(command, root, before)
            actual = execute_request(request(command, root, before), cwd=tmp_path).result
        assert expected.exit_code == actual.exit_code == 0 and actual.complete
        assert actual.as_dict()['result'] == expected.as_dict()['result']
        assert inventory(tmp_path) == protected
    finally:
        for path in sorted(modes, key=lambda p: len(p.parts)):
            path.chmod(modes[path])


@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('metrics', [False, True])
def test_cli_small_targets_do_not_truncate_or_change_the_payload(tmp_path, command, metrics):
    root, before, _ = project_pair(tmp_path)
    expected = direct(command, root, before)
    options = {'--step-wall-ms': '1', '--resource-profile': 'constrained'}
    if metrics:
        options['--metrics'] = True
    actual = execute_request(request(command, root, before, **options), cwd=tmp_path,
                             consumption=WorkConsumption(sampler=ticking())).result
    assert actual.exit_code == expected.exit_code == 0 and actual.complete
    assert actual.as_dict()['result'] == expected.as_dict()['result']
    if metrics:
        runtime = actual.as_dict()['summary']['runtime']
        assert runtime['soft_budget_exceeded']
        assert runtime['invocation']['controls']['phases']['work_unit'] == {'start': 3, 'end': 3}
        assert runtime['includes_result_delivery'] is False
    else:
        assert 'runtime' not in actual.details


@pytest.mark.parametrize('command', COMMANDS)
def test_invalid_resource_target_fails_before_project_access(tmp_path, command):
    value = request(command, tmp_path / 'absent', tmp_path / 'absent-base', **{'--step-wall-ms': '0'})
    with patch('specroad.cli.invocation_context.InvocationContextBuilder.prepare',
               side_effect=AssertionError('project access')), no_write_attempts():
        result = execute_request(value).result
    assert result.exit_code == 2 and result.result is None


@pytest.mark.parametrize('command', COMMANDS)
def test_late_artifact_change_cannot_publish_the_old_success(tmp_path, command):
    root, before, _ = project_pair(tmp_path)
    with ReadCommandWork(command, root, **inputs(command, before)) as work:
        assert not work.advance(2)
        path = root / artifact_path('goal', aid('goal'), 'SR')
        value = json.loads(path.read_bytes()); value['title'] = 'Changed after evaluation'
        path.write_bytes(artifact_bytes(value))
        assert work.advance()
        assert work.result.exit_code == 6 and not work.result.complete and work.result.result is None


def test_query_cli_filters_use_complete_inventory_and_explicit_pagination(tmp_path):
    root, _, _ = project_pair(tmp_path)
    result = dispatch_result(['query', '--project', str(root)]).as_dict()['result']
    assert result['total'] == 2 and result['returned'] == result['limit'] == 1 and result['truncated']
    result = dispatch_result(['query', '--project', str(root), '--type', 'goal', '--type', 'requirement',
        '--owner', 'one', '--owner', 'two', '--sort', 'title:desc', '--select', '/title', '--select', '/owner',
        '--offset', '1', '--limit', '100'])
    assert result.exit_code == 0
    assert result.as_dict()['result'] == {'items': [{'id': aid('goal'), 'artifact_type': 'goal',
        'values': {'/title': 'New goal', '/owner': 'two'}}], 'total': 2, 'offset': 1,
        'limit': 100, 'returned': 1, 'truncated': False}
    validate_result_document('artifact-query-v1', result.as_dict()['result'])


def test_query_reads_repeated_srx_files_relative_to_explicit_cwd_and_ands_them(tmp_path):
    root, _, _ = project_pair(tmp_path)
    for name, node in [('a.json', binary('eq', field('/owner'), literal('one'))),
                       ('b.json', binary('eq', field('/artifact_type'), literal('requirement')))]:
        (tmp_path / name).write_bytes(artifact_bytes(expression_document(node)))
    protected = inventory(tmp_path)
    result = execute_request({'command_id': 'query', 'options': {'--project': str(root),
        '--filter': ['a.json', 'b.json'], '--limit': '100'}}, cwd=tmp_path).result
    assert result.exit_code == 0
    assert [v['id'] for v in result.as_dict()['result']['items']] == [aid()]
    assert result.as_dict()['result']['total'] == 1 and inventory(tmp_path) == protected


def test_query_rechecks_explicit_srx_bytes_before_publishing(tmp_path):
    root, _, _ = project_pair(tmp_path)
    path = tmp_path / 'filter.json'; path.write_bytes(artifact_bytes(expression_document(literal(True))))
    with ReadCommandWork('query', root, options={'--filter': ['filter.json']}, cwd=tmp_path) as work:
        assert not work.advance(2)
        path.write_bytes(artifact_bytes(expression_document(literal(False))))
        assert work.advance() and work.result.exit_code == 6 and work.result.result is None


@pytest.mark.parametrize('document', [expression_document(literal(1)), {'language': 'python', 'expression': 'True'}])
def test_query_rejects_invalid_or_nonboolean_srx_without_partial_page(tmp_path, document):
    root, _, _ = project_pair(tmp_path)
    path = tmp_path / 'filter.json'; path.write_bytes(artifact_bytes(document))
    result = dispatch_result(['query', '--project', str(root), '--filter', str(path)])
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert any(d.code == 'SRV110' for d in result.diagnostics)


@pytest.mark.parametrize('options', [['--verification-result', 'passed'], ['--release', 'v1'], ['--evaluation', 'absent.json']])
def test_query_does_not_infer_unavailable_provider_facts(tmp_path, options):
    root, _, _ = project_pair(tmp_path)
    result = dispatch_result(['query', '--project', str(root), *options])
    assert result.exit_code == 3 and not result.complete and result.result is None


def test_query_does_not_skip_invalid_unselected_sources(tmp_path):
    root, _, _ = project_pair(tmp_path)
    put(root, artifact_path('goal', aid('goal'), 'SR'), b'{')
    result = dispatch_result(['query', '--project', str(root), '--type', 'requirement'])
    assert result.exit_code == 3 and result.result is None


def test_diff_git_reads_the_pinned_base_and_keeps_worktree_and_index(tmp_path):
    current, before, files = project_pair(tmp_path)
    fixture = GitFixture(tmp_path / 'git-project'); commit = fixture.commit(files)
    for path in files:
        put(fixture.root, path, (current / path).read_bytes())
    protected = inventory(fixture.root)
    result = diff_project(fixture.root, commit)
    expected = diff_project(current, str(before), against_kind='local')
    assert result.exit_code == expected.exit_code == 0 and result.complete
    assert result.as_dict()['result'] == expected.as_dict()['result']
    assert result.details['base_commit'] == commit and result.result['changed']
    assert inventory(fixture.root) == protected
    validate_result_document('artifact-diff-v1', result.as_dict()['result'])
    missing = diff_project(fixture.root, 'refs/heads/missing')
    assert missing.exit_code == 3 and not missing.complete and missing.result is None
    assert inventory(fixture.root) == protected


def test_diff_explicit_relative_local_base_uses_request_cwd(tmp_path):
    root, before, _ = project_pair(tmp_path)
    actual = execute_request({'command_id': 'diff', 'options': {'--project': str(root),
        '--against': 'before', '--against-kind': 'local'}}, cwd=tmp_path).result
    assert actual.exit_code == 0
    assert actual.as_dict()['result'] == diff_project(root, str(before), against_kind='local').as_dict()['result']


@pytest.mark.parametrize('change', ['project', 'opaque'])
def test_diff_never_approves_foreign_projects_or_uninterpreted_resource_deltas(tmp_path, change):
    root, before, _ = project_pair(tmp_path)
    if change == 'project':
        path = root / 'specroad.json'; value = json.loads(path.read_bytes())
        value['project_id'] = 'different'; path.write_bytes(artifact_bytes(value))
    else:
        put(root, 'profiles/opaque.json', b'{}')
    result = diff_project(root, str(before), against_kind='local')
    assert result.exit_code == 3 and not result.complete and result.result is None


@pytest.fixture(scope='module')
def distribution(tmp_path_factory):
    target = tmp_path_factory.mktemp('read-command-distribution') / 'portable'
    build_distribution(target)
    return target / 'specroad.pyz'


@pytest.mark.parametrize('command', COMMANDS)
def test_module_and_portable_processes_match_the_public_reader(tmp_path, distribution, command):
    root, before, _ = project_pair(tmp_path)
    argv = arguments(command, root, before)
    expected = direct(command, root, before)
    protected = inventory(tmp_path)
    for process in (run_cli(argv, root, capture=True),
                    run_python(['-I', '-S', '-B', str(distribution), *argv], root, capture=True)):
        assert process.returncode == expected.exit_code == 0
        document = json.loads(process.stdout)
        assert document['command'] == command and document['result'] == expected.as_dict()['result']
    assert inventory(tmp_path) == protected
