"""Resumed graph scope, exact cycle/path oracles and honest partial-work state."""
from collections import deque
from itertools import cycle
from unittest.mock import patch

import pytest

from specroad.cli.application import dispatch_result
from specroad.graph.indices import RelationIndex
from specroad.graph.references import RelationReferences
from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.query import TraceTraversal, trace_artifact
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.read_only import inventory, make_project, no_write_attempts
from support.relations import aid, edge, rid


def records(count, relations):
    values = {n: domain_value('requirement', id=aid(number=n), relations=[])
              for n in range(1, count + 1)}
    for source, target, number, kind in relations:
        values[source]['relations'].append(edge(kind, aid(number=target), number=number,
            extensions={'org.example': {'original': 'Cafe\u0301'}}))
    return list(values.values())


def index_of(values):
    return RelationIndex(RelationReferences(tuple(SourceRelations(artifact_bytes(v)) for v in values)))


def cyclic_records():
    return records(7, [(1, 2, 1, 'depends_on'), (1, 3, 2, 'depends_on'),
        (2, 4, 3, 'depends_on'), (3, 4, 4, 'depends_on'), (4, 1, 5, 'depends_on'),
        (2, 3, 6, 'depends_on'), (4, 5, 7, 'depends_on'), (5, 6, 8, 'depends_on'),
        (1, 2, 9, 'refines'), (6, 3, 10, 'supersedes')])


def expected_rows(values, start, direction, depth):
    """Independent queue traversal of plain fixture dictionaries, without Core views."""
    adjacency = {v['id']: [] for v in values}
    types = {v['id']: v['artifact_type'] for v in values}
    for value in values:
        for relation in value['relations']:
            for inverse in (False, True):
                if (direction == 'out' and inverse) or (direction == 'in' and not inverse):
                    continue
                source, target = ((relation['target'], value['id']) if inverse
                                  else (value['id'], relation['target']))
                kind = 'superseded_by' if inverse and relation['type'] == 'supersedes' else relation['type']
                adjacency[source].append({'relation_id': relation['relation_id'], 'type': kind,
                    'source': source, 'target': target, 'inverse': inverse,
                    'stored_source': value['id'], 'stored_relation': relation})
    distances, queue, edges = {start: 0}, deque([start]), []
    while queue:
        source = queue.popleft()
        if distances[source] == depth:
            continue
        for view in adjacency[source]:
            edges.append(view)
            if view['target'] not in distances:
                distances[view['target']] = distances[source] + 1
                queue.append(view['target'])
    return {'nodes': [{'id': name, 'artifact_type': types[name], 'distance': distance}
                     for name, distance in sorted(distances.items(), key=lambda pair: (pair[1], pair[0]))],
            'edges': sorted(edges, key=lambda view: (view['source'], view['type'], view['target'],
                                                   view['relation_id'], view['inverse']))}


def finish(work, targets=(1,)):
    for units in cycle(targets):
        before = work.state['units_completed']
        if work.advance(units):
            assert 0 <= work.state['units_completed'] - before <= units
            return work.result
        assert work.state['units_completed'] - before == units
        assert work.state['pending'] or work.state['current'] is not None
        with pytest.raises(RuntimeError):
            _ = work.result


@pytest.mark.parametrize('direction', ['in', 'out', 'both'])
@pytest.mark.parametrize('depth', [0, 1, 2, 3, 20])
def test_cycles_diamonds_and_multiple_relation_types_match_independent_scope(direction, depth):
    values = cyclic_records(); expected = expected_rows(values, aid(), direction, depth)
    for targets, supplied in [((1,), values), ((7, 1, 3), list(reversed(values))), ((10000,), values)]:
        work = TraceTraversal(index_of(supplied), aid(), direction=direction, depth=depth)
        assert finish(work, targets) == expected
        state = work.state
        assert state['complete'] and state['phase'] == 'complete'
        assert state['pending'] == [] and state['current'] is None
        assert state['units_completed'] == len(expected['nodes']) + len(expected['edges'])
        assert state['visited_count'] == len(expected['nodes'])
        assert state['edge_view_count'] == len(expected['edges'])
        assert len({n['id'] for n in expected['nodes']}) == len(expected['nodes'])
        assert aid(number=7) not in {n['id'] for n in expected['nodes']}
        assert work.advance(1) and work.state == state and work.result == expected


def test_small_target_retains_unprocessed_high_degree_edges_and_pending_nodes():
    values = records(514, [(1, n, n, 'depends_on') for n in range(2, 515)])
    work = TraceTraversal(index_of(values), aid(), direction='out', depth=1)
    with pytest.raises(RuntimeError):
        _ = work.result
    assert work.state['units_completed'] == 0 and not work.state['complete']
    assert work.advance(1) is False
    assert work.state['visited_count'] == 1 and work.state['edge_view_count'] == 0
    assert work.state['current']['remaining_edges'] == 513
    assert work.advance(1) is False
    assert work.state['current']['remaining_edges'] == 512
    assert work.state['pending'] == [{'id': aid(number=2), 'distance': 1}]
    assert work.state['edge_view_count'] == 1
    assert finish(work, (1, 5, 2)) == expected_rows(values, aid(), 'out', 1)
    assert work.state['units_completed'] == 1027


def test_long_chain_is_iterative_and_explicit_depth_survives_many_soft_targets():
    values = records(1301, [(n, n + 1, n, 'depends_on') for n in range(1, 1301)])
    index = index_of(values)
    divided = TraceTraversal(index, aid(), direction='out', depth=1300)
    whole = TraceTraversal(index, aid(), direction='out', depth=1300)
    expected = expected_rows(values, aid(), 'out', 1300)
    assert finish(divided, (17, 1, 128)) == finish(whole, (10000,)) == expected
    assert expected['nodes'][-1] == {'id': aid(number=1301), 'artifact_type': 'requirement', 'distance': 1300}
    assert len(expected['nodes']) == 1301 and len(expected['edges']) == 1300


