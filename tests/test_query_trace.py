"""Public directed trace contracts, exact graph sets and read-only boundaries."""
import importlib
import json
from unittest.mock import patch

import pytest

from specroad.changes import project_lock
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.model.paths import artifact_path
from specroad.model.schema_catalog import SchemaCatalog
from specroad.query import trace_artifact
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.model import put
from support.portable import build_distribution
from support.processes import run_cli, run_python
from support.project_locks import options
from support.read_only import inventory, make_project, no_write_attempts
from support.relations import aid, edge, rid

trace_module = importlib.import_module('specroad.query.trace')


def requirement(number, **changes):
    return domain_value('requirement', id=aid(number=number), **changes)


def project(root, *values):
    root.mkdir()
    make_project(root, *values)
    return root


def chain(root, count=4):
    return project(root, *(requirement(n, relations=[edge('depends_on', aid(number=n + 1), number=n)]
                                       if n < count else []) for n in range(1, count + 1)))


@pytest.mark.parametrize('direction,depth,nodes,edges', [
    ('in', 0, [(2, 0)], []), ('out', 0, [(2, 0)], []), ('both', 0, [(2, 0)], []),
    ('in', 1, [(2, 0), (1, 1)], [(1, True)]),
    ('out', 1, [(2, 0), (3, 1)], [(2, False)]),
    ('both', 1, [(2, 0), (1, 1), (3, 1)], [(1, True), (2, False)]),
    ('in', 2, [(2, 0), (1, 1)], [(1, True)]),
    ('out', 2, [(2, 0), (3, 1), (4, 2)], [(2, False), (3, False)]),
    ('both', 2, [(2, 0), (1, 1), (3, 1), (4, 2)],
     [(1, False), (1, True), (2, False), (2, True), (3, False)])])
def test_direction_and_depth_determine_exact_nodes_and_traversed_views(tmp_path, direction, depth, nodes, edges):
    root = chain(tmp_path / 'project')
    result = trace_artifact(root, aid(number=2), direction=direction, depth=depth)
    assert result.exit_code == 0 and result.complete and result.command == 'trace'
    data = result.as_dict()['result']
    assert data['start'] == aid(number=2) and data['direction'] == direction and data['depth'] == depth
    assert data['nodes'] == [{'id': aid(number=n), 'artifact_type': 'requirement', 'distance': distance}
                             for n, distance in nodes]
    assert {(v['relation_id'], v['inverse']) for v in data['edges']} == {(rid(n), inverse) for n, inverse in edges}
    assert len(data['edges']) == len(edges)
    for view in data['edges']:
        n = next(n for n in (1, 2, 3) if rid(n) == view['relation_id'])
        assert view['stored_source'] == aid(number=n)
        assert view['stored_relation'] == edge('depends_on', aid(number=n + 1), number=n)
        assert (view['source'], view['target']) == (
            (aid(number=n + 1), aid(number=n)) if view['inverse'] else (aid(number=n), aid(number=n + 1)))
    assert data['coverage']['source_count'] == 4 and data['coverage']['relation_count'] == 3
    assert not data['coverage']['atomic_snapshot']
    assert not result.as_dict()['summary']['full_semantic_validation']


def test_explicit_depth_above_historical_default_is_not_silently_capped(tmp_path):
    root = chain(tmp_path / 'project', 14)
    result = trace_artifact(root, aid(number=1), direction='out', depth=12)
    assert result.exit_code == 0
    assert [(n['id'], n['distance']) for n in result.as_dict()['result']['nodes']] == [
        (aid(number=n), n - 1) for n in range(1, 14)]
    assert len(result.as_dict()['result']['edges']) == 12


