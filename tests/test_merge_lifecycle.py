"""17.f.W: native three-source lifecycle conflicts and original-byte retention."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.merge import inspect_merge_lifecycle
from specroad.model.errors import ModelError
from support.merge_lifecycle import artifact, bound_records, changed, decision, with_successors
from support.merge_relations import history_for
from support.read_only import inventory
from support.relations import aid
from test_merge_inventory import bind_files
from test_merge_sources import read_only_sources
from test_project_bundle import project


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    return project(tmp_path_factory.mktemp('lifecycle-seed')/'project').raw


@pytest.mark.parametrize('presence', [(True,True,True), (False,True,True),
                                     (False,False,True), (False,True,False)])
def test_identical_recorded_original_is_retained_byte_for_byte(tmp_path, original, presence):
    path, value = artifact(original, 'evidence')
    raw = json.dumps(value, indent=4).encode() + b'\r\n'
    sources, history = bound_records(tmp_path, original, path, [raw if p else None for p in presence])
    before = inventory(tmp_path)
    with read_only_sources():
        result = inspect_merge_lifecycle(sources, history=history)
    assert result.compatible and result.originals[path] == raw
    assert inventory(tmp_path) == before
    selected = 'ours' if presence[1] else 'theirs'
    assert decision(result, value['id'])['original'] == {
        'role':selected, 'path':path, 'byte_sha256':sha256(raw).hexdigest(),
        'classification':'unchanged_ours' if presence[1] else 'adopt_existing'}
    assert result.data['source_bindings'] == sources.binding
    assert result.data['source_bindings_sha256'] == sources.sha256
    assert result.data['metadata_policy_version'] == 'merge-metadata-v1'
    assert not result.ready and not result.write_authorized and not result.approval_granted


@pytest.mark.parametrize('states', [('draft','proposed','rejected'),
                                   ('proposed','draft','in_review'),
                                   ('approved','retired','proposed')])
def test_conflicting_lifecycle_transitions_keep_all_three_original_values(tmp_path, original, states):
    path, value = artifact(original)
    value['success_criterion'] = ['A synthetic stored goal; no approval claim.']
    variants = [changed(value, maturity=state) for state in states]
    sources, history = bound_records(tmp_path, original, path, variants)
    result = inspect_merge_lifecycle(sources, history=history)
    conflict, = result.conflicts
    assert conflict['kind'] == 'lifecycle_transition_conflict'
    assert conflict['identity'] == {'kind':'artifact','id':value['id'],'version':None}
    assert conflict['original_values'] == dict(zip(('base','ours','theirs'), variants))
    assert conflict['lifecycle_values'] == {role:{'maturity':state} for role,state in zip(('base','ours','theirs'), states)}
    with pytest.raises(ModelError) as error:
        _ = result.originals
    assert error.value.reason == 'unresolved_lifecycle_merge'


@pytest.mark.parametrize('side', ['ours','theirs','both'])
def test_one_or_identical_lifecycle_change_is_not_a_conflicting_transition(tmp_path, original, side):
    path, value = artifact(original)
    updated = changed(value, maturity='proposed')
    variants = [value, updated if side in ('ours','both') else value,
                updated if side in ('theirs','both') else value]
    sources, history = bound_records(tmp_path, original, path, variants)
    result = inspect_merge_lifecycle(sources, history=history)
    assert result.compatible and path not in result.originals
    assert not decision(result, value['id'])['protected']
    assert decision(result, value['id'])['original'] is None
    assert not result.approval_granted  # No mutable target or new release approval.


@pytest.mark.parametrize('sides,conflicts', [(((),(1,),(2,)),True),
    (((1,),(1,),(2,)),False), (((),(1,),(1,)),False), (((),(1,),()),False)])
def test_supersession_uses_inverse_successor_ids_not_relation_array_positions(tmp_path, original, sides, conflicts):
    _, old = artifact(original)
    sources = bind_files(tmp_path, with_successors(original, old, sides=sides))
    result = inspect_merge_lifecycle(sources, history=history_for(sources))
    assert result.compatible == (not conflicts)
    if conflicts:
        conflict, = result.conflicts
        assert conflict['kind'] == 'supersession_target_conflict'
        assert conflict['identity']['id'] == old['id']
        assert conflict['successor_ids'] == {'base':[], 'ours':[aid('goal',1)], 'theirs':[aid('goal',2)]}


@pytest.mark.parametrize('side', ['ours','theirs','both'])
def test_original_rewrite_conflicts_even_when_the_other_side_is_unchanged(tmp_path, original, side):
    path, value = artifact(original, 'evidence')
    updated = changed(value, title='Rewritten evidence')
    sources, history = bound_records(tmp_path, original, path, [value,
        updated if side in ('ours','both') else value, updated if side in ('theirs','both') else value])
    result = inspect_merge_lifecycle(sources, history=history)
    conflict, = result.conflicts
    assert conflict['kind'] == 'immutable_original_change'
    assert not result.compatible and not result.approval_granted
    assert conflict['base']['byte_sha256'] != conflict[side if side != 'both' else 'ours']['byte_sha256']


def test_unknown_history_never_turns_identical_originals_into_merge_authority(tmp_path, original):
    path, value = artifact(original, 'evidence')
    sources, history = bound_records(tmp_path, original, path, [value]*3)
    row = next(row for row in history['observations'] if row['role']=='theirs' and row['identity']['id']==value['id'])
    row['origin'] = None
    result = inspect_merge_lifecycle(sources, history=history)
    assert [row['kind'] for row in result.conflicts] == ['identity_history_unresolved']
    with pytest.raises(ModelError): _ = result.originals


def test_detached_deterministic_result_is_never_truthy_approval(tmp_path, original):
    path, value = artifact(original, 'evidence')
    sources, history = bound_records(tmp_path, original, path, [value]*3)
    first = inspect_merge_lifecycle(sources, history=history)
    history['observations'].reverse()
    second = inspect_merge_lifecycle(sources, history=history)
    assert first.canonical_bytes == second.canonical_bytes
    assert first.sha256 == sha256(first.canonical_bytes).hexdigest()
    first.data['decisions'].clear(); copy = first.originals; copy.clear()
    assert first.originals and first.data['decisions']
    with pytest.raises(FrozenInstanceError): first._encoded = b'{}'
    with pytest.raises(TypeError): bool(first)


def test_native_sources_cannot_be_replaced_by_unbound_dictionaries():
    with pytest.raises(ModelError) as failure:
        inspect_merge_lifecycle({}, history={})
    assert failure.value.reason == 'merge_sources_required'
