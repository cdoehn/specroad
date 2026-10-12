"""Complete shortest origin paths and the public read-only project boundary."""
import importlib
from copy import deepcopy
from unittest.mock import patch
import json

import pytest

from specroad.changes import project_lock
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.model.paths import artifact_path
from specroad.model.schema_catalog import SchemaCatalog
from specroad.query import why_artifact
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.model import configuration_file, put
from support.portable import build_distribution
from support.processes import run_cli, run_python
from support.project_locks import options
from support.read_only import inventory, make_project, no_write_attempts
from support.relations import aid, artifact, edge, rid

why_module = importlib.import_module('specroad.query.why')


def value(kind, number, relations=()):
    if kind == 'source':
        return artifact(kind, number, relations, source_kind='document', locator='owned:source',
                        captured_at='2026-01-01T00:00:00Z')
    return domain_value(kind, id=aid(kind, number), relations=list(relations))


def relation(kind, target_kind, target_number, number):
    return edge(kind, aid(target_kind, target_number), number=number)


def diamond():
    return [
        value('requirement', 1, [relation('derived_from', 'need', 1, 1),
            relation('derived_from', 'need', 2, 2), relation('refines', 'requirement', 2, 3)]),
        value('requirement', 2, [relation('addresses', 'goal', 1, 4), relation('refines', 'requirement', 3, 11)]),
        value('requirement', 3, [relation('addresses', 'goal', 1, 12)]),
        value('need', 1, [relation('addresses', 'goal', 1, 5), relation('derived_from', 'source', 1, 7),
                          relation('refines', 'need', 2, 10)]),
        value('need', 2, [relation('addresses', 'goal', 1, 6), relation('derived_from', 'source', 1, 8)]),
        value('goal', 1, [relation('derived_from', 'source', 2, 9)]),
        value('goal', 2), value('source', 1), value('source', 2)]


def project(root, values=None, depth=3, **limits):
    root.mkdir()
    return make_project(root, *(diamond() if values is None else values),
                        resource_limits={'trace_depth': depth, **limits})


def signature(path):
    assert set(path) == {'artifacts', 'relations', 'inverse'}
    assert len(path['artifacts']) == len(path['relations']) + 1 == len(path['inverse']) + 1
    assert all(set(item) == {'id', 'id_scheme', 'artifact_type', 'id_prefix'}
               and item['id_scheme'] == 'random128-v1' and item['id_prefix'] == 'SR'
               for item in path['artifacts'])
    assert all(set(item) == {'relation_id', 'id_scheme'} and item['id_scheme'] == 'random128-v1'
               for item in path['relations'])
    return (tuple(item['id'] for item in path['artifacts']),
            tuple(item['relation_id'] for item in path['relations']), tuple(path['inverse']))


def expected_route(nodes, relations, inverse=None):
    return (tuple(aid(kind, n) for kind, n in nodes), tuple(rid(n) for n in relations),
            tuple(False for _ in relations) if inverse is None else tuple(inverse))


def expected_diamond(depth):
    r, a, b, c, g, s, t = (('requirement', 1), ('need', 1), ('need', 2),
                          ('requirement', 2), ('goal', 1), ('source', 1), ('source', 2))
    routes = [([r, a], [1]), ([r, b], [2]), ([r, a, g], [1, 5]),
              ([r, b, g], [2, 6]), ([r, c, g], [3, 4]),
              ([r, a, s], [1, 7]), ([r, b, s], [2, 8]),
              ([r, a, g, t], [1, 5, 9]), ([r, b, g, t], [2, 6, 9]),
              ([r, c, g, t], [3, 4, 9])]
    return {expected_route(nodes, edges) for nodes, edges in routes if len(edges) <= depth}