def test_isolated_start_remains_a_known_node_and_unknown_start_is_an_error(tmp_path):
    root = project(tmp_path / 'project', requirement(1))
    known = trace_artifact(root, aid(number=1), direction='both', depth=99)
    assert known.exit_code == 0 and known.as_dict()['result']['edges'] == []
    assert known.as_dict()['result']['nodes'] == [{'id': aid(number=1), 'artifact_type': 'requirement', 'distance': 0}]
    for depth in (0, 1):
        missing = trace_artifact(root, aid(number=2), direction='out', depth=depth)
        assert missing.exit_code == 3 and not missing.complete and missing.result is None
        assert any(d.rationale == 'unknown_relation_view_artifact' for d in missing.diagnostics)


def test_inverse_supersedes_keeps_original_identity_and_data(tmp_path):
    relation = edge('supersedes', aid(number=1), extensions={'org.example': {'text': 'Cafe\u0301'}})
    root = project(tmp_path / 'project', requirement(1), requirement(2, relations=[relation]))
    result = trace_artifact(root, aid(number=1), direction='in', depth=1)
    assert result.exit_code == 0
    assert result.as_dict()['result']['edges'] == [{'relation_id': rid(), 'type': 'superseded_by',
        'source': aid(number=1), 'target': aid(number=2), 'inverse': True,
        'stored_source': aid(number=2), 'stored_relation': relation}]


def test_direct_cli_and_structured_invocation_agree_on_complete_machine_result(tmp_path):
    root = chain(tmp_path / 'project'); before = inventory(root)
    args = ['trace', aid(number=2), '--direction', 'both', '--depth', '2', '--project', str(root), '--format=json']
    direct = trace_artifact(root, aid(number=2), direction='both', depth=2)
    cli = dispatch_result(args)
    structured = execute_request({'command_id': 'trace', 'arguments': {'id': aid(number=2)},
        'options': {'--project': str(root), '--direction': 'both', '--depth': '2'}}).result
    process = run_cli(args, root, capture=True)
    for value in (direct, cli, structured):
        assert value.exit_code == 0 and value.command == 'trace'
        assert value.as_dict()['result'] == direct.as_dict()['result']
    assert process.returncode == 0 and json.loads(process.stdout)['result'] == direct.as_dict()['result']
    assert inventory(root) == before and not (root / '.git').exists()


def test_zipapp_and_module_return_the_same_trace(tmp_path):
    root = chain(tmp_path / 'project')
    build_distribution(tmp_path / 'distribution')
    args = ['trace', aid(number=2), '--direction=both', '--depth=2', '--project', str(root), '--format=json']
    process = run_python(['-I', '-S', '-B', str(tmp_path / 'distribution/specroad.pyz'), *args], root, capture=True)
    assert process.returncode == 0
    assert json.loads(process.stdout)['result'] == trace_artifact(root, aid(number=2), direction='both', depth=2).as_dict()['result']


@pytest.mark.parametrize('direction,depth', [('sideways', 1), (None, 1), ('out', -1),
                                           ('out', True), ('out', 1.5), ('out', '1')])
def test_invalid_direct_scope_fails_before_project_access(tmp_path, direction, depth):
    with patch.object(trace_module, 'ProjectSource', side_effect=AssertionError('project read')), no_write_attempts():
        result = trace_artifact(tmp_path / 'absent', aid(), direction=direction, depth=depth)
    assert result.exit_code == 2 and result.result is None and not result.complete


@pytest.mark.parametrize('depth', ['-1', '+1', '1.0', ' 1', '١', 'true'])
def test_non_decimal_cli_depth_is_usage_error_without_traversal(tmp_path, depth):
    root = chain(tmp_path / 'project')
    with patch.object(trace_module, 'build_project_relation_index', side_effect=AssertionError('traversal')):
        result = dispatch_result(['trace', aid(), '--direction', 'out', '--depth', depth, '--project', str(root)])
    assert result.exit_code == 2 and result.result is None


def test_missing_required_scope_and_unknown_direction_are_usage_errors(tmp_path):
    root = chain(tmp_path / 'project')
    for scope in ([], ['--depth', '1'], ['--direction', 'in'], ['--direction', 'wrong', '--depth', '1']):
        result = dispatch_result(['trace', aid(), *scope, '--project', str(root)])
        assert result.exit_code == 2 and result.result is None


