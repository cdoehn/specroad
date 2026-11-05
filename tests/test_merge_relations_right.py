"""17.e.R: deliberate removal, origin tampering and protected source boundaries."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from specroad.merge import merge_relations, inspect_merge_identities, SourceRequest, load_merge_sources
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from support.merge_relations import edge, history_for, relation_observation
from support.model import put
from support.read_only import inventory
from support.relations import rid
from test_merge_inventory import bind_files
from test_merge_relations import bind, original
from test_merge_sources import read_only_sources


@pytest.mark.parametrize('side', ['ours','theirs','both'])
def test_explicit_removal_against_unchanged_is_a_read_only_candidate(bind, side):
    old = edge(); left, right, options = [old], [old], {}
    if side in ('ours','both'): left = []; options['removed_ours'] = [rid()]
    if side in ('theirs','both'): right = []; options['removed_theirs'] = [rid()]
    sources, history, _ = bind([[old], left, right])
    result = merge_relations(sources, history=history, **options)
    assert result.merged and result.relations == []
    assert not result.ready and not result.write_authorized


@pytest.mark.parametrize('side', ['ours','theirs'])
def test_explicit_remove_against_changed_same_id_is_a_conflict(bind, side):
    old, edited = edge(), edge(rationale='changed')
    values = [[old], [], [edited]]
    if side=='theirs': values[1],values[2] = values[2],values[1]
    sources, history, _ = bind(values)
    result = merge_relations(sources, history=history, **{'removed_'+side:[rid()]})
    conflict, = result.conflicts
    assert conflict['kind'] == 'relation_remove_edit'
    assert conflict[side]['state'] == 'absent'
    assert conflict['identity']['id'] == rid()
    with pytest.raises(ModelError): _ = result.relations


@pytest.mark.parametrize('value', [None, True, rid(), {}, [True], [rid(999)], [rid(),rid()]])
def test_removal_wishes_must_be_unique_absent_native_base_relations(bind, value):
    sources, history, _ = bind([[edge()], [], [edge()]])
    with pytest.raises(ModelError) as caught:
        merge_relations(sources, history=history, removed_ours=value)
    assert caught.value.reason == 'invalid_relation_removal'


def test_present_relation_cannot_be_marked_removed(bind):
    sources, history, _ = bind([[edge()]]*3)
    with pytest.raises(ModelError) as caught:
        merge_relations(sources, history=history, removed_ours=[rid()])
    assert caught.value.reason == 'invalid_relation_removal'


@pytest.mark.parametrize('field,value', [('created_at','2026-01-02T00:00:00Z'),
    ('created_by',{'actor_type':'tool','actor_id':'other'})])
def test_relation_birth_metadata_cannot_change_even_with_same_history_claim(bind, field, value):
    old = edge(created_at='2026-01-01T00:00:00Z',created_by={'actor_type':'tool','actor_id':'first'})
    changed = deepcopy(old); changed[field] = value
    sources, history, _ = bind([[old], [changed], [old]])
    assert merge_relations(sources, history=history).conflicts[0]['kind'] == 'relation_origin_metadata_change'


def test_equal_origin_metadata_remains_unchanged_during_content_merge(bind):
    old = edge(created_at='2026-01-01T00:00:00Z',created_by={'actor_type':'tool','actor_id':'first'})
    left,right=deepcopy(old),deepcopy(old);left['rationale']='ours';right['extensions']={'vendor.merge':2}
    sources,history,_=bind([[old],[left],[right]])
    value=merge_relations(sources,history=history).relations[0]['relation']
    assert value == {**old,'rationale':'ours','extensions':{'vendor.merge':2}}


def test_owner_move_is_not_hidden_by_global_identity_or_array_position(tmp_path, original):
    goal_path = next(p for p in original if p.startswith('spec/goals/'))
    other_path = next(p for p in original if p.startswith('spec/documents/'))
    variants=[]
    for owner_path in (goal_path,other_path,goal_path):
        files=dict(original);value=json.loads(files[owner_path]);value['relations']=[edge()]
        files[owner_path]=jcs(value);variants.append(files)
    sources=bind_files(tmp_path,variants);history=history_for(sources)
    conflict,=merge_relations(sources,history=history).conflicts
    assert conflict['kind']=='relation_owner_change'
    assert conflict['base']['owner_id'] != conflict['ours']['owner_id']


def test_duplicate_global_relation_ids_are_not_disambiguated_by_owner_paths(tmp_path, original):
    from specroad.snapshots.inventory import source_resource_rows
    files=dict(original)
    for prefix in ('spec/goals/','spec/requirements/'):
        path=next(p for p in files if p.startswith(prefix));value=json.loads(files[path]);value['relations']=[edge()]
        files[path]=jcs(value)
    with pytest.raises(ModelError):
        sources=bind_files(tmp_path,[files]*3)
        # Native admission or the complete inventory must reject, not rename.
        source_resource_rows(sources.ours)


@pytest.mark.parametrize('damage', ['unknown_field','format','source_hash','observations_type','extra_row_field',
    'role','identity_extra','identity_unknown','identity_version','duplicate','origin_type','origin_field','origin_empty','origin_nul'])
def test_closed_source_bound_history_input_rejects_tampering_before_content_shortcuts(bind, damage):
    sources,history,_=bind([[edge()]]*3)
    row=relation_observation(history)
    if damage=='unknown_field': history['write_authorized']=True
    elif damage=='format': history['history_format_version']=True
    elif damage=='source_hash': history['source_bindings_sha256']='0'*64
    elif damage=='observations_type': history['observations']={}
    elif damage=='extra_row_field': row['proof']=True
    elif damage=='role': row['role']='OURS'
    elif damage=='identity_extra': row['identity']['pointer']='/relations/0'
    elif damage=='identity_unknown': row['identity']['id']=rid(999)
    elif damage=='identity_version': row['identity']['version']='1.0.0'
    elif damage=='duplicate': history['observations'].append(deepcopy(row))
    elif damage=='origin_type': row['origin']=True
    elif damage=='origin_field': row['origin']['proof']=True
    elif damage=='origin_empty': row['origin']['creation_event']=' '
    elif damage=='origin_nul': row['origin']['namespace']='a\0b'
    with pytest.raises(ModelError): merge_relations(sources,history=history)


def test_known_collision_is_not_masked_by_another_roles_unknown_origin(bind):
    sources,history,_=bind([[edge()]]*3)
    relation_observation(history,'base')['origin']=None
    relation_observation(history,'theirs')['origin']['namespace']='different'
    conflict,=merge_relations(sources,history=history).conflicts
    assert conflict['kind']=='identity_collision'


def test_equal_new_relation_id_on_both_sides_requires_same_origin(bind):
    sources,history,_=bind([[],[edge()],[edge()]])
    relation_observation(history,'theirs')['origin']['creation_event']='independent'
    conflict,=merge_relations(sources,history=history).conflicts
    assert conflict['kind']=='identity_collision' and conflict['base']['state']=='absent'


def test_unique_new_id_does_not_require_an_invented_second_history(bind):
    sources,history,_=bind([[],[edge()],[]])
    history['observations'].remove(relation_observation(history))
    assert merge_relations(sources,history=history).relations[0]['relation']==edge()


def test_conflict_copy_mutation_does_not_change_original_observations(bind):
    sources,history,_=bind([[edge(rationale=v)] for v in ('base','ours','theirs')])
    result=merge_relations(sources,history=history);copy=result.conflicts
    copy[0]['original_values']['ours']['relation'].clear();history['observations'].clear()
    assert result.conflicts[0]['original_values']['ours']['relation']['rationale']=='ours'


def test_current_source_mutation_after_capture_is_rejected(bind, tmp_path):
    sources,history,_=bind([[edge()]]*3)
    path=next(p for p in sources.ours.files if p.startswith('spec/goals/'))
    value=json.loads(sources.ours.files[path]);value['title']='late edit'
    put(tmp_path/'ours',path,jcs(value))
    with pytest.raises(ModelError): merge_relations(sources,history=history)


def test_sources_are_rechecked_after_candidate_computation(bind, tmp_path):
    sources,history,_=bind([[edge(rationale='old')],[edge(rationale='ours')],[edge(extensions={'vendor.merge':1})]])
    from specroad.merge.fields import merge_fields
    path=next(p for p in sources.ours.files if p.startswith('spec/goals/'))
    def mutate_then_merge(*args,**kwargs):
        value=json.loads(sources.ours.files[path]);value['title']='late'
        put(tmp_path/'ours',path,jcs(value))
        return merge_fields(*args,**kwargs)
    with patch('specroad.merge.relations.merge_fields',side_effect=mutate_then_merge),pytest.raises(ModelError):
        merge_relations(sources,history=history)


def test_no_random_rename_or_writer_is_used_even_for_identity_collisions(bind):
    sources,history,_=bind([[edge()]]*3)
    relation_observation(history)['origin']['namespace']='different'
    with read_only_sources(),patch('os.urandom',side_effect=AssertionError('random rename')):
        result=merge_relations(sources,history=history)
    assert result.conflicts[0]['identity']['id']==rid()


def test_real_qualified_legacy_navigation_is_retained_without_rewriting_originals(tmp_path):
    from support.legacy_manifest import migrated,write_files,MANIFEST
    _,files,_=migrated();root=tmp_path/'source';write_files(root,files)
    sources=load_merge_sources(*(SourceRequest(root) for _ in range(3)))
    history=history_for(sources);before=inventory(root)
    with read_only_sources(): result=merge_relations(sources,history=history)
    expected=[]
    entries={entry['path']:entry for entry in json.loads(files[MANIFEST])['entries']}
    for path,raw in files.items():
        if not path.startswith('spec/') or not path.endswith('.json'): continue
        value=json.loads(raw)
        if path in entries:
            relations=[{**item['original'],'relation_id':item['relation_id'],'id_scheme':item['id_scheme']}
                       for item in entries[path]['relation_projections']]
        else:
            relations=value['relations']
        expected.extend({'owner_id':value['id'],'relation':row} for row in relations)
    expected.sort(key=lambda row:row['relation']['relation_id'])
    assert expected and result.relations==expected
    assert inventory(root)==before and not result.write_authorized


@pytest.mark.parametrize('kind',['profile','rule','language_registry','language_package'])
def test_other_normative_resource_histories_share_the_identity_collision_gate(tmp_path, kind):
    from specroad.cli.application import dispatch_result
    from support.profiles import profile_data
    root=tmp_path/'project';assert dispatch_result(['init',str(root)]).exit_code==0
    put(root,'profiles/unused.json',jcs(profile_data(profile_id='unused')))
    put(root,'rules/unused.json',jcs({'schema_version':'0.2.0','rule_id':'unused','version':'1.0.0','payload':{}}))
    sources=load_merge_sources(*(SourceRequest(root) for _ in range(3)));history=history_for(sources)
    row=next(row for row in history['observations'] if row['role']=='ours' and row['identity']['kind']==kind)
    row['origin']['namespace']='independent'
    conflict,=inspect_merge_identities(sources,history=history).conflicts
    assert conflict['kind']=='identity_collision' and conflict['identity']['kind']==kind


@pytest.mark.parametrize('ours,theirs', [(True,1),(1,True),(None,False)])
def test_json_types_do_not_collapse_in_whole_relation_equality_shortcuts(bind, ours, theirs):
    values=[edge(extensions={'vendor.merge':value}) for value in ('base',ours,theirs)]
    sources,history,_=bind([[value] for value in values])
    result=merge_relations(sources,history=history)
    assert result.conflicts[0]['kind']=='relation_content_change'
    assert result.conflicts[0]['field_conflicts'][0]['pointer']=='/relation/extensions/vendor.merge'


def test_two_known_common_origins_are_not_sensitive_to_observation_order(bind):
    sources,history,_=bind([[edge()]]*3)
    history['observations'].reverse()
    assert merge_relations(sources,history=history).merged


def test_history_for_another_role_order_is_not_accepted(tmp_path, original):
    from specroad.merge import MergeSources
    from support.merge_relations import bound_relations
    sources,history,_=bound_relations(tmp_path,original,[[],[edge()],[edge(number=2)]])
    swapped=MergeSources(sources.base,sources.theirs,sources.ours)
    with pytest.raises(ModelError) as caught: merge_relations(swapped,history=history)
    assert caught.value.reason=='merge_history_source_mismatch'
