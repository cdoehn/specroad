"""Complete branching paths across actual pauses and persisted process restarts."""
from copy import deepcopy
from hashlib import sha256
from itertools import cycle, product
from unittest.mock import patch
import json

import pytest

from specroad.graph.indices import RelationIndex
from specroad.graph.path_output import PathRecord
from specroad.graph.references import RelationReferences
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.query import WhyTraversal, why_artifact
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.processes import run_core
from support.read_only import inventory, make_project, no_write_attempts
from support.relations import aid, artifact, edge, rid


def index_of(values):
    return RelationIndex(RelationReferences(tuple(SourceRelations(artifact_bytes(v)) for v in values)))


def branching(width=3, layers=4):
    levels = [[aid()]] + [[aid(number=2 + level * width + n) for n in range(width)]
                         for level in range(layers)] + [[aid('goal')]]
    values = {name: domain_value('goal' if name == aid('goal') else 'requirement',
                                id=name, relations=[]) for names in levels for name in names}
    number, relation_ids = 1, {}
    for before, after in zip(levels, levels[1:]):
        for source in before:
            for target in after:
                kind = 'addresses' if target == aid('goal') else 'refines'
                values[source]['relations'].append(edge(kind, target, number=number))
                relation_ids[(source, target)] = rid(number)
                number += 1
    values[aid('goal')]['relations'].append(edge('derived_from', aid('source'), number=number))
    values[aid('source')] = artifact('source', source_kind='document', locator='owned:source',
                                   captured_at='2026-01-01T00:00:00Z')
    expected = []
    # Independent Cartesian-product oracle; no Core traversal/predecessor calls.
    for middle in product(*levels[1:-1]):
        nodes = (aid(),) + middle + (aid('goal'),)
        relations = tuple(relation_ids[pair] for pair in zip(nodes, nodes[1:]))
        expected.append((nodes, relations, (False,) * len(relations)))
        expected.append((nodes + (aid('source'),), relations + (rid(number),),
                         (False,) * (len(relations) + 1)))
    return list(values.values()), expected


def signature(record):
    return (tuple(a['id'] for a in record['artifacts']),
            tuple(r['relation_id'] for r in record['relations']), tuple(record['inverse']))


def finish(work, targets=(1,)):
    for units in cycle(targets):
        before = work.state['units_completed']
        complete = work.advance(units)
        assert 0 < work.state['units_completed'] - before <= units or complete
        if complete:
            return work.result
        assert work.state['units_completed'] - before == units
        with pytest.raises(RuntimeError):
            _ = work.result


def resumed(index, work):
    raw = work.checkpoint()
    restored = WhyTraversal.restore(index, raw, expected_sha256=sha256(raw).hexdigest())
    assert restored.state == work.state and restored.checkpoint() == raw
    return restored


@pytest.mark.parametrize('targets', [(1,), (3, 19, 1), (1000000,)])
def test_8192_paths_match_independent_product_without_sampling_or_longer_walks(targets):
    values, expected = branching(4, 6)
    work = WhyTraversal(index_of(values), aid(), depth=8)
    result = finish(work, targets)
    assert len(result['paths']) == len(expected) == 8192
    assert {signature(p) for p in result['paths']} == set(expected)
    assert result['targets'] == [
        {'id': aid('goal'), 'artifact_type': 'goal', 'distance': 7, 'path_count': 4096},
        {'id': aid('source'), 'artifact_type': 'source', 'distance': 8, 'path_count': 4096}]
    assert [signature(p) for p in result['paths']] == sorted(expected[:], key=lambda p: (
        'goal' if p[0][-1] == aid('goal') else 'source', p))
    before = work.state
    assert work.advance(1) and work.state == before and work.result == result


