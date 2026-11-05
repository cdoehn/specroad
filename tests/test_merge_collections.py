"""17.d.W: explicit built-in keys and real immutable source observations."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.merge import CollectionConflict, build_merge_inventory, merge_fields, merge_attachments
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.domain_schemas import domain_schema
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.record_schemas import record_schema
from specroad.model.schema_catalog import SchemaCatalog, SchemaLookupError
from support.domain import domain_value
from support.records import record_value
from support.read_only import inventory
from test_merge_inventory import bind_files, row_for, PLAN_ID, ROLES
from test_merge_sources import read_only_sources
from test_project_bundle import project


def merge(values, schema):
    before = [jcs(value) for value in values]
    result = merge_fields(*values, schema_id=schema['$id'])
    assert [jcs(value) for value in values] == before
    assert result.ready is False and result.write_authorized is False
    return result


def test_independent_tags_merge_only_with_explicit_schema_identity():
    values = [domain_value('goal', tags=tags) for tags in (['stable'], ['stable', 'ours'], ['theirs', 'stable'])]
    result = merge(values, domain_schema('goal'))
    assert result.value['tags'] == ['ours', 'stable', 'theirs']
    assert result.conflicts == ()
    conservative = merge_fields(*values)
    assert conservative.conflicts[0].pointer == '/tags'
    assert conservative.conflicts[0].kind == 'collection_semantics_required'


def test_term_synonyms_are_explicit_sets_without_changing_other_fields():
    base = domain_value('term', synonyms=['base'], forbidden_synonyms=[])
    ours = deepcopy(base); ours['synonyms'].append('left')
    theirs = deepcopy(base); theirs['synonyms'].append('right'); theirs['forbidden_synonyms'] = ['ambiguous']
    result = merge([base, ours, theirs], domain_schema('term'))
    assert result.value == {**base, 'synonyms': ['base', 'left', 'right'], 'forbidden_synonyms': ['ambiguous']}


@pytest.mark.parametrize('ours,theirs,expected', [
    (['b','a'], ['a','b'], ['b','a']),
    (['b','a'], ['c','b','a'], ['c','b','a']),
    (['c','b','a'], ['b','a'], ['c','b','a']),
    (['b'], ['a','b','c'], ['b','c']),
])
def test_set_reordering_and_one_sided_changes_preserve_an_existing_target(ours, theirs, expected):
    values = [domain_value('goal', tags=value) for value in (['a','b'], ours, theirs)]
    assert merge(values, domain_schema('goal')).value['tags'] == expected


def test_keyed_objects_and_nested_scalar_sets_merge_independently():
    base = record_value('configuration')
    ours, theirs = deepcopy(base), deepcopy(base)
    ours['dimensions'][0]['allowed_values'].append('mac')
    theirs['dimensions'][0]['allowed_values'].append('bsd')
    ours['dimensions'].append({'name':'region', 'allowed_values':['eu'], 'default':'eu'})
    theirs['dimensions'].insert(0, {'name':'edition', 'allowed_values':['basic'], 'default':'basic'})
    result = merge([base, ours, theirs], record_schema('configuration'))
    assert [value['name'] for value in result.value['dimensions']] == ['edition','platform','region']
    assert result.value['dimensions'][1] == {'name':'platform',
        'allowed_values':['bsd','linux','mac','windows'], 'default':'linux'}


def test_disjoint_fields_of_one_key_are_combined():
    base = record_value('configuration'); ours, theirs = deepcopy(base), deepcopy(base)
    ours['dimensions'][0]['default'] = 'windows'
    theirs['dimensions'][0]['allowed_values'].append('bsd')
    result = merge([base, ours, theirs], record_schema('configuration'))
    assert result.value['dimensions'] == [{'name':'platform', 'allowed_values':['linux','windows','bsd'], 'default':'windows'}]


def test_keyed_remove_edit_keeps_whole_observations_and_stable_identity():
    base = record_value('configuration'); ours, theirs = deepcopy(base), deepcopy(base)
    ours['dimensions'] = []; theirs['dimensions'][0]['default'] = 'windows'
    result = merge([base, ours, theirs], record_schema('configuration'))
    conflict, = result.conflicts
    assert isinstance(conflict, CollectionConflict)
    assert conflict.pointer == '/dimensions' and conflict.kind == 'set_element_conflict'
    assert [key.value for key in conflict.element_keys] == ['platform']
    assert [value.value for value in (conflict.base, conflict.ours, conflict.theirs)] == [v['dimensions'] for v in (base, ours, theirs)]
    with pytest.raises(ModelError) as caught:
        _ = result.value
    assert caught.value.reason == 'unresolved_field_merge'


@pytest.mark.parametrize('position', range(3))
def test_duplicate_keys_in_any_source_are_rejected_before_shortcuts(position):
    values = [record_value('configuration') for _ in range(3)]
    values[position]['dimensions'].append(deepcopy(values[position]['dimensions'][0]))
    with pytest.raises(ModelError) as caught:
        merge(values, record_schema('configuration'))
    assert caught.value.reason == 'duplicate_merge_set_key'
    assert caught.value.pointer == '/dimensions'


def test_combination_that_violates_the_field_schema_is_withheld():
    base = record_value('configuration', dimensions=[{'name':'choice', 'allowed_values':['a','b']}], selection={'choice':'a'})
    ours, theirs = deepcopy(base), deepcopy(base)
    ours['dimensions'][0]['allowed_values'] = ['a']
    theirs['dimensions'][0]['allowed_values'] = ['b']
    result = merge([base, ours, theirs], record_schema('configuration'))
    conflict, = result.conflicts
    assert conflict.kind == 'schema_invalid_combination' and conflict.pointer == ''
    with pytest.raises(ModelError):
        _ = result.value


@pytest.mark.parametrize('identity', ['https://invalid.example/schema', '/tmp/schema.json', {}, True, 'urn:specroad:schema:0.2.0:missing'])
def test_schema_identity_is_exact_and_never_a_free_resolver(identity):
    value = domain_value('goal')
    with pytest.raises(SchemaLookupError):
        merge_fields(value, value, value, schema_id=identity)


def test_invalid_input_cannot_be_hidden_by_equal_other_sides():
    values = [domain_value('goal') for _ in range(3)]; values[0]['artifact_type'] = 'term'
    with pytest.raises(ModelError):
        merge(values, domain_schema('goal'))


def test_schema_annotation_is_inspectable_and_does_not_change_instance_fields():
    catalog = SchemaCatalog(); schema = catalog.get(domain_schema('term')['$id'])
    assert schema.schema['properties']['synonyms']['x-specroad-merge'] == {'kind':'set','key':''}
    assert schema.schema['properties']['tags']['x-specroad-merge'] == {'kind':'set','key':''}
    assert schema.metadata()['sha256'] == sha256(jcs(schema.schema)).hexdigest()
    value = domain_value('term'); before = jcs(value); schema.validate(value)
    assert jcs(value) == before and 'x-specroad-merge' not in value


def test_results_and_conflict_keys_are_detached_and_not_write_capabilities():
    base = domain_value('goal', tags=['base']); ours, theirs = deepcopy(base), deepcopy(base)
    ours['tags'].append('ours'); theirs['tags'].append('theirs')
    result = merge([base, ours, theirs], domain_schema('goal'))
    expected = deepcopy(result.value)
    ours['tags'].clear(); detached = result.value; detached['tags'].clear()
    assert result.value == expected
    with pytest.raises(TypeError):
        bool(result)
    with pytest.raises(FrozenInstanceError):
        result.conflicts = ()


def test_qualified_project_sources_feed_collection_and_attachment_candidates_without_writes(tmp_path):
    original = project(tmp_path/'seed').raw
    path = next(path for path in original if path.startswith('spec/requirements/'))
    record = json.loads(original[path]); variants = []
    for role, tags in zip(ROLES, (['base'], ['base','left'], ['base','right'])):
        files = dict(original); files[path] = jcs({**record, 'tags':tags})
        if role != 'base':
            payload_path = 'attachments/'+role+'.bin'
            raw = role.encode()+b'\x00\xff'
            attachment = AttachmentDescriptor(payload_path, 'application/octet-stream',
                len(raw), sha256(raw).hexdigest())
            # Native sources select declared attachments, not arbitrary files.
            # Add a distinct synthetic record; keep the existing recorded
            # evidence and its original attachment bytes unchanged.
            evidence = record_value('evidence',
                id='SR-EVD-'+('1' if role == 'ours' else '2')*26,
                attachments=[attachment.data])
            evidence['run_context']['run_id'] = 'test-ci:merge-'+role
            files[artifact_path('evidence', evidence['id'], 'SR')] = jcs(evidence)
            files[payload_path] = raw
        variants.append(files)
    sources = bind_files(tmp_path, variants); before = inventory(tmp_path)
    with read_only_sources():
        for role, expected in zip(ROLES, variants):
            assert getattr(sources, role).files == expected
        plan = build_merge_inventory(sources, plan_id=PLAN_ID)
        for role in ('ours', 'theirs'):
            payload_path = 'attachments/'+role+'.bin'; raw = role.encode()+b'\x00\xff'
            row = row_for(plan.data, 'attachment', payload_path)
            assert row[role]['state'] == 'present'
            assert row[role]['path'] == payload_path and row[role]['size'] == len(raw)
            assert row[role]['byte_sha256'] == row[role]['value_sha256'] == sha256(raw).hexdigest()
            assert row[role]['value_domain'] == 'bytes-v1'
            assert all(row[other]['state'] == 'absent' for other in ROLES if other != role)
        values = [json.loads(getattr(sources, role).files[path]) for role in ROLES]
        fields = merge(values, domain_schema('requirement'))
        binaries = merge_attachments(*[{p:raw for p,raw in getattr(sources, role).files.items()
                                       if p.startswith('attachments/')} for role in ROLES])
    assert fields.value['tags'] == ['base','left','right']
    assert binaries.files['attachments/ours.bin'] == b'ours\x00\xff'
    assert binaries.files['attachments/theirs.bin'] == b'theirs\x00\xff'
    for name, raw in original.items():
        if name.startswith('attachments/'):
            assert binaries.files[name] == raw
        if name.startswith('spec/evidence/'):
            assert all(getattr(sources, role).files[name] == raw for role in ROLES)
    row = row_for(plan.data, 'artifact', record['id'])
    assert row['target_classification'] == 'conflict'
    assert row['pending_reasons'] == ['semantic_planning_required']
    assert plan.ready is False and fields.ready is False and binaries.ready is False
    assert inventory(tmp_path) == before