def test_public_trace_does_not_attempt_writes_processes_entropy_stdin_or_lock_acquisition(tmp_path):
    root = chain(tmp_path / 'project'); before = inventory(root)
    with no_write_attempts(), patch('builtins.input', side_effect=AssertionError('stdin')), \
            patch('secrets.token_bytes', side_effect=AssertionError('entropy')), \
            patch('specroad.changes.locking.LockFiles.acquire', side_effect=AssertionError('lock')):
        direct = trace_artifact(root, aid(), direction='out', depth=3)
        cli = dispatch_result(['trace', aid(), '--direction', 'out', '--depth', '3', '--project', str(root)])
    assert direct.exit_code == cli.exit_code == 0
    assert inventory(root) == before and not (root / '.specroad').exists()


def test_writer_and_unresolved_journal_block_before_model_loading(tmp_path):
    root = chain(tmp_path / 'project'); (root / '.specroad/locks').mkdir(parents=True)
    with project_lock(root, **options()), patch.object(trace_module, 'build_project_relation_index',
                                                      side_effect=AssertionError('model read')):
        before = inventory(root)
        result = trace_artifact(root, aid(), direction='out', depth=2)
        assert result.exit_code == 5 and result.result is None and inventory(root) == before
    put(root, '.specroad/transactions/pending.json', b'not a complete journal')
    before = inventory(root)
    with patch.object(trace_module, 'build_project_relation_index', side_effect=AssertionError('model read')):
        result = trace_artifact(root, aid(), direction='out', depth=2)
    assert result.exit_code == 5 and result.result is None and inventory(root) == before


def test_invalid_unreached_source_prevents_a_false_complete_trace(tmp_path):
    root = chain(tmp_path / 'project')
    put(root, artifact_path('requirement', aid(number=9), 'SR'), b'{broken')
    before = inventory(root)
    result = trace_artifact(root, aid(), direction='out', depth=0)
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert inventory(root) == before


def test_changed_unreached_source_is_rejected_by_final_freshness_check(tmp_path):
    root = chain(tmp_path / 'project')
    original = trace_module._trace_rows
    def change_after_traversal(*args):
        rows = original(*args)
        put(root, artifact_path('requirement', aid(number=4), 'SR'), artifact_bytes(requirement(4, title='changed')))
        return rows
    with patch.object(trace_module, '_trace_rows', side_effect=change_after_traversal):
        result = trace_artifact(root, aid(), direction='out', depth=0)
    assert result.exit_code == 6 and not result.complete and result.result is None


def test_result_mutation_cannot_change_sources_or_later_trace(tmp_path):
    root = chain(tmp_path / 'project'); before = inventory(root)
    first = trace_artifact(root, aid(), direction='out', depth=2); expected = first.as_dict()['result']
    changed = first.as_dict()['result']; changed['nodes'].clear(); changed['edges'][0]['stored_relation']['target'] = aid()
    assert first.as_dict()['result'] == expected
    assert trace_artifact(root, aid(), direction='out', depth=2).as_dict()['result'] == expected
    assert inventory(root) == before


def test_registered_machine_protocol_exposes_actual_trace_without_resume_claim(tmp_path):
    registry = builtin_registry(); command = registry.resolve('trace')
    assert command.command_class.value == 'read_only' and command.preflight_profile.value == 'project_read'
    assert command.effect_scope.value == 'none' and command.requires_project
    description = dispatch_result(['command', 'describe', 'trace']).as_dict()['result']
    assert description['stdout']['result_schema'] == 'artifact-trace-v1'
    assert description['work']['continuation_supported'] is False
    root = chain(tmp_path / 'project'); payload = trace_artifact(root, aid(), direction='out', depth=2).as_dict()['result']
    catalog = SchemaCatalog(registry); schema = catalog.show('artifact-trace-v1')['schema']
    assert set(schema['required']) == set(payload) and schema['additionalProperties'] is False