@pytest.mark.parametrize('stage', ['initial', 'edge', 'search', 'paths', 'prefix', 'next_target', 'complete'])
def test_checkpoint_roundtrip_preserves_each_real_frontier_without_prefix_replay(stage):
    values, expected = branching(2, 2); index = index_of(values)
    work = WhyTraversal(index, aid(), depth=4)
    if stage == 'edge':
        work.advance(2)
        assert work.state['current'] == aid() and work.state['next_edge'] == 1
    elif stage == 'search':
        work.advance(5)
        assert work.state['phase'] == 'search'
    elif stage in ('paths', 'prefix', 'next_target'):
        while work.state['phase'] != 'paths':
            work.advance(1)
        while stage == 'prefix' and work.state['paths_materialized'] < 2:
            work.advance(1)
        while stage == 'next_target' and work.state['target_position'] < 1:
            work.advance(1)
    elif stage == 'complete':
        finish(work)
    before = work.state; restored = resumed(index, work)
    work.close()
    with patch.object(PathRecord, 'from_views', wraps=PathRecord.from_views) as produced:
        result = finish(restored, (1, 7, 2))
    assert produced.call_count == len(expected) - before['paths_materialized']
    assert {signature(p) for p in result['paths']} == set(expected)
    reference = WhyTraversal(index, aid(), depth=4); finish(reference, (10000,))
    assert restored.state['units_completed'] == reference.state['units_completed']


@pytest.mark.parametrize('stage', ['edge', 'prefix', 'next_target'])
def test_persisted_checkpoint_resumes_in_a_fresh_process_with_independent_digest(tmp_path, stage):
    values, expected = branching(); index = index_of(values)
    work = WhyTraversal(index, aid(), depth=6)
    if stage == 'edge':
        work.advance(2)
    else:
        while work.state['paths_materialized'] < 3:
            work.advance(1)
        while stage == 'next_target' and work.state['target_position'] < 1:
            work.advance(1)
    before = work.state
    raw = work.checkpoint(); trusted_digest = sha256(raw).hexdigest()
    (tmp_path / 'checkpoint.json').write_bytes(raw)
    (tmp_path / 'graph.json').write_text(json.dumps(values))
    body = '''
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
import json
from specroad.graph.indices import RelationIndex
from specroad.graph.path_output import PathRecord
from specroad.graph.references import RelationReferences
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes
from specroad.query import WhyTraversal
values = json.loads(Path('graph.json').read_text())
index = RelationIndex(RelationReferences(tuple(SourceRelations(json.dumps(v).encode()) for v in values)))
work = WhyTraversal.restore(index, Path('checkpoint.json').read_bytes(), expected_sha256=TRUSTED_DIGEST)
initial = work.state
with patch.object(PathRecord, 'from_views', wraps=PathRecord.from_views) as produced:
    while not work.advance(3):
        pass
    calls = produced.call_count
print(json.dumps({'initial': initial, 'final': work.state, 'new_paths': calls,
                  'result_sha256': sha256(canonical_json_bytes(work.result)).hexdigest()}))
'''.replace('TRUSTED_DIGEST', repr(trusted_digest))
    process = run_core(body, tmp_path, capture=True)
    assert process.returncode == 0, process.stderr
    output = json.loads(process.stdout)
    assert output['initial'] == before
    assert output['new_paths'] == len(expected) - before['paths_materialized']
    result = finish(work, (11,))
    assert output['final'] == work.state
    assert output['result_sha256'] == sha256(canonical_json_bytes(result)).hexdigest()
    assert (tmp_path / 'checkpoint.json').read_bytes() == raw


def test_every_single_operation_can_be_exported_and_restored_with_owned_progress():
    values, expected = branching(2, 1); index = index_of(values)
    work = WhyTraversal(index, aid(), depth=3)
    while not work.advance(1):
        work = resumed(index, work)
        state = work.state; state['pending'].clear(); state['path_frames'].clear()
        assert work.state != state or not (work.state['pending'] or work.state['path_frames'])
    assert {signature(p) for p in work.result['paths']} == set(expected)
    result = work.result; result['paths'].clear(); result['targets'].clear()
    assert len(work.result['paths']) == 4


