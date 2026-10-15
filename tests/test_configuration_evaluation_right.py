"""Independent shortest-path oracles, deterministic failures and reader boundaries."""
from itertools import permutations
import json

import pytest

from specroad.cli.application import execute_request
from specroad.configurations import evaluate_configuration
from specroad.configurations.evaluation import ConfigurationEvaluationError
from specroad.configurations.project_evaluation import evaluate_project_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.query.read_work import ReadCommandWork
from support.artifacts import artifact_bytes
from support.closure import source, subject
from support.model import put
from support.portable import build_distribution
from support.processes import run_python
from support.read_only import inventory, make_project, no_write_attempts
from support.records import record_value
from support.relations import aid, artifact, edge, rid
from support.srx import binary, expression_document, field, literal


def configuration(number=1, **changes):
    return record_value('configuration', id=aid('configuration', number), name='Variant ' + str(number), **changes)


def condition(platform='windows'):
    return expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal(platform)))


def evaluate(values):
    return evaluate_configuration(tuple(SourceRelations(artifact_bytes(value)) for value in values),
                                  aid('configuration')).data


def route(row):
    return (tuple(a['id'] for a in row['path']['artifacts']),
            tuple(r['relation_id'] for r in row['path']['relations']))


def graph():
    return [configuration(), artifact(relations=[edge('depends_on', aid(number=2), number=6),
                                                edge('depends_on', aid(number=3), number=1)]),
            artifact(number=2, relations=[edge('depends_on', aid(number=4), number=5)]),
            artifact(number=3, relations=[edge('depends_on', aid(number=4), number=2)]),
            artifact(number=4, applicability=condition())]


def project(root, values=None, **options):
    root.mkdir()
    return make_project(root, *(graph() if values is None else values), **options)


def test_tied_paths_choose_complete_artifact_identity_order_before_relation_ids():
    result = evaluate(graph())
    row = result['inconsistent_dependencies'][0]
    assert route(row) == ((aid(), aid(number=2), aid(number=4)), (rid(6), rid(5)))
    assert row['distance'] == 2


def test_parallel_required_edges_use_the_smallest_relation_identity_for_the_same_node_path():
    values = [configuration(), artifact(relations=[edge('depends_on', aid(number=2), number=2),
        edge('supersedes', aid(number=2), number=1)]), artifact(number=2, applicability=condition())]
    for reversed_edges in (False, True):
        if reversed_edges:
            values[1]['relations'].reverse()
        row = evaluate(values)['inconsistent_dependencies'][0]
        assert route(row) == ((aid(), aid(number=2)), (rid(),))


def test_source_and_edge_permutations_preserve_the_entire_evaluation():
    values = graph(); expected = evaluate(values)
    for order in permutations(values[:3]):
        changed = json.loads(json.dumps([*order, *values[3:]]))
        for value in changed:
            value['relations'].reverse()
        # Relation-array ordering changes the configuration hash only when the
        # configuration record itself changes; this fixture has no CFG edges.
        assert evaluate(changed) == expected


def test_exhaustive_three_node_graphs_match_an_independent_simple_path_oracle():
    pairs = [(a, b) for a in range(3) for b in range(3) if a != b]
    for edge_mask in range(1 << len(pairs)):
        edges = [(a, b, n + 1) for n, (a, b) in enumerate(pairs) if edge_mask & (1 << n)]
        for applicability_mask in range(8):
            active = {n for n in range(3) if applicability_mask & (1 << n)}
            values = [artifact(number=n + 1, relations=[edge('depends_on', aid(number=b + 1), number=r)
                      for a, b, r in edges if a == n],
                      applicability=condition('linux' if n in active else 'windows')) for n in range(3)]
            expected = []
            for start in sorted(active):
                by_target = {}
                def walk(nodes, relations):
                    current = nodes[-1]
                    if current not in active:
                        by_target.setdefault(current, []).append((tuple(nodes), tuple(relations)))
                        return
                    for a, b, number in edges:
                        if a == current and b not in nodes:
                            walk(nodes + [b], relations + [number])
                walk([start], [])
                for target in sorted(by_target):
                    nodes, relations = min(by_target[target], key=lambda value: (len(value[1]), value))
                    expected.append((aid(number=start + 1), aid(number=target + 1), len(relations),
                        (tuple(aid(number=n + 1) for n in nodes), tuple(rid(n) for n in relations))))
            actual = evaluate([configuration(), *values])['inconsistent_dependencies']
            actual = [(row['source_id'], row['target_id'], row['distance'], route(row)) for row in actual]
            assert actual == expected, (edge_mask, applicability_mask)