@pytest.mark.parametrize('depth', [0, 1, 2, 3, 20])
def test_every_shortest_path_per_origin_is_returned_with_exact_depth(tmp_path, depth):
    root = project(tmp_path / 'project', depth=depth)
    result = why_artifact(root, aid()); assert result.exit_code == 0 and result.complete
    data = result.as_dict()['result']; expected = expected_diamond(depth)
    assert {signature(path) for path in data['paths']} == expected
    assert data['path_count'] == len(data['paths']) == len(expected)
    assert data['start'] == aid() and data['depth'] == depth
    targets = []
    for kind, number in [('goal', 1), ('need', 1), ('need', 2), ('source', 1), ('source', 2)]:
        paths = [p for p in expected if p[0][-1] == aid(kind, number)]
        if paths:
            targets.append({'id': aid(kind, number), 'artifact_type': kind,
                            'distance': len(paths[0][1]), 'path_count': len(paths)})
    assert data['targets'] == targets
    assert data['coverage']['source_count'] == 9 and data['coverage']['relation_count'] == 12
    assert data['coverage']['atomic_snapshot'] is False
    assert result.as_dict()['summary']['full_semantic_validation'] is False


def test_equal_length_distinct_relation_identities_are_distinct_paths(tmp_path):
    values = [value('requirement', 1, [relation('derived_from', 'need', 1, 1),
                                      relation('refines', 'need', 1, 2)]),
              value('need', 1, [relation('addresses', 'goal', 1, 3)]), value('goal', 1)]
    root = project(tmp_path / 'project', values)
    data = why_artifact(root, aid()).as_dict()['result']
    r, n, g = ('requirement', 1), ('need', 1), ('goal', 1)
    assert {signature(p) for p in data['paths']} == {
        expected_route([r, n], [1]), expected_route([r, n], [2]),
        expected_route([r, n, g], [1, 3]), expected_route([r, n, g], [2, 3])}
    assert data['path_count'] == 4


@pytest.mark.parametrize('kind', ['goal', 'need', 'source'])
def test_origin_start_includes_its_one_zero_edge_shortest_path(tmp_path, kind):
    root = project(tmp_path / 'project', [value(kind, 1)], depth=0)
    result = why_artifact(root, aid(kind)); assert result.exit_code == 0
    data = result.as_dict()['result']
    assert [signature(p) for p in data['paths']] == [expected_route([(kind, 1)], [])]
    assert data['targets'] == [{'id': aid(kind), 'artifact_type': kind, 'distance': 0, 'path_count': 1}]


def test_directed_incoming_edges_do_not_invent_an_origin_route(tmp_path):
    values = [value('source', 1, [relation('references', 'requirement', 1, 1)]), value('requirement', 1)]
    root = project(tmp_path / 'project', values)
    result = why_artifact(root, aid()); assert result.exit_code == 0
    assert result.as_dict()['result']['paths'] == [] and result.as_dict()['result']['targets'] == []


def test_symmetric_inverse_preserves_stored_relation_identity_and_orientation(tmp_path):
    values = [value('goal', 1, [relation('conflicts_with', 'requirement', 1, 1)]), value('requirement', 1)]
    assert values[0]['id'] < values[1]['id']
    root = project(tmp_path / 'project', values)
    result = why_artifact(root, aid()); assert result.exit_code == 0
    assert [signature(p) for p in result.as_dict()['result']['paths']] == [
        expected_route([('requirement', 1), ('goal', 1)], [1], [True])]


def test_nonhierarchy_cycles_terminate_without_longer_or_repeated_paths(tmp_path):
    values = [value('requirement', 1, [relation('depends_on', 'requirement', 2, 1)]),
              value('requirement', 2, [relation('depends_on', 'requirement', 1, 2),
                                      relation('addresses', 'goal', 1, 3)]), value('goal', 1)]
    root = project(tmp_path / 'project', values, depth=1000)
    result = why_artifact(root, aid()); assert result.exit_code == 0
    assert [signature(p) for p in result.as_dict()['result']['paths']] == [
        expected_route([('requirement', 1), ('requirement', 2), ('goal', 1)], [1, 3])]


