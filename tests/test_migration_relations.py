"""Q.3 source-bound identities, independent preimages and legacy projections."""
import copy
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch
import pytest

from specroad.migration.planning import plan_migration
from specroad.migration.plan_originals import _relation, _SourceRelations
from specroad.migration.reference01 import inventory_bytes
from support.migration_plans import FIELDS, planned_files, target_inputs, vector_source
from support.migration_relations import REQUIREMENT, VECTORS, EXPECTED, pair_source, immutable_source
from support.reference01 import put


@pytest.mark.parametrize('vector', VECTORS, ids=[row['name'] for row in VECTORS])
def test_exact_q3_preimage_digest_and_crockford_identity(vector):
    namespace, project, source_id, index, relation = json.loads(vector['preimage_utf8'])
    assert namespace == 'specroad-relation-migration-0.1-to-0.2-v1'
    before = copy.deepcopy(relation); seen = {}
    actual = _relation(project, source_id, index, relation, seen)
    assert actual == {**before, 'relation_id': vector['relation_id'], 'id_scheme': 'derived128-v1'}
    assert seen == {vector['relation_id']: vector['preimage_utf8'].encode('utf-8')}
    assert sha256(seen[vector['relation_id']]).hexdigest() == vector['preimage_sha256']
    assert vector['preimage_sha256'][:32] == vector['digest128_hex']
    assert relation == before


def test_native_plan_and_manifest_use_the_same_qualified_relation_identity():
    files = vector_source(); before = dict(files)
    result = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    assert result.ready and files == before
    target = planned_files(files, result.change_plan)
    relation = json.loads(target[REQUIREMENT])['relations'][0]
    assert relation['relation_id'] == EXPECTED['normative']
    manifest = json.loads(target['mappings/legacy-manifest.json'])
    rows = [r for r in manifest['entries'] if r['logical_path'] == REQUIREMENT]
    assert rows
    for row in rows:
        assert row['relation_projections'] == [{'index': 0, 'relation_id': relation['relation_id'],
            'id_scheme': 'derived128-v1', 'original': json.loads(files[REQUIREMENT])['relations'][0]}]
        assert target[row['path']] == files[REQUIREMENT]


def test_original_array_order_is_not_replaced_by_target_sort_or_position():
    files = pair_source(); first = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    first_relations = json.loads(planned_files(files, first.change_plan)[REQUIREMENT])['relations']
    assert [r['relation_id'] for r in first_relations] == [EXPECTED['normative'], EXPECTED['second_target_index']]
    value = json.loads(files[REQUIREMENT]); value['relations'].reverse(); put(files, value)
    second = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    second_relations = json.loads(planned_files(files, second.change_plan)[REQUIREMENT])['relations']
    assert [r['relation_id'] for r in second_relations] == [EXPECTED['second_target'], EXPECTED['original_index']]
    assert [r['target'] for r in second_relations] == ['SR-GOAL-0002', 'SR-GOAL-0001']


def test_immutable_relation_is_only_projected_in_manifest_and_original_bytes_remain():
    files = immutable_source(); before = dict(files)
    result = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    assert result.ready and files == before
    target = planned_files(files, result.change_plan)
    name = 'spec/baselines/SR-BASE-0001.json'; raw = files[name]
    assert target[name] == raw
    original = json.loads(raw); assert 'relation_id' not in original['relations'][0]
    manifest = json.loads(target['mappings/legacy-manifest.json'])
    rows = [r for r in manifest['entries'] if r['logical_path'] == name]
    assert rows
    ids = set()
    for row in rows:
        assert target[row['path']] == raw and row['original_byte_sha256'] == sha256(raw).hexdigest()
        projection = row['relation_projections'][0]; ids.add(projection['relation_id'])
        assert projection['id_scheme'] == 'derived128-v1' and projection['index'] == 0
        assert projection['original'] == original['relations'][0]
    assert len(ids) == 1


def test_repeated_source_is_stable_across_sandbox_and_file_enumeration(tmp_path, monkeypatch):
    files = pair_source(); inputs = target_inputs(files)
    values = []
    for name in ('first', 'second'):
        sandbox = tmp_path / name; sandbox.mkdir(); monkeypatch.chdir(sandbox)
        result = plan_migration(files, inputs=inputs, **FIELDS)
        values.append(result.canonical_bytes)
        files = dict(reversed(list(files.items())))
    assert values[0] == values[1]


def test_unrelated_artifact_metadata_and_original_json_layout_do_not_change_relation_id():
    files = vector_source(); value = json.loads(files[REQUIREMENT])
    value.update(title='A different non-relation field', revision=2)
    files[REQUIREMENT] = json.dumps(value, ensure_ascii=True, indent=4).encode()
    result = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    relation = json.loads(planned_files(files, result.change_plan)[REQUIREMENT])['relations'][0]
    assert relation['relation_id'] == EXPECTED['normative']


def test_native_derivation_never_uses_entropy_clock_or_a_file_writer():
    files = pair_source(); inputs = target_inputs(files); before = dict(files)
    with patch('secrets.token_bytes', side_effect=AssertionError('entropy')), \
         patch('time.time', side_effect=AssertionError('clock')), \
         patch.object(Path, 'write_bytes', side_effect=AssertionError('write')), \
         patch.object(Path, 'write_text', side_effect=AssertionError('write')):
        result = plan_migration(files, inputs=inputs, **FIELDS)
    assert result.ready and not result.write_authorized and files == before


def test_bound_projections_are_owned_and_cannot_mutate_later_materialization():
    inventory = inventory_bytes(pair_source()); projections = _SourceRelations(inventory)
    original = next(o for o in inventory.originals if o.path == REQUIREMENT)
    first = projections.projections(original); second = projections.materialize(original)
    first[0]['original']['extensions']['example.changed'] = ['not source data']
    second[0]['target'] = 'SR-GOAL-9999'
    again = projections.materialize(original)
    assert again[0]['target'] == 'SR-GOAL-0001' and again[0]['extensions'] == {}
    assert again[0]['relation_id'] == EXPECTED['normative']
