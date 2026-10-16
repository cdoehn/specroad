"""Exact conflicting source bindings, full-scope admission and native edge cases."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.documents import DocumentStructureError, assess_document_structure
from specroad.changes import TargetModel
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument, validate_model
from support.domain import relation
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import record_value, ref
from support.scopes import descriptor
from support.targets import model, SCOPE
from test_document_roles import document
from test_document_structure import block, composed_records, contains, section


@pytest.mark.parametrize('same_parent', [False, True])
def test_conflicting_parents_bind_original_source_paths_pointers_and_relation_bytes(same_parent):
    first = contains(ref('SEC'), '1', 4); second = contains(ref('SEC'), '0', 2)
    records = [document(relations=[first]), section()]
    if same_parent: records[0]['relations'].append(second)
    else: records.append(document('1', document_role='supporting', relations=[second]))
    supplied = model(records); report = assess_document_structure(supplied)
    issue, = report.data['diagnostics']; assert issue['parent_count'] == 2
    assert issue['reason'] == 'document_section_parent_cardinality'
    actual = issue['incoming_relations']; assert len(actual) == 2
    for row in actual:
        raw = supplied.source_files[row['path']]; value = json.loads(raw)
        position = int(row['pointer'].split('/')[-1])
        assert row['source_id'] == value['id'] and row['relation'] == value['relations'][position]
        assert row['source_sha256'] == sha256(raw).hexdigest()
        assert row['relation_sha256'] == canonical_json_sha256(row['relation'])
        assert row['relation']['target'] == ref('SEC')
    if same_parent:
        assert [r['pointer'] for r in actual] == ['/relations/1', '/relations/0']
    assert report.data['section_owners'] is None and report.data['documents'] is None


def test_orphan_diagnostic_has_no_invented_parent_or_incoming_relation():
    report = assess_document_structure(model([document(), section()]))
    issue, = report.data['diagnostics']
    assert issue['parent_count'] == 0 and issue['incoming_relations'] == []
    assert issue['related_ids'] == issue['relation_ids'] == []


@pytest.mark.parametrize('position', [-1, -0.5, True, False, None, '0', []])
def test_invalid_positions_are_refused_by_the_native_model_before_structure(position):
    records = [document(relations=[contains(ref('SEC'), '0', position)]), section()]
    with no_write_attempts(), pytest.raises(ModelError) as error: model(records)
    assert error.value.reason == 'invalid_relation_position'
    assert error.value.pointer == '/relations/0/position'


def test_missing_position_is_not_replaced_with_an_implicit_zero():
    edge = contains(ref('SEC'), '0'); edge.pop('position')
    with no_write_attempts(), pytest.raises(ModelError) as error:
        model([document(relations=[edge]), section()])
    assert error.value.reason == 'invalid_relation_position'


@pytest.mark.parametrize('position', [0.0, 1.0])
def test_document_field_contract_keeps_integer_positions_stricter_than_generic_edges(position):
    records = [document(relations=[contains(ref('SEC'), '0', position)]), section()]
    base = model(records); by_id = {record['id']: record for record in records}
    # The normal fixture uses canonical JSON, which converts integral floats
    # to integer spelling. Supply actual decimal-spelled bytes for this case.
    sources = [ModelDocument(d.path, json.dumps(by_id[json.loads(d.content)['id']]).encode())
               for d in base.documents]
    supplied = TargetModel(base.configuration_bytes, base.binding, sources,
                           profile=base.profile, resource_files=base.resource_files)
    report = assess_document_structure(supplied); issue, = report.data['diagnostics']
    assert issue['reason'] == 'invalid_contains_position' and issue['pointer'] == '/relations/0/position'
    assert not report.structure_valid and not report.data['document_fields_valid']
    assert report.data['section_owners'] is None


def test_equal_document_root_positions_use_full_target_ids_without_rewriting_relations():
    records = [document(relations=[contains(ref('SEC', '1'), '0'), contains(ref('SEC'), '1')]),
        section('1'), section()]; original = deepcopy(records)
    report = assess_document_structure(model(records))
    assert report.require_document(ref('DOC'))['root_section_ids'] == [ref('SEC'), ref('SEC', '1')]
    assert records == original
    assert [r['relation_id'] for r in report.data['children'][ref('DOC')]] == ['REL-'+'1'*26, 'REL-'+'0'*26]


@pytest.mark.parametrize('maturity', ['draft', 'retired'])
def test_section_maturity_does_not_silently_remove_its_parent_requirement(maturity):
    report = assess_document_structure(model([document(), section(maturity=maturity)]))
    issue, = report.data['diagnostics']
    assert issue['reason'] == 'document_section_parent_cardinality' and issue['parent_count'] == 0


def test_retired_parent_edge_is_still_a_stored_second_owner():
    records = [document(relations=[contains(ref('SEC'), '0')]), section(),
        document('1', maturity='retired', relations=[contains(ref('SEC'), '1')])]
    report = assess_document_structure(model(records)); issue, = report.data['diagnostics']
    assert issue['parent_count'] == 2 and len(issue['incoming_relations']) == 2


def test_multiple_documents_keep_separate_roots_and_nested_ownership():
    records = composed_records() + [document('1', document_role='supporting',
        relations=[contains(ref('SEC', '3'), '5')]), section('3')]
    report = assess_document_structure(model(records))
    assert report.structure_valid
    assert report.require_document(ref('DOC', '1'))['root_section_ids'] == [ref('SEC', '3')]
    assert report.require_document(ref('DOC'))['root_section_ids'] == [ref('SEC', '2'), ref('SEC')]
    assert len(report.require_document(ref('DOC', '1'))['preorder']) == 1


def test_unowned_section_in_another_part_of_the_inventory_blocks_document_selection():
    records = composed_records() + [section('3')]
    report = assess_document_structure(model(records))
    with pytest.raises(DocumentStructureError) as error: report.require_document(ref('DOC'))
    assert error.value.reason == 'document_section_parent_cardinality'
    assert report.data['diagnostics'][0]['artifact_id'] == ref('SEC', '3')


def test_deep_section_chain_is_reported_as_bound_flat_data():
    count = 96; ids = [f'SR-SEC-{i:026d}' for i in range(count)]
    def edge(target, number):
        return {**relation('contains', target), 'relation_id': f'REL-{number:026d}', 'position': 0}
    records = [document(relations=[edge(ids[0], 0)])]
    records += [record_value('section', id=identity,
        relations=[edge(ids[i+1], i+1)] if i+1 < count else []) for i, identity in enumerate(ids)]
    report = assess_document_structure(model(records)); traversal = report.require_document(ref('DOC'))['preorder']
    assert [row['artifact_id'] for row in traversal] == ids
    assert [row['depth'] for row in traversal] == list(range(count))
    assert traversal[-1]['parent_id'] == ids[-2]
    assert len(report.data['section_owners']) == count


def test_duplicate_relation_identity_is_a_native_error_not_a_parent_count_result():
    records = [document(relations=[contains(ref('SEC'), '0')]), section(), section('1'),
        document('1', document_role='supporting', relations=[contains(ref('SEC', '1'), '0')])]
    report = assess_document_structure(model(records)); issue, = report.data['diagnostics']
    assert issue['reason'] == 'duplicate_relation_id'
    assert not report.structure_valid and report.data['section_owners'] is None


def test_invalid_document_to_block_contains_pair_preserves_native_field_diagnostic():
    supplied = model([document(relations=[contains(ref('BLOCK'), '0')]), block()])
    report = assess_document_structure(supplied); issue, = report.data['diagnostics']
    assert issue['reason'] == 'invalid_contains_target' and issue['pointer'] == '/relations/0/target'
    assert not report.structure_valid


@pytest.mark.parametrize('scope', [descriptor('document', {'document_id': ref('DOC')}),
    descriptor('project', boundary_policy='partial'), descriptor('specification'),
    descriptor('project', configuration_id=ref('CFG'))])
def test_partial_configured_or_other_scope_cannot_claim_full_section_ownership(scope):
    supplied = model(composed_records())
    with no_write_attempts(), pytest.raises(DocumentStructureError) as error:
        assess_document_structure(supplied, scope_descriptor=scope)
    assert error.value.reason == 'document_structure_full_project_scope_required'
    assert error.value.pointer == '/scope_descriptor' and error.value.exit_code == 3


def test_explicit_full_scope_preserves_default_observation_and_is_owned():
    supplied = model(composed_records()); scope = deepcopy(SCOPE)
    expected = assess_document_structure(supplied)
    actual = assess_document_structure(supplied, scope_descriptor=scope)
    scope['boundary_policy'] = 'partial'
    assert actual.data == expected.data and actual.sha256 == expected.sha256


@pytest.mark.parametrize('value', [None, False, [], {}])
def test_document_selector_requires_a_string_identity(value):
    report = assess_document_structure(model(composed_records()))
    with pytest.raises(ModelError) as error: report.require_document(value)
    assert error.value.reason == 'document_id_required'


@pytest.mark.parametrize('value', ['', ref('SEC'), ref('DOC', '1')])
def test_unknown_or_wrong_kind_document_identity_never_selects_a_fallback(value):
    report = assess_document_structure(model(composed_records()))
    with pytest.raises(DocumentStructureError) as error: report.require_document(value)
    assert error.value.reason == 'document_not_found' and error.value.exit_code == 3


def test_current_record_revision_changes_binding_but_does_not_rewrite_prior_observation():
    records = composed_records(); first = assess_document_structure(model(records))
    records[0].update(revision=2, title='Changed document')
    second = assess_document_structure(model(records))
    assert first.require_document(ref('DOC'))['revision'] == 1
    assert second.require_document(ref('DOC'))['revision'] == 2
    assert first.data['model_root_sha256'] != second.data['model_root_sha256']
    assert first.data['input_sha256'] != second.data['input_sha256']
    assert first.require_document(ref('DOC'))['preorder'] == second.require_document(ref('DOC'))['preorder']


def test_mutated_model_source_bytes_cannot_reuse_the_original_model_binding():
    supplied = model(composed_records()); source = supplied.documents[0]
    changed = json.loads(source.content); changed['title'] = 'Foreign replacement'
    object.__setattr__(supplied, 'documents', (ModelDocument(source.path, canonical_json_bytes(changed)),
                                             *supplied.documents[1:]))
    with no_write_attempts(), pytest.raises(ModelError) as error: assess_document_structure(supplied)
    assert error.value.reason == 'target_sources_changed'


def test_valid_structure_does_not_supply_unavailable_complete_document_semantics():
    supplied = model(composed_records()); structure = assess_document_structure(supplied)
    report = validate_model(supplied.documents, profile=supplied.profile)
    assert structure.structure_valid and not structure.data['full_validation_passed']
    assert not report.passed
    assert next(row for row in report.data['stages'] if row['stage'] == 'document_model')['status'] == 'unavailable'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_parent_conflict_source_contract_runs_in_isolated_core_and_pyz(tmp_path, mode):
    supplied = model([document(relations=[contains(ref('SEC'), '1'), contains(ref('SEC'), '0')]), section()])
    expected = assess_document_structure(supplied, scope_descriptor=SCOPE).data
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
    body += 'scope=' + repr(SCOPE) + '\n'
    body += '''profile=ProfileResource(dict(resources)['profiles/core.json'])
supplied=TargetModel(configuration,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key),
 resource_files=[ModelDocument(p,b) for p,b in resources])
print(json.dumps(assess_document_structure(supplied,scope_descriptor=scope).data,sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