PAIRS = [('addresses', 'requirement', 'goal'), ('refines', 'requirement', 'requirement'),
         ('derived_from', 'requirement', 'source'), ('depends_on', 'requirement', 'requirement'),
         ('constrains', 'requirement', 'component'), ('allocated_to', 'requirement', 'interface'),
         ('implemented_by', 'requirement', 'task'), ('verified_by', 'requirement', 'test'),
         ('produces', 'test', 'evidence'), ('mitigates', 'requirement', 'risk'),
         ('scheduled_for', 'requirement', 'release'), ('part_of', 'task', 'release'),
         ('supersedes', 'requirement', 'requirement'), ('contains', 'document', 'section'),
         ('references', 'source', 'requirement')]


@pytest.mark.parametrize('kind,source_type,target_type', PAIRS, ids=[p[0] for p in PAIRS])
def test_every_stored_strong_relation_yields_the_exact_configuration_path(kind, source_type, target_type):
    first = source(source_type, relations=[edge(kind, aid(target_type, 2))])
    extra = {'subjects': [subject(first['id'])]} if target_type == 'evidence' else {}
    last = source(target_type, 2, applicability=condition(), **extra)
    rows = evaluate([configuration(), first, last])['inconsistent_dependencies']
    assert len(rows) == 1
    assert route(rows[0]) == ((first['id'], last['id']), (rid(),))
    assert rows[0]['path']['inverse'] == [False]


def test_unrelated_excluded_component_has_no_invented_dependency():
    values = graph() + [artifact(number=9, applicability=condition())]
    assert aid(number=9) in evaluate(values)['excluded_artifact_ids']
    assert all(row['target_id'] != aid(number=9) for row in evaluate(values)['inconsistent_dependencies'])


def test_many_applicable_origins_and_targets_are_not_limited_by_query_pagination():
    targets = [artifact(number=n, applicability=condition()) for n in range(101, 112)]
    origins = [artifact(number=n, relations=[edge('depends_on', item['id'], number=n * 100 + i)
                                            for i, item in enumerate(targets)]) for n in range(1, 13)]
    result = evaluate([configuration(), *origins, *targets])
    assert len(result['inconsistent_dependencies']) == 12 * 11
    assert len({(r['source_id'], r['target_id']) for r in result['inconsistent_dependencies']}) == 132


def test_no_implicit_trace_depth_truncates_a_configuration_error_path(tmp_path):
    length = 32
    values = [configuration(), *(artifact(number=n, relations=[edge('depends_on', aid(number=n + 1), number=n)])
                                 for n in range(1, length)), artifact(number=length, applicability=condition())]
    root = project(tmp_path / 'project', values, resource_limits={'trace_depth': 0, 'query_default_limit': 1})
    result = evaluate_project_configuration(root, aid('configuration'))
    assert result.exit_code == 3 and result.complete
    rows = result.as_dict()['result']['inconsistent_dependencies']
    assert len(rows) == length - 1 and rows[0]['distance'] == length - 1
    assert len(rows[0]['path']['artifacts']) == length


@pytest.mark.parametrize('status', ['rejected', 'retired'])
def test_lifecycle_state_does_not_remove_applicable_required_origins(status):
    values = graph(); values[1]['maturity'] = status
    assert evaluate(values)['inconsistent_dependencies'][0]['source_id'] == aid()


def test_invalid_conditions_are_checked_in_identity_order_independent_of_input_order():
    values = [configuration(), artifact(applicability=expression_document(literal('invalid'))),
              artifact(number=2, applicability=expression_document(literal(None)))]
    errors = []
    for order in (values, values[::-1]):
        supplied = tuple(SourceRelations(artifact_bytes(value), path=value['id'] + '.json') for value in order)
        with pytest.raises(ConfigurationEvaluationError) as caught:
            evaluate_configuration(supplied, aid('configuration'))
        errors.append(caught.value.diagnostic())
    assert errors[0] == errors[1] and errors[0]['path'] == aid() + '.json'