def test_relation_array_and_file_creation_order_do_not_change_path_order(tmp_path):
    first = diamond(); second = deepcopy(first)
    for v in second:
        v['relations'].reverse()
    a = why_artifact(project(tmp_path / 'first', first), aid())
    b = why_artifact(project(tmp_path / 'second', list(reversed(second))), aid())
    assert a.exit_code == b.exit_code == 0
    for field in ('targets', 'paths', 'path_count'):
        assert a.as_dict()['result'][field] == b.as_dict()['result'][field]


def test_soft_count_targets_do_not_cap_the_complete_path_set(tmp_path):
    values = [value('requirement', 1, [relation('derived_from', 'need', n, n) for n in range(1, 33)]),
              *[value('need', n, [relation('addresses', 'goal', 1, 100 + n)]) for n in range(1, 33)],
              value('goal', 1)]
    root = project(tmp_path / 'project', values, depth=2, model_bytes=1,
                   relation_count=1, query_result_count=1)
    result = why_artifact(root, aid()); assert result.exit_code == 0
    data = result.as_dict()['result']; assert data['path_count'] == 64
    expected = {expected_route([('requirement', 1), ('need', n)], [n]) for n in range(1, 33)}
    expected |= {expected_route([('requirement', 1), ('need', n), ('goal', 1)], [n, 100+n])
                 for n in range(1, 33)}
    assert {signature(p) for p in data['paths']} == expected
    assert data['targets'][0]['path_count'] == 32


def test_missing_configured_depth_is_an_explicit_model_error_before_graph_loading(tmp_path):
    root = project(tmp_path / 'project'); configuration_file(root)
    with patch.object(why_module, 'build_project_relation_index', side_effect=AssertionError('graph load')):
        result = why_artifact(root, aid())
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert any(d.rationale == 'why_depth_not_configured' for d in result.diagnostics)


@pytest.mark.parametrize('depth', [-1, True, 1.5, '3'])
def test_invalid_configured_depth_never_becomes_an_empty_success(tmp_path, depth):
    root = project(tmp_path / 'project', depth=depth)
    result = why_artifact(root, aid())
    assert result.exit_code == 3 and not result.complete and result.result is None


@pytest.mark.parametrize('depth', [0, 3])
def test_unknown_start_is_an_error_even_with_zero_depth(tmp_path, depth):
    root = project(tmp_path / 'project', depth=depth)
    result = why_artifact(root, aid(number=99))
    assert result.exit_code == 3 and result.result is None and not result.complete


@pytest.mark.parametrize('broken', ['missing_target', 'malformed', 'hierarchy_cycle'])
def test_invalid_unreachable_sources_block_a_complete_answer(tmp_path, broken):
    values = diamond()
    if broken == 'missing_target':
        values.append(value('requirement', 8, [relation('depends_on', 'requirement', 99, 99)]))
    elif broken == 'hierarchy_cycle':
        values.extend([value('requirement', 8, [relation('refines', 'requirement', 9, 98)]),
                       value('requirement', 9, [relation('refines', 'requirement', 8, 99)])])
    root = project(tmp_path / 'project', values, depth=0)
    if broken == 'malformed':
        put(root, artifact_path('requirement', aid(number=8), 'SR'), b'{broken')
    before = inventory(root); result = why_artifact(root, aid())
    assert result.exit_code == 3 and not result.complete and result.result is None
    assert inventory(root) == before


@pytest.mark.parametrize('change', ['unreached_source', 'configuration'])
def test_changes_during_path_materialization_block_final_success(tmp_path, change):
    root = project(tmp_path / 'project'); original = why_module._why_paths
    def alter(*args):
        rows = original(*args)
        if change == 'configuration':
            configuration_file(root, resource_limits={'trace_depth': 2})
        else:
            changed = value('goal', 2); changed['title'] = 'Changed unreachable input'
            put(root, artifact_path('goal', aid('goal', 2), 'SR'), artifact_bytes(changed))
        return rows
    with patch.object(why_module, '_why_paths', side_effect=alter):
        result = why_artifact(root, aid())
    assert result.exit_code == 6 and not result.complete and result.result is None