@pytest.mark.parametrize('damage', ['truncated', 'tampered', 'wrong_digest', 'mutable_bytes', 'uppercase_digest'])
def test_integrity_is_checked_before_parsing_or_graph_visits(damage):
    values, _ = branching(2, 1); index = index_of(values)
    raw = WhyTraversal(index, aid(), depth=3).checkpoint(); digest = sha256(raw).hexdigest()
    if damage == 'truncated':
        raw = raw[:-1]
    elif damage == 'tampered':
        raw = raw.replace(b'"units":0', b'"units":1')
    elif damage == 'wrong_digest':
        digest = '0' * 64
    elif damage == 'mutable_bytes':
        raw = bytearray(raw)
    else:
        digest = digest.upper()
    with patch.object(RelationIndex, 'for_artifact', side_effect=AssertionError('graph before integrity')):
        with pytest.raises(ValueError):
            WhyTraversal.restore(index, raw, expected_sha256=digest)


@pytest.mark.parametrize('change', ['reachable_edge', 'unreached_relation_metadata', 'added_identity'])
def test_complete_input_binding_rejects_changed_graph_including_unreached_data(change):
    values, _ = branching(2, 1)
    values += [domain_value('requirement', id=aid(number=900),
                           relations=[edge('depends_on', aid(number=901), number=900)]),
               domain_value('requirement', id=aid(number=901), relations=[])]
    raw = WhyTraversal(index_of(values), aid(), depth=3).checkpoint()
    changed = deepcopy(values)
    if change == 'reachable_edge':
        changed[0]['relations'].pop()
    elif change == 'unreached_relation_metadata':
        changed[-2]['relations'][0]['extensions'] = {'org.example': {'changed': True}}
    else:
        changed.append(domain_value('requirement', id=aid(number=902), relations=[]))
    with pytest.raises(ValueError):
        WhyTraversal.restore(index_of(changed), raw, expected_sha256=sha256(raw).hexdigest())
    reordered = deepcopy(values[::-1])
    for value in reordered:
        value['relations'].reverse()
    assert WhyTraversal.restore(index_of(reordered), raw, expected_sha256=sha256(raw).hexdigest()).checkpoint() == raw


@pytest.mark.parametrize('damage', ['extra_field', 'algorithm', 'phase', 'boolean_distance',
                                  'duplicate_pending', 'negative_offset', 'invalid_inverse',
                                  'noncanonical', 'duplicate_field'])
def test_closed_checkpoint_contract_rejects_malformed_even_with_an_owner_supplied_digest(damage):
    values, _ = branching(2, 1); index = index_of(values)
    work = WhyTraversal(index, aid(), depth=3); work.advance(2)
    value = json.loads(work.checkpoint())
    if damage == 'extra_field':
        value['execute'] = 'untrusted'
    elif damage == 'algorithm':
        value['algorithm'] = 'other'
    elif damage == 'phase':
        value['phase'] = 'complete'
    elif damage == 'boolean_distance':
        value['distances'][aid()] = False
    elif damage == 'duplicate_pending':
        value['pending'] *= 2
    elif damage == 'negative_offset':
        value['edge_offset'] = -1
    elif damage == 'invalid_inverse':
        name = next(name for name in value['predecessors'] if name != aid())
        value['predecessors'][name][0][1] = True
    raw = canonical_json_bytes(value)
    if damage == 'noncanonical':
        raw += b'\n'
    elif damage == 'duplicate_field':
        raw = b'{"units":2,' + raw[1:]
    with pytest.raises(ValueError):
        WhyTraversal.restore(index, raw, expected_sha256=sha256(raw).hexdigest())


@pytest.mark.parametrize('damage', ['drop_prefix', 'wrong_frame', 'wrong_position', 'wrong_path'])
def test_materialization_cursor_and_completed_prefix_are_validated(damage):
    values, _ = branching(2, 1); index = index_of(values)
    work = WhyTraversal(index, aid(), depth=3)
    while work.state['target_position'] < 1:
        work.advance(1)
    value = json.loads(work.checkpoint())
    if damage == 'drop_prefix':
        value['paths'].pop()
    elif damage == 'wrong_frame':
        value['frames'][0]['node'] = aid()
    elif damage == 'wrong_position':
        value['target_position'] = 0
    else:
        value['paths'][0]['inverse'][0] = True
    raw = canonical_json_bytes(value)
    with pytest.raises(ValueError):
        WhyTraversal.restore(index, raw, expected_sha256=sha256(raw).hexdigest())


