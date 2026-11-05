"""17.e.W: real native source integration and explicit common-history gates."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.merge import merge_relations, inspect_merge_identities, build_merge_inventory
from specroad.model.canonical import canonical_json_sha256 as digest
from specroad.model.errors import ModelError
from support.merge_relations import bound_relations, relation_observation, edge
from support.read_only import inventory
from support.relations import rid
from test_merge_sources import read_only_sources
from test_project_bundle import project


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    return project(tmp_path_factory.mktemp('relation-seed')/'project').raw


@pytest.fixture
def bind(tmp_path, original):
    def create(values):
        return bound_relations(tmp_path, original, values)
    return create


def test_independent_global_ids_keep_both_even_with_the_same_type_and_target(bind, tmp_path):
    a, b = edge(number=1), edge(number=2)
    sources, history, owner = bind([[], [a], [b]])
    before = inventory(tmp_path)
    with read_only_sources():
        result = merge_relations(sources, history=history)
    assert result.relations == [{'owner_id':owner,'relation':a}, {'owner_id':owner,'relation':b}]
    assert inventory(tmp_path) == before
    assert result.merged and not result.ready and not result.write_authorized
    assert result.data['source_bindings'] == sources.binding
    assert result.data['source_bindings_sha256'] == sources.sha256


@pytest.mark.parametrize('side', ['ours','theirs','both'])
def test_single_or_identical_content_change_keeps_the_chosen_value(bind, side):
    old = edge(); edited = edge(rationale='changed')
    left = edited if side in ('ours','both') else old
    right = edited if side in ('theirs','both') else old
    sources, history, owner = bind([[old], [left], [right]])
    result = merge_relations(sources, history=history)
    assert result.relations == [{'owner_id':owner,'relation':edited}]


def test_independent_fields_of_one_shared_relation_are_recursively_combined(bind):
    old = edge(rationale='old'); left, right = deepcopy(old), deepcopy(old)
    left['rationale'] = 'ours'; right['extensions'] = {'vendor.merge':{'score':1}}
    sources, history, owner = bind([[old], [left], [right]])
    expected = deepcopy(left); expected['extensions'] = right['extensions']
    assert merge_relations(sources, history=history).relations == [{'owner_id':owner,'relation':expected}]


def test_array_indices_and_owner_file_edits_do_not_redefine_relation_identity(bind):
    a, b = edge(number=1), edge(number=2)
    changed = edge(number=2, rationale='theirs')
    sources, history, owner = bind([[a,b], [b,a], [a,changed]])
    result = merge_relations(sources, history=history)
    assert result.relations == [{'owner_id':owner,'relation':a}, {'owner_id':owner,'relation':changed}]


@pytest.mark.parametrize('field', ['namespace','creation_event'])
def test_independent_origin_conflicts_before_identical_bytes_shortcut(bind, field):
    relation = edge(); sources, history, _ = bind([[relation]]*3)
    relation_observation(history)['origin'][field] = 'independent'
    result = merge_relations(sources, history=history)
    conflict, = result.conflicts
    assert conflict['kind'] == 'identity_collision' and conflict['diagnostic_code'] == 'SRV101'
    assert conflict['identity']['id'] == rid()
    assert conflict['base']['value_sha256'] == digest(relation)
    with pytest.raises(ModelError) as caught:
        _ = result.relations
    assert caught.value.reason == 'unresolved_relation_merge'


@pytest.mark.parametrize('missing', ['null','absent','all'])
def test_missing_origin_is_unresolved_even_for_identical_ids_and_bytes(bind, missing):
    sources, history, _ = bind([[edge()]]*3)
    row = relation_observation(history)
    if missing == 'null': row['origin'] = None
    elif missing == 'absent': history['observations'].remove(row)
    else: history['observations'] = []
    result = merge_relations(sources, history=history)
    assert result.conflicts and all(row['kind'] == 'identity_history_unresolved' for row in result.conflicts)
    assert not result.merged


def test_different_id_scheme_is_a_collision_with_known_shared_origin(bind):
    sources, history, _ = bind([[edge()], [edge(id_scheme='derived128-v1')], [edge()]])
    result = merge_relations(sources, history=history)
    assert result.conflicts[0]['kind'] == 'identity_collision'
    assert result.conflicts[0]['ours']['id_scheme'] == 'derived128-v1'


@pytest.mark.parametrize('kind', ['configuration','artifact','mapping'])
def test_same_origin_policy_applies_to_nonrelation_identities(bind, kind):
    sources, history, _ = bind([[],[],[]])
    row = next(row for row in history['observations'] if row['role']=='theirs' and row['identity']['kind']==kind)
    row['origin']['creation_event'] = 'independent-created'
    result = inspect_merge_identities(sources, history=history)
    conflict, = result.conflicts
    assert conflict['kind'] == 'identity_collision' and conflict['identity'] == row['identity']
    assert merge_relations(sources, history=history).conflicts == result.conflicts
    assert not result.ready and not result.write_authorized


def test_conflicting_same_field_preserves_original_values_and_hashes(bind):
    values = [edge(rationale=text) for text in ('base','ours','theirs')]
    sources, history, owner = bind([[value] for value in values])
    result = merge_relations(sources, history=history); conflict, = result.conflicts
    assert conflict['kind'] == 'relation_content_change'
    assert conflict['field_conflicts'] == [{'kind':'scalar_change','pointer':'/relation/rationale'}]
    assert conflict['original_values'] == dict(zip(('base','ours','theirs'),
        [{'owner_id':owner,'relation':value} for value in values]))
    assert [conflict[role]['value_sha256'] for role in ('base','ours','theirs')] == [digest(value) for value in values]


@pytest.mark.parametrize('ours,theirs', [([], [edge()]), ([edge()], []), ([],[])])
def test_absent_base_relation_is_not_an_implicit_removal(bind, ours, theirs):
    sources, history, _ = bind([[edge()], ours, theirs])
    conflict, = merge_relations(sources, history=history).conflicts
    assert conflict['kind'] == 'relation_absence_unproven'
    assert (conflict['ours']['state'] == 'absent') == (not ours)
    assert (conflict['theirs']['state'] == 'absent') == (not theirs)


def test_empty_relation_sets_need_no_invented_relations_or_creation_events(bind):
    sources, history, _ = bind([[], [], []])
    assert merge_relations(sources, history=history).relations == []


def test_results_are_detached_deterministic_and_not_authority(bind):
    sources, history, _ = bind([[edge()]]*3)
    first = merge_relations(sources, history=history)
    history['observations'].reverse()
    second = merge_relations(sources, history=history)
    assert first.canonical_bytes == second.canonical_bytes
    assert first.sha256 == sha256(first.canonical_bytes).hexdigest()
    history['observations'].clear(); copy = first.relations; copy[0]['relation'].clear()
    assert first.relations[0]['relation'] == edge()
    with pytest.raises(FrozenInstanceError): first._encoded = b'{}'
    with pytest.raises(TypeError): bool(first)


def test_inventory_stays_original_after_a_successful_relation_candidate(bind):
    sources, history, _ = bind([[],[edge()], [edge(number=2)]])
    before = build_merge_inventory(sources, plan_id='MP-'+'0'*26)
    result = merge_relations(sources, history=history)
    after = build_merge_inventory(sources, plan_id='MP-'+'0'*26)
    assert result.merged and before.canonical_bytes == after.canonical_bytes
    assert not after.ready and all(row['target_classification']=='conflict' for row in
        after.data['resources'] if row['identity']['kind']=='relation')


def test_dictionary_is_not_a_qualified_native_source():
    with pytest.raises(ModelError) as caught:
        merge_relations({}, history={})
    assert caught.value.reason == 'merge_sources_required'