def test_active_writer_and_unresolved_journal_block_before_graph_loading(tmp_path):
    root = project(tmp_path / 'project'); (root / '.specroad/locks').mkdir(parents=True)
    with project_lock(root, **options()), patch.object(why_module, 'build_project_relation_index',
                                                       side_effect=AssertionError('graph load')):
        before = inventory(root); result = why_artifact(root, aid())
        assert result.exit_code == 5 and result.result is None and inventory(root) == before
    put(root, '.specroad/transactions/pending.json', b'incomplete')
    before = inventory(root)
    with patch.object(why_module, 'build_project_relation_index', side_effect=AssertionError('graph load')):
        result = why_artifact(root, aid())
    assert result.exit_code == 5 and result.result is None and inventory(root) == before


def test_direct_cli_request_and_process_return_the_same_machine_paths(tmp_path):
    root = project(tmp_path / 'project')
    args = ['why', aid(), '--project', str(root), '--format=json']
    direct = why_artifact(root, aid()); cli = dispatch_result(args)
    structured = execute_request({'command_id': 'why', 'arguments': {'id': aid()},
                                   'options': {'--project': str(root)}}).result
    process = run_cli(args, root, capture=True)
    assert direct.exit_code == cli.exit_code == structured.exit_code == process.returncode == 0
    expected = direct.as_dict()['result']
    assert cli.as_dict()['result'] == structured.as_dict()['result'] == json.loads(process.stdout)['result'] == expected


def test_portable_zipapp_returns_all_the_same_paths(tmp_path):
    root = project(tmp_path / 'project'); build_distribution(tmp_path / 'distribution')
    process = run_python(['-I', '-S', '-B', str(tmp_path / 'distribution/specroad.pyz'),
                         'why', aid(), '--project', str(root), '--format=json'], root, capture=True)
    assert process.returncode == 0
    assert json.loads(process.stdout)['result'] == why_artifact(root, aid()).as_dict()['result']


def test_public_why_attempts_no_project_writes_processes_entropy_stdin_or_writer_lock(tmp_path):
    root = project(tmp_path / 'project'); before = inventory(root)
    with no_write_attempts(), patch('builtins.input', side_effect=AssertionError('stdin')), \
            patch('secrets.token_bytes', side_effect=AssertionError('entropy')), \
            patch('specroad.changes.locking.LockFiles.acquire', side_effect=AssertionError('lock')):
        direct = why_artifact(root, aid())
        cli = dispatch_result(['why', aid(), '--project', str(root)])
    assert direct.exit_code == cli.exit_code == 0
    assert inventory(root) == before and not (root / '.specroad').exists()


def test_result_mutations_do_not_change_sources_or_subsequent_paths(tmp_path):
    root = project(tmp_path / 'project'); before = inventory(root)
    result = why_artifact(root, aid()); expected = result.as_dict()['result']
    changed = result.as_dict()['result']; changed['targets'].clear(); changed['paths'][0]['artifacts'][0]['id'] = 'changed'
    assert result.as_dict()['result'] == expected == why_artifact(root, aid()).as_dict()['result']
    assert inventory(root) == before


def test_public_command_schema_declares_actual_read_only_synchronous_behavior(tmp_path):
    registry = builtin_registry(); command = registry.resolve('why')
    assert command.command_class.value == 'read_only' and command.preflight_profile.value == 'project_read'
    assert command.effect_scope.value == 'none' and command.requires_project
    description = dispatch_result(['command', 'describe', 'why']).as_dict()['result']
    assert description['stdout']['result_schema'] == 'artifact-why-v1'
    assert description['work']['continuation_supported'] is False
    root = project(tmp_path / 'project'); data = why_artifact(root, aid()).as_dict()['result']
    schema = SchemaCatalog(registry).show('artifact-why-v1')['schema']
    assert set(schema['required']) == set(data) and schema['additionalProperties'] is False
    assert dispatch_result(['why', '--project', str(root)]).exit_code == 2
    assert dispatch_result(['why', aid(), '--depth=1', '--project', str(root)]).exit_code == 2