@pytest.mark.parametrize('units', [0, -1, True, 1.5, '1', None])
def test_invalid_work_targets_preserve_all_state(units):
    values, _ = branching(2, 1); work = WhyTraversal(index_of(values), aid(), depth=3)
    before = work.checkpoint()
    with pytest.raises(ValueError):
        work.advance(units)
    assert work.checkpoint() == before


@pytest.mark.parametrize('depth', [-1, True, 1.5, '1'])
def test_invalid_semantic_depth_is_not_coerced(depth):
    values, _ = branching(2, 1)
    with pytest.raises(ValueError):
        WhyTraversal(index_of(values), aid(), depth=depth)


def test_unknown_start_and_invalid_index_are_not_empty_successes():
    values, _ = branching(2, 1)
    with pytest.raises(ModelError):
        WhyTraversal(index_of(values), aid(number=999), depth=0)
    with pytest.raises(TypeError):
        WhyTraversal(values, aid(), depth=3)


@pytest.mark.parametrize('mode', ['close', 'failure'])
def test_cancelled_or_failed_work_cannot_publish_but_prior_checkpoint_remains_owned(mode):
    values, expected = branching(2, 1); index = index_of(values)
    work = WhyTraversal(index, aid(), depth=3)
    while work.state['phase'] == 'search':
        work.advance(1)
    raw = work.checkpoint()
    if mode == 'close':
        work.close(); work.close()
        assert work.state['phase'] == 'cancelled'
    else:
        with patch.object(work, '_path_step', side_effect=MemoryError('injected allocation refusal')):
            with pytest.raises(MemoryError):
                work.advance(1)
        assert work.state['phase'] == 'failed'
    for action in (lambda: work.advance(1), work.checkpoint, lambda: work.result):
        with pytest.raises(RuntimeError):
            action()
    restored = WhyTraversal.restore(index, raw, expected_sha256=sha256(raw).hexdigest())
    assert {signature(p) for p in finish(restored)['paths']} == set(expected)


def test_long_path_materialization_and_restore_do_not_require_recursive_walks():
    count = 1100
    values = [domain_value('requirement', id=aid(number=n), relations=[
        edge('refines', aid(number=n + 1), number=n)]) for n in range(1, count)]
    values += [domain_value('requirement', id=aid(number=count),
                           relations=[edge('addresses', aid('goal'), number=count)]),
               domain_value('goal', id=aid('goal'), relations=[])]
    index = index_of(values); work = WhyTraversal(index, aid(), depth=count)
    while work.state['phase'] == 'search':
        work.advance(1)
    work.advance(1000)
    assert len(work.state['path_frames']) == 1001
    work = resumed(index, work)
    result = finish(work, (7, 1))
    assert [signature(p) for p in result['paths']] == [
        (tuple(aid(number=n) for n in range(1, count + 1)) + (aid('goal'),),
         tuple(rid(n) for n in range(1, count + 1)), (False,) * count)]


def test_public_why_uses_real_small_steps_and_checkpoint_codec_without_project_writes(tmp_path):
    values, expected = branching(2, 2)
    root = tmp_path / 'project'; root.mkdir()
    make_project(root, *values, resource_limits={'trace_depth': 4})
    before = inventory(root); original = WhyTraversal.advance; phases = set()

    def tiny_steps(work, _units):
        phases.add(work.state['phase'])
        return original(work, 1)

    with no_write_attempts(), patch.object(WhyTraversal, 'advance', tiny_steps):
        result = why_artifact(root, aid())
        index = index_of(values); work = WhyTraversal(index, aid(), depth=4)
        work.advance(1); restored = resumed(index, work)
        data = finish(restored)
    assert result.exit_code == 0 and phases == {'search', 'paths'}
    assert result.as_dict()['result']['paths'] == data['paths']
    assert {signature(p) for p in data['paths']} == set(expected)
    assert inventory(root) == before and not (root / '.specroad').exists()
