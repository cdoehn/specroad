"""Whole-graph cycle admission and source-bound repeated document occurrences."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.documents import (DocumentComposition, DocumentIncludeCycleError,
                               compose_document)
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from support.domain import relation
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import block_value, record_value, ref
from support.targets import model, SCOPE


def edge(kind, target, number, position=0):
    value = {**relation(kind, target), 'relation_id': f'REL-{number:026d}'}
    if kind == 'contains': value['position'] = position
    return value


def include_project(mode='content'):
    destination = ref('DOC', '1') if mode == 'content' else ref('SEC', '1')
    values = [record_value('document', relations=[edge('contains', ref('SEC'), 0)]),
        record_value('document', id=ref('DOC', '1'), document_role='supporting',
                     relations=[edge('contains', ref('SEC', '1'), 1)]),
        record_value('section', relations=[edge('contains', ref('BLOCK', '1'), 3, 1),
                                          edge('contains', ref('BLOCK'), 2, 0)]),
        record_value('section', id=ref('SEC', '1'), relations=[edge('contains', ref('BLOCK', '2'), 4)])]
    for number in range(2):
        block = block_value('include_document'); block['id'] = ref('BLOCK', str(number))
        block['payload']['mode'] = mode; block['relations'] = [edge('references', destination, 5 + number)]
        values.append(block)
    block = block_value('prose'); block['id'] = ref('BLOCK', '2'); block['payload']['markdown'] = 'Owned content'
    values.append(block)
    return values


def occurrence_ids(result):
    return [row['artifact_id'] for row in result.data['occurrences']]


@pytest.mark.parametrize('mode', ['content', 'section'])
def test_repeated_includes_expand_every_occurrence_from_the_same_native_records(mode):
    supplied = model(include_project(mode))
    with no_write_attempts(): result = compose_document(supplied, ref('DOC'))
    suffix = ([ref('DOC', '1')] if mode == 'content' else []) + [ref('SEC', '1'), ref('BLOCK', '2')]
    expected = [ref('DOC'), ref('SEC'), ref('BLOCK'), *suffix, ref('BLOCK', '1'), *suffix]
    assert occurrence_ids(result) == expected
    data = result.data; rows = data['occurrences']
    assert data['occurrence_count'] == len(expected) and len(data['records']) == len(set(expected))
    assert [r['occurrence_index'] for r in rows] == list(range(len(expected)))
    assert rows[0]['parent_occurrence'] is None and rows[0]['depth'] == 0 and rows[0]['via'] is None
    for row in rows[1:]:
        parent = rows[row['parent_occurrence']]
        assert row['depth'] == parent['depth'] + 1
        assert row['via']['source_id'] == parent['artifact_id']
        assert row['via']['target_id'] == row['artifact_id']
        raw = supplied.source_files[row['via']['path']]; source = json.loads(raw)
        relation_index = int(row['via']['pointer'].split('/')[-1])
        assert row['via']['relation'] == source['relations'][relation_index]
        assert row['via']['relation_sha256'] == canonical_json_sha256(row['via']['relation'])
        assert row['via']['source_sha256'] == sha256(raw).hexdigest()
    assert [r['include_mode'] for r in data['include_edges']] == [mode, mode]
    assert data['scope_descriptor'] == SCOPE
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert data['input_sha256'] == supplied._sources_sha256
    for ident, bound in data['records'].items():
        raw = supplied.source_files[bound['path']]
        assert bound['record'] == json.loads(raw) and bound['record']['id'] == ident
        assert bound['source_sha256'] == sha256(raw).hexdigest()
        assert bound['record_sha256'] == canonical_json_sha256(bound['record'])
        assert result.source_files[bound['path']] == raw


@pytest.mark.parametrize('rotation', range(7))
def test_input_file_order_does_not_change_composition_or_cycle_graph(rotation):
    values = include_project(); expected = compose_document(model(values), ref('DOC'))
    actual = compose_document(model(values[rotation:] + values[:rotation]), ref('DOC'))
    assert actual.data == expected.data and actual.sha256 == expected.sha256


def test_contains_positions_control_occurrences_without_rewriting_source_relations():
    values = include_project(); first = compose_document(model(values), ref('DOC'))
    assert values[2]['relations'][0]['target'] == ref('BLOCK', '1')
    values[2]['relations'][0]['position'] = 0  # tie uses full target then relation ID
    second = compose_document(model(values), ref('DOC'))
    assert occurrence_ids(first) == occurrence_ids(second)
    values[2]['relations'][1]['position'] = 2
    changed = compose_document(model(values), ref('DOC'))
    assert occurrence_ids(changed)[2] == ref('BLOCK', '1')
    assert changed.data['records'][ref('BLOCK', '2')]['record'] == first.data['records'][ref('BLOCK', '2')]['record']


@pytest.mark.parametrize('mode', ['content', 'section'])
def test_direct_self_include_is_rejected_with_actual_cycle_sources_before_expansion(mode):
    values = include_project(mode)
    values[4]['relations'][0]['target'] = ref('DOC') if mode == 'content' else ref('SEC')
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises(DocumentIncludeCycleError) as caught:
        compose_document(supplied, ref('DOC'))
    issue = caught.value.diagnostic()
    assert issue['reason'] == 'document_include_cycle' and caught.value.exit_code == 3
    assert issue['artifact_ids'][0] == issue['artifact_ids'][-1]
    assert set(issue['artifact_ids']) == ({ref('BLOCK'), ref('SEC'), ref('DOC')} if mode == 'content'
                                        else {ref('BLOCK'), ref('SEC')})
    assert len(issue['edges']) == len(issue['relation_ids']) == len(issue['artifact_ids']) - 1
    for position, witness in enumerate(issue['edges']):
        assert (witness['source_id'], witness['target_id']) == tuple(issue['artifact_ids'][position:position+2])
        raw = supplied.source_files[witness['path']]; original = json.loads(raw)
        assert witness['relation'] == original['relations'][int(witness['pointer'].split('/')[-1])]
        assert witness['source_sha256'] == sha256(raw).hexdigest()
    assert supplied.source_files == before


def test_transitive_document_cycle_is_deterministic_and_never_returns_partial_composition():
    values = include_project(); values[-1]['block_kind'] = 'include_document'
    values[-1]['payload'] = {'mode': 'content'}; values[-1]['relations'] = [edge('references', ref('DOC'), 7)]
    diagnostics = []
    for sources in (values, list(reversed(values))):
        with no_write_attempts(), pytest.raises(DocumentIncludeCycleError) as caught:
            compose_document(model(sources), ref('DOC'))
        diagnostics.append(caught.value.diagnostic())
    assert diagnostics[0] == diagnostics[1]
    assert set(diagnostics[0]['artifact_ids']) == {ref('DOC'), ref('SEC'), ref('BLOCK'),
                                                 ref('DOC', '1'), ref('SEC', '1'), ref('BLOCK', '2')}


@pytest.mark.parametrize('failure', ['missing_target', 'missing_reference', 'wrong_target_kind'])
def test_missing_or_wrong_include_target_has_no_external_or_title_based_fallback(failure):
    values = include_project()
    if failure == 'missing_target': values[4]['relations'][0]['target'] = ref('DOC', '2')
    elif failure == 'missing_reference': values[4]['relations'] = []
    else: values[4]['relations'][0]['target'] = ref('SEC', '1')
    with no_write_attempts(), pytest.raises(ModelError): compose_document(model(values), ref('DOC'))


def test_unowned_section_prevents_composition_even_for_an_otherwise_valid_selected_document():
    values = include_project() + [record_value('section', id=ref('SEC', '2'))]
    with no_write_attempts(), pytest.raises(ModelError) as caught: compose_document(model(values), ref('DOC'))
    assert caught.value.reason == 'document_section_parent_cardinality'


def test_regular_artifact_reference_to_an_ancestor_is_not_an_include_edge():
    values = include_project(); values[-1]['block_kind'] = 'artifact_ref'
    values[-1]['payload'] = {'render_mode': 'link'}; values[-1]['relations'] = [edge('references', ref('DOC'), 7)]
    with no_write_attempts(): result = compose_document(model(values), ref('DOC'))
    assert len(result.data['include_edges']) == 2
    assert occurrence_ids(result).count(ref('DOC')) == 1
    assert occurrence_ids(result).count(ref('BLOCK', '2')) == 2


def test_changed_included_content_updates_every_new_occurrence_without_revising_owners():
    values = include_project(); first = compose_document(model(values), ref('DOC')); old = first.data
    changed = deepcopy(values); changed[-1]['payload']['markdown'] = 'New owned content'; changed[-1]['revision'] = 2
    second = compose_document(model(changed), ref('DOC'))
    rows = [r for r in second.data['occurrences'] if r['artifact_id'] == ref('BLOCK', '2')]
    assert len(rows) == 2 and all(r['revision'] == 2 for r in rows)
    assert second.data['records'][ref('BLOCK', '2')]['record'] == changed[-1]
    for ident in (ref('DOC'), ref('SEC'), ref('BLOCK'), ref('BLOCK', '1')):
        assert first.data['records'][ident] == second.data['records'][ident]
    assert second.data['model_root_sha256'] != old['model_root_sha256'] and first.data == old


def test_long_acyclic_include_chain_has_flat_occurrence_ancestry_and_complete_sources():
    count = 48; values = []
    def ident(prefix, n): return f'SR-{prefix}-{n:026d}'
    for number in range(count):
        values.append(record_value('document', id=ident('DOC', number),
            document_role='primary_specification' if number == 0 else 'supporting',
            relations=[edge('contains', ident('SEC', number), number * 3)]))
        values.append(record_value('section', id=ident('SEC', number),
            relations=[edge('contains', ident('BLOCK', number), number * 3 + 1)]))
        block = block_value('include_document' if number + 1 < count else 'prose')
        block['id'] = ident('BLOCK', number)
        if number + 1 < count: block['relations'] = [edge('references', ident('DOC', number + 1), number * 3 + 2)]
        values.append(block)
    with no_write_attempts(): result = compose_document(model(values), ident('DOC', 0))
    rows = result.data['occurrences']
    assert len(rows) == len(result.source_files) == count * 3
    assert [r['depth'] for r in rows] == list(range(count * 3))
    assert [r['parent_occurrence'] for r in rows] == [None, *range(count * 3 - 1)]
    assert rows[-1]['artifact_id'] == ident('BLOCK', count - 1)


def test_empty_document_composes_its_bound_root_without_inventing_sections_or_primary_approval():
    supplied = model([record_value('document', document_role='supporting')])
    with no_write_attempts(): result = compose_document(supplied, ref('DOC'))
    assert occurrence_ids(result) == [ref('DOC')] and result.data['include_edges'] == []
    assert not result.data['primary_role_checked']


def test_passive_block_payload_is_not_executed_or_presented_as_semantically_valid():
    values = include_project(); values[-1]['block_kind'] = 'query'
    values[-1]['payload'] = {'query': {'external_loader': 'execute()'}, 'columns': [{}], 'empty_policy': 'omit'}
    with no_write_attempts(): result = compose_document(model(values), ref('DOC'))
    assert result.data['records'][ref('BLOCK', '2')]['record']['payload'] == values[-1]['payload']
    assert not result.data['payload_semantics_checked'] and not result.data['rendering_performed']


def test_composition_and_source_files_are_detached_and_never_claim_full_or_write_approval():
    result = compose_document(model(include_project()), ref('DOC')); expected = result.data
    result.data['occurrences'].clear(); result.data['records'].clear(); result.source_files.clear()
    assert result.data == expected and result.sha256 == canonical_json_sha256(expected)
    assert result.source_files and expected['validation_scope'] == 'supplied_snapshot_document_composition'
    assert all(expected[k] for k in ('document_structure_checked', 'include_graph_checked', 'include_graph_acyclic'))
    assert not any(expected[k] for k in ('project_files_verified','full_validation_passed','primary_role_checked',
        'payload_semantics_checked','rendering_performed','write_authorized','approval_granted'))
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(TypeError): DocumentComposition()


def test_actual_source_files_are_unchanged_and_later_removal_cannot_replace_owned_input(tmp_path):
    supplied = model(include_project()); path = tmp_path / 'owned.json'
    path.write_bytes(supplied.documents[0].content); before = inventory(tmp_path)
    with no_write_attempts(): first = compose_document(supplied, ref('DOC'))
    assert inventory(tmp_path) == before
    path.unlink()
    with no_write_attempts(): second = compose_document(supplied, ref('DOC'))
    assert first.data == second.data and not path.exists()


@pytest.mark.parametrize('selector', [None, False, '', ref('DOC', '2'), ref('SEC')])
def test_invalid_document_selector_never_falls_back_to_another_document(selector):
    with no_write_attempts(), pytest.raises(ModelError): compose_document(model(include_project()), selector)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_include_composition_runs_with_identical_occurrences_and_bindings_in_core_and_pyz(tmp_path, mode):
    supplied = model(include_project()); expected = compose_document(supplied, ref('DOC')).data
    body = '''import json
from specroad.documents import compose_document
from specroad.changes import TargetModel
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
'''
    body += 'print(json.dumps(compose_document(owned,' + repr(ref('DOC')) + ').data,sort_keys=True))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
