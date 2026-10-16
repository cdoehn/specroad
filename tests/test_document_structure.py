"""Source-owned section parents and deterministic data composition; no rendering."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import shutil

import pytest

from specroad.documents import (DocumentStructureAssessment, DocumentStructureError,
                               assess_document_structure)
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from support.domain import domain_value, relation
from support.inspection import inspection_project
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.targets import model, SCOPE
from test_document_roles import document


def contains(target, token, position=0):
    return {**relation('contains', target), 'relation_id': 'REL-' + token * 26,
            'position': position}


def section(token='0', **changes):
    return record_value('section', id=ref('SEC', token), **changes)


def block(token='0', **changes):
    return record_value('content_block', id=ref('BLOCK', token), **changes)


def composed_records():
    return [document(relations=[contains(ref('SEC'), '0', 7), contains(ref('SEC', '2'), '1', 0)]),
        section(relations=[contains(ref('SEC', '1'), '2', 2), contains(ref('BLOCK', '1'), '3', 0)]),
        section('1', relations=[contains(ref('BLOCK'), '4', 0)]), section('2'),
        block(), block('1'), domain_value('goal')]


def test_nested_composition_binds_actual_sources_and_stored_parent_relations():
    supplied = model(composed_records())
    with no_write_attempts(): report = assess_document_structure(supplied)
    data = report.data; result = report.require_document(ref('DOC'))
    assert report.structure_valid and data['document_fields_valid'] and data['diagnostics'] == []
    assert result['root_section_ids'] == [ref('SEC', '2'), ref('SEC')]
    assert [(r['artifact_id'], r['depth'], r['parent_id']) for r in result['preorder']] == [
        (ref('SEC', '2'), 0, ref('DOC')), (ref('SEC'), 0, ref('DOC')),
        (ref('BLOCK', '1'), 1, ref('SEC')), (ref('SEC', '1'), 1, ref('SEC')),
        (ref('BLOCK'), 2, ref('SEC', '1'))]
    assert data['section_owners'] == [
        {'section_id': ref('SEC'), 'parent_id': ref('DOC'), 'relation_id': 'REL-' + '0' * 26},
        {'section_id': ref('SEC', '1'), 'parent_id': ref('SEC'), 'relation_id': 'REL-' + '2' * 26},
        {'section_id': ref('SEC', '2'), 'parent_id': ref('DOC'), 'relation_id': 'REL-' + '1' * 26}]
    for rows in data['children'].values():
        for row in rows:
            assert row['relation_sha256'] == canonical_json_sha256(row['relation'])
            assert row['position'] == row['relation']['position']
            assert row['artifact_id'] == row['relation']['target']
    for row in data['source_bindings']:
        assert row['source_sha256'] == sha256(supplied.source_files[row['path']]).hexdigest()
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert data['input_sha256'] == supplied._sources_sha256 and data['scope_descriptor'] == SCOPE
    assert not any(data[k] for k in ('project_files_verified', 'full_validation_passed',
        'primary_role_checked', 'include_graph_checked', 'payload_semantics_checked',
        'rendering_performed', 'write_authorized', 'approval_granted'))


@pytest.mark.parametrize('shift', range(7))
def test_supplied_file_order_cannot_change_nested_composition(shift):
    records = composed_records(); expected = assess_document_structure(model(records))
    records = records[shift:] + records[:shift]
    actual = assess_document_structure(model(records))
    assert actual.data == expected.data and actual.sha256 == expected.sha256


def test_relation_array_order_changes_source_binding_but_not_composition():
    records = composed_records(); before = assess_document_structure(model(records))
    for record in records: record['relations'].reverse()
    after = assess_document_structure(model(records))
    assert after.require_document(ref('DOC')) == before.require_document(ref('DOC'))
    assert after.data['children'] == before.data['children']
    assert after.data['input_sha256'] != before.data['input_sha256']


def test_position_change_changes_traversal_without_revising_referenced_content():
    records = composed_records(); original = deepcopy(records)
    before = assess_document_structure(model(records))
    records[0]['relations'][0]['position'] = 0
    records[0]['relations'][1]['position'] = 7
    after = assess_document_structure(model(records))
    assert after.require_document(ref('DOC'))['root_section_ids'] == [ref('SEC'), ref('SEC', '2')]
    assert before.require_document(ref('DOC'))['root_section_ids'] == [ref('SEC', '2'), ref('SEC')]
    assert records[1:] == original[1:]


def test_equal_positions_use_target_then_relation_id_without_collapsing_occurrences():
    records = [document(relations=[contains(ref('SEC'), '0')]),
        section(relations=[contains(ref('BLOCK', '1'), '3'),
            contains(ref('BLOCK'), '2'), contains(ref('BLOCK'), '1')]), block(), block('1')]
    report = assess_document_structure(model(records)); children = report.data['children'][ref('SEC')]
    assert [r['artifact_id'] for r in children] == [ref('BLOCK'), ref('BLOCK'), ref('BLOCK', '1')]
    assert [r['relation_id'] for r in children] == ['REL-' + t * 26 for t in ('1', '2', '3')]
    assert [r['position'] for r in children] == [0, 0, 0]
    assert [r['relation_id'] for r in report.require_document(ref('DOC'))['preorder'][1:]] == [r['relation_id'] for r in children]


@pytest.mark.parametrize('parents', [0, 2])
def test_section_requires_exactly_one_stored_incoming_relation(parents):
    records = [section()]
    for i in range(parents):
        token = str(i)
        records.append(document(token, document_role='supporting', relations=[contains(ref('SEC'), token)]))
    report = assess_document_structure(model(records)); data = report.data
    assert not report.structure_valid and data['documents'] is None and data['children'] is None
    issue, = data['diagnostics']
    assert issue['reason'] == 'document_section_parent_cardinality'
    assert issue['artifact_id'] == ref('SEC') and issue['parent_count'] == parents
    assert len(issue['relation_ids']) == parents
    with pytest.raises(DocumentStructureError) as error: report.require_document(ref('DOC'))
    assert error.value.exit_code == 3 and error.value.reason == issue['reason']


def test_two_contains_edges_from_the_same_parent_do_not_count_as_one_owner():
    records = [document(relations=[contains(ref('SEC'), '0'), contains(ref('SEC'), '1')]), section()]
    report = assess_document_structure(model(records)); issue, = report.data['diagnostics']
    assert issue['reason'] == 'document_section_parent_cardinality' and issue['parent_count'] == 2
    assert issue['related_ids'] == [ref('DOC'), ref('DOC')]


def test_native_cycle_rejection_prevents_unrooted_recursive_composition():
    records = [document(), section(relations=[contains(ref('SEC', '1'), '0')]),
        section('1', relations=[contains(ref('SEC'), '1')])]
    report = assess_document_structure(model(records)); issue, = report.data['diagnostics']
    assert issue['reason'] == 'relation_hierarchy_cycle' and issue['relation_type'] == 'contains'
    assert not report.structure_valid and report.data['documents'] is None


def test_missing_contains_target_retains_the_native_reference_diagnostic():
    supplied = model([document(relations=[contains(ref('SEC'), '0')])])
    report = assess_document_structure(supplied); issue, = report.data['diagnostics']
    assert issue['reason'] == 'missing_relation_target'
    assert issue['path'] == supplied.documents[0].path and issue['pointer'] == '/relations/0/target'
    assert not report.structure_valid and report.data['documents'] is None


def test_noncontains_reference_is_not_a_child_or_a_section_owner():
    edge = relation('references', ref('GOAL')); edge['relation_id'] = 'REL-' + '5' * 26
    records = composed_records(); records[4]['relations'].append(edge)
    report = assess_document_structure(model(records))
    assert report.structure_valid
    assert ref('GOAL') not in [r['artifact_id'] for r in report.require_document(ref('DOC'))['preorder']]


def test_missing_document_fields_block_structure_before_parent_cardinality():
    broken = document(); broken.pop('purpose')
    supplied = model([broken, section()])
    report = assess_document_structure(supplied); issue, = report.data['diagnostics']
    assert issue['reason'] == 'missing_field' and issue['pointer'] == '/purpose'
    assert issue['artifact_id'] == broken['id']
    assert not report.data['document_fields_valid'] and not report.structure_valid
    assert report.data['section_owners'] is None and report.data['documents'] is None


def test_empty_document_is_valid_structure_without_claiming_a_primary_role():
    report = assess_document_structure(model([document(document_role='supporting')]))
    assert report.structure_valid
    assert report.require_document(ref('DOC')) == {'document_id': ref('DOC'), 'revision': 1,
        'root_section_ids': [], 'preorder': []}
    assert not report.data['primary_role_checked']


def test_owned_report_and_returned_traversal_cannot_be_mutated_into_other_evidence():
    report = assess_document_structure(model(composed_records())); digest = report.sha256
    report.require_document(ref('DOC'))['preorder'].clear()
    report.data['section_owners'].clear()
    assert report.sha256 == digest and report.require_document(ref('DOC'))['preorder']
    with pytest.raises(FrozenInstanceError): report._encoded = b'{}'
    with pytest.raises(TypeError): bool(report)
    with pytest.raises(TypeError): DocumentStructureAssessment(report.data)


def test_owned_project_structure_is_read_only_and_independent_of_later_disk_changes(tmp_path):
    root = tmp_path / 'project'; supplied = inspection_project(root, artifacts=composed_records())
    before = inventory(tmp_path)
    with no_write_attempts(): expected = assess_document_structure(supplied)
    assert inventory(tmp_path) == before
    shutil.rmtree(root)
    with no_write_attempts(): actual = assess_document_structure(supplied)
    assert actual.data == expected.data and not root.exists()


@pytest.mark.parametrize('value', [None, {}, [], object()], ids=['none', 'mapping', 'sequence', 'object'])
def test_structure_requires_an_owned_target_model(value):
    with no_write_attempts(), pytest.raises(ModelError) as error: assess_document_structure(value)
    assert error.value.reason == 'document_target_model_required'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_document_structure_contract_runs_in_isolated_core_and_pyz(tmp_path, mode):
    supplied = model(composed_records()); expected = assess_document_structure(supplied).data
    body = '''import json
from specroad.documents import assess_document_structure
from specroad.changes import TargetModel
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'configuration=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += '''profile=ProfileResource(dict(resources)['profiles/core.json'])
supplied=TargetModel(configuration,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key),
 resource_files=[ModelDocument(p,b) for p,b in resources])
print(json.dumps(assess_document_structure(supplied).data,sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
