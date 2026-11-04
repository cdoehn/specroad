"""Collision rejection, exact original binding and migration-only derivation."""
from dataclasses import replace
import json
from unittest.mock import patch
import pytest

from specroad.migration.planning import plan_migration
from specroad.migration.plan_originals import _relation, _SourceRelations
from specroad.migration.plan_values import MigrationPlanError
from specroad.migration.reference01 import inventory_bytes
from specroad.model.errors import ModelError
from specroad.model.relation_identity import (RelationInventory, RelationIdentity,
    allocate_relation_identity)
from support.migration_plans import FIELDS, planned_files, target_inputs, vector_source
from support.migration_relations import REQUIREMENT, EXPECTED, pair_source, immutable_source
from support.reference01 import put, seal


@pytest.mark.parametrize('missing', ['nothing', 'configuration', 'mapping', 'resources'])
def test_collision_is_an_error_even_when_target_inputs_are_missing(missing, monkeypatch):
    files = pair_source(); inputs = target_inputs(files); before = dict(files)
    if missing == 'configuration': inputs['target_configuration'] = None
    elif missing == 'mapping': inputs['requirement_mappings'] = []
    elif missing == 'resources': inputs['target_resources'] = []
    # Trusted test injection at the encoder boundary; source data has no hook.
    monkeypatch.setitem(_relation.__globals__, 'encode128', lambda raw: '0' * 26)
    with patch('secrets.token_bytes', side_effect=AssertionError('random fallback')):
        with pytest.raises(MigrationPlanError) as caught:
            plan_migration(files, inputs=inputs, **FIELDS)
    assert caught.value.reason == 'migration_relation_id_collision'
    assert caught.value.exit_code == 3 and files == before


def test_identical_derivation_repeated_in_archived_and_current_snapshot_is_not_a_collision(monkeypatch):
    files = vector_source(); seal(files)
    monkeypatch.setitem(_relation.__globals__, 'encode128', lambda raw: '0' * 26)
    result = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    assert result.ready
    manifest = json.loads(planned_files(files, result.change_plan)['mappings/legacy-manifest.json'])
    rows = [r for r in manifest['entries'] if r['logical_path'] == REQUIREMENT]
    assert len({r['source_model_root_sha256'] for r in rows}) >= 2
    assert all(r['relation_projections'][0]['relation_id'] == 'REL-' + '0' * 26 for r in rows)


def test_collision_is_checked_across_historical_and_current_relation_inputs(monkeypatch):
    files = vector_source(); seal(files)
    goal = json.loads(files['spec/goals/SR-GOAL-0001.json']); goal['id'] = 'SR-GOAL-0002'; put(files, goal)
    current = json.loads(files[REQUIREMENT]); current['revision'] += 1
    current['relations'][0]['target'] = goal['id']; put(files, current)
    before = dict(files)
    monkeypatch.setitem(_relation.__globals__, 'encode128', lambda raw: '0' * 26)
    with pytest.raises(MigrationPlanError, match='migration_relation_id_collision'):
        plan_migration(files, inputs=target_inputs(files), **FIELDS)
    assert files == before


def test_original_relation_object_key_order_is_not_a_distinct_derivation():
    relation = json.loads(vector_source()[REQUIREMENT])['relations'][0]
    seen = {}
    first = _relation('synthetic-reference-project', 'SR-REQ-0001', 0, relation, seen)
    second = _relation('synthetic-reference-project', 'SR-REQ-0001', 0,
                       dict(reversed(list(relation.items()))), seen)
    assert first == second and len(seen) == 1 and first['relation_id'] == EXPECTED['normative']


@pytest.mark.parametrize('changed', ['bytes', 'path', 'snapshot', 'role', 'classification'])
def test_relation_lookup_rejects_a_changed_or_unbound_original(changed):
    inventory = inventory_bytes(pair_source()); projections = _SourceRelations(inventory)
    original = next(o for o in inventory.originals if o.path == REQUIREMENT)
    fields = {'bytes': {'source_bytes': original.source_bytes + b' '},
        'path': {'path': 'spec/requirements/SR-REQ-9999.json'},
        'snapshot': {'snapshot_root': '0' * 64}, 'role': {'role': 'attachment'},
        'classification': {'classification': 'immutable_legacy'}}[changed]
    with pytest.raises(MigrationPlanError, match='migration_relation_source_unbound'):
        projections.materialize(replace(original, **fields))
    assert projections.materialize(original)[0]['relation_id'] == EXPECTED['normative']


def test_immutable_projection_cannot_be_materialized_or_relabelled_as_mutable():
    inventory = inventory_bytes(immutable_source()); projections = _SourceRelations(inventory)
    original = next(o for o in inventory.originals if o.path == 'spec/baselines/SR-BASE-0001.json')
    assert projections.projections(original)
    with pytest.raises(MigrationPlanError, match='migration_immutable_relations'):
        projections.materialize(original)
    with pytest.raises(MigrationPlanError, match='migration_relation_source_unbound'):
        projections.materialize(replace(original, classification='mutable'))


@pytest.mark.parametrize('source', [None, {}, [], '0.1.0'])
def test_projection_inventory_requires_the_qualified_source_value_type(source):
    with pytest.raises(MigrationPlanError, match='migration_source_inventory_required'):
        _SourceRelations(source)


@pytest.mark.parametrize('field', ['relation_id', 'id_scheme'])
def test_existing_current_identity_fields_cannot_be_laundered_as_a_source_relation(field):
    files = vector_source(); old = json.loads(files[REQUIREMENT])
    old['relations'][0][field] = EXPECTED['normative'] if field == 'relation_id' else 'derived128-v1'
    put(files, old); before = dict(files)
    with pytest.raises(MigrationPlanError) as caught:
        plan_migration(files, inputs=target_inputs(files), **FIELDS)
    assert caught.value.reason == 'source_schema_invalid' and files == before


def test_regular_creation_remains_random_and_cannot_reserve_a_derived_projection():
    files = vector_source()
    plan = plan_migration(files, inputs=target_inputs(files), **FIELDS).change_plan
    projected = json.loads(planned_files(files, plan)[REQUIREMENT])['relations'][0]
    derived = RelationIdentity(projected['relation_id'], projected['id_scheme'])
    inventory = RelationInventory((), (), ())
    with pytest.raises(ModelError, match='new_relation_identity_must_be_random'):
        inventory.reserve(derived)
    with patch('specroad.model.relation_identity.secrets.token_bytes', side_effect=[bytes(16), b'\xff' * 16]) as entropy:
        first = allocate_relation_identity(inventory)
        second = allocate_relation_identity(first.inventory)
    assert first.identity.id == 'REL-' + '0' * 26 and second.identity.id == 'REL-7' + 'Z' * 25
    assert first.identity.id_scheme == second.identity.id_scheme == 'random128-v1'
    assert entropy.call_count == 2 and inventory.reserved_ids == frozenset()