@pytest.mark.parametrize('selected', [None, '', 'not-an-id', aid('goal')])
def test_absent_or_wrong_explicit_configuration_is_never_a_default(selected):
    supplied = (SourceRelations(artifact_bytes(configuration())),)
    with pytest.raises(ConfigurationEvaluationError):
        evaluate_configuration(supplied, selected)


@pytest.mark.parametrize('supplied', [None, {}, 'sources', iter(())])
def test_inventory_must_be_an_owned_sequence(supplied):
    with pytest.raises(ModelError) as caught:
        evaluate_configuration(supplied, aid('configuration'))
    assert caught.value.reason == 'configuration_inventory_required'


def test_duplicate_artifact_identity_cannot_hide_a_conflicting_variant():
    with pytest.raises(ConfigurationEvaluationError) as caught:
        evaluate([configuration(), artifact(), artifact(applicability=condition())])
    assert caught.value.reason == 'duplicate_configuration_inventory_id'


def test_parent_cycle_cannot_produce_a_partial_applicability_result():
    with pytest.raises(ConfigurationEvaluationError):
        evaluate([configuration(parent=aid('configuration', 2)), configuration(2, parent=aid('configuration'))])


def test_disallowed_selected_value_cannot_become_an_empty_scope():
    with pytest.raises(ConfigurationEvaluationError):
        evaluate([configuration(selection={'platform': 'unknown'}), artifact()])


@pytest.mark.parametrize('change', ['addition', 'removal', 'project_configuration'])
def test_final_currentness_check_rejects_changed_membership_or_project_configuration(tmp_path, change):
    root = project(tmp_path / 'project')
    with ReadCommandWork('configuration.evaluate', root, configuration_id=aid('configuration')) as work:
        assert not work.advance(2)
        if change == 'addition':
            value = artifact(number=20); put(root, artifact_path('requirement', value['id'], 'SR'), artifact_bytes(value))
        elif change == 'removal':
            (root / artifact_path('requirement', aid(number=4), 'SR')).unlink()
        else:
            path = root / 'specroad.json'; value = json.loads(path.read_text()); value['default_locale'] = 'en-US'
            path.write_bytes(artifact_bytes(value))
        assert work.advance(1)
        assert work.result.exit_code == 6 and work.result.result is None and not work.result.complete


def test_linked_configuration_source_is_rejected_without_following_or_writing(tmp_path):
    root = project(tmp_path / 'project')
    path = root / artifact_path('configuration', aid('configuration'), 'SR')
    outside = tmp_path / 'outside.json'; outside.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(outside)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = evaluate_project_configuration(root, aid('configuration'))
    assert result.exit_code == 7 and result.result is None
    assert inventory(tmp_path) == before


def test_invalid_live_applicability_preserves_location_and_srv130(tmp_path):
    value = artifact(applicability=expression_document(literal('invalid')))
    root = project(tmp_path / 'project', [configuration(), value])
    result = evaluate_project_configuration(root, aid('configuration'))
    assert result.exit_code == 3 and result.result is None
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == 'SRV130' and diagnostic.rationale == 'invalid_applicability'
    assert diagnostic.path == artifact_path('requirement', aid(), 'SR')
    assert diagnostic.location['pointer'].startswith('/applicability')


def test_soft_runtime_targets_do_not_truncate_the_completed_semantic_result(tmp_path):
    root = project(tmp_path / 'project')
    expected = evaluate_project_configuration(root, aid('configuration')).as_dict()['result']
    result = execute_request({'command_id': 'configuration.evaluate',
        'arguments': {'configuration_id': aid('configuration')},
        'options': {'--project': str(root), '--resource-profile': 'constrained',
                    '--cpu-budget-ms': '1', '--wall-budget-ms': '1', '--metrics': True}}).result
    assert result.exit_code == 3 and result.complete
    assert result.as_dict()['result'] == expected


def test_installed_pyz_executes_the_registered_configuration_command(tmp_path):
    root = project(tmp_path / 'project', [configuration(), artifact()])
    _, package = build_distribution(tmp_path / 'distribution')
    result = run_python(['-I', '-S', '-B', str(package), 'configuration', 'evaluate', aid('configuration'),
                         '--project', str(root), '--format=json'], cwd=tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope['command'] == 'configuration.evaluate' and envelope['result']['consistent']
    assert envelope['result']['applicable_artifact_ids'] == [aid('configuration'), aid()]