def test_state_and_result_are_owned_without_io_or_durable_checkpoint_claim():
    values = cyclic_records(); index = index_of(values)
    before = [artifact_bytes(v) for v in values]
    with no_write_attempts(), patch('builtins.input', side_effect=AssertionError('stdin')), \
            patch('secrets.token_bytes', side_effect=AssertionError('entropy')):
        work = TraceTraversal(index, aid(), direction='both', depth=4)
        state = work.state; state['pending'].clear(); state['depth'] = 0
        assert work.state['pending'] and work.state['depth'] == 4
        work.advance(2)
        state = work.state; state['current']['remaining_edges'] = 0; state['pending'].clear()
        assert work.state['current']['remaining_edges'] > 0 and work.state['pending']
        expected = finish(work, (1,))
        changed = work.result; changed['nodes'].clear(); changed['edges'][0]['stored_relation']['extensions'].clear()
        assert work.result == expected == expected_rows(values, aid(), 'both', 4)
        assert work.state['validation_scope'] == 'supplied_relation_set_only'
        assert work.state['durable_checkpoint'] is False
        assert [artifact_bytes(v) for v in values] == before


@pytest.mark.parametrize('units', [0, -1, True, False, 1.5, '1', None])
def test_invalid_targets_do_not_consume_or_discard_pending_scope(units):
    values = cyclic_records(); work = TraceTraversal(index_of(values), aid(), direction='both', depth=2)
    work.advance(2); before = work.state
    with pytest.raises(ValueError):
        work.advance(units)
    assert work.state == before
    assert finish(work) == expected_rows(values, aid(), 'both', 2)


@pytest.mark.parametrize('direction,depth', [('wrong', 1), (None, 1), ('out', -1),
                                          ('out', True), ('out', 1.0), ('out', '1')])
def test_invalid_semantic_scope_is_rejected_before_any_graph_visit(direction, depth):
    index = index_of(cyclic_records())
    with patch.object(RelationIndex, 'for_artifact', side_effect=AssertionError('graph visit')):
        with pytest.raises(ValueError):
            TraceTraversal(index, aid(), direction=direction, depth=depth)


@pytest.mark.parametrize('depth', [0, 1])
def test_unknown_start_is_not_a_completed_empty_traversal(depth):
    with pytest.raises(ModelError) as failure:
        TraceTraversal(index_of(cyclic_records()), aid(number=99), direction='out', depth=depth)
    assert failure.value.reason == 'unknown_relation_view_artifact'


@pytest.mark.parametrize('index', [None, {}])
def test_unresolved_inputs_are_not_accepted_as_a_relation_index(index):
    with pytest.raises(TypeError):
        TraceTraversal(index, aid(), direction='out', depth=0)


@pytest.mark.parametrize('units', [0, 1, 3, 10000])
def test_close_is_idempotent_and_never_reopens_partial_or_complete_work(units):
    work = TraceTraversal(index_of(cyclic_records()), aid(), direction='both', depth=3)
    if units:
        work.advance(units)
    before = work.state
    work.close(); work.close()
    assert work.state['units_completed'] == before['units_completed']
    assert work.state['pending'] == before['pending'] and work.state['current'] == before['current']
    assert work.state['phase'] == ('complete' if before['complete'] else 'cancelled')
    with pytest.raises(RuntimeError):
        work.advance(1)
    with pytest.raises(RuntimeError):
        _ = work.result


def test_interrupted_edge_expansion_fails_without_publishing_or_restarting_work():
    values = records(3, [(1, 2, 1, 'depends_on'), (2, 3, 2, 'depends_on')])
    work = TraceTraversal(index_of(values), aid(), direction='out', depth=3)
    assert work.advance(2) is False
    with patch.object(RelationIndex, 'for_artifact', side_effect=OSError('owned injected read failure')):
        with pytest.raises(OSError):
            work.advance(1)
    assert work.state['phase'] == 'failed' and not work.state['complete']
    assert work.state['units_completed'] == 2
    with pytest.raises(RuntimeError):
        _ = work.result
    with pytest.raises(RuntimeError):
        work.advance(1)
    work.close(); assert work.state['phase'] == 'failed'


def test_public_cycle_trace_uses_real_cooperative_steps_and_retains_project_guards(tmp_path):
    root = tmp_path / 'project'; root.mkdir(); values = cyclic_records(); make_project(root, *values)
    before = inventory(root); observed = []; original = TraceTraversal.advance
    def advance_one(self, units):
        complete = original(self, 1)
        observed.append((self.state['units_completed'], complete))
        return complete
    with patch.object(TraceTraversal, 'advance', advance_one), no_write_attempts():
        direct = trace_artifact(root, aid(), direction='both', depth=3)
    assert direct.exit_code == 0 and direct.complete and len(observed) > 10
    assert observed[-1][1] and all(not complete for _, complete in observed[:-1])
    assert [units for units, _ in observed] == list(range(1, len(observed) + 1))
    data = direct.as_dict()['result']; expected = expected_rows(values, aid(), 'both', 3)
    assert {key: data[key] for key in ('nodes', 'edges')} == expected
    cli = dispatch_result(['trace', aid(), '--direction=both', '--depth=3', '--project', str(root)])
    assert cli.exit_code == 0 and cli.as_dict()['result'] == data
    assert data['coverage']['source_count'] == 7 and data['coverage']['relation_count'] == 10
    assert inventory(root) == before and not (root / '.specroad').exists()
