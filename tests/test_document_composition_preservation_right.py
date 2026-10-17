"""Preserved content, stored state and ownership under adversarial composition."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring._composition_preservation import _preserve_composition_sources
from specroad.authoring._document_validation import _document_gates
from specroad.authoring.documents import preview_section_move
from specroad.authoring.execution import execute_authoring_plan
from specroad.authoring.plans import _execution_inputs
from specroad.changes import (ChangePlan, TargetModel, PublicationAuthority, assess_change_target,
                              prepare_change_plan)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.relation_values import RelationIdentity
from specroad.validation import ModelDocument, validate_model
from specroad.changes._target_materialization import validation_resources
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from test_document_authoring import ACTOR, TIME, preview_case, saved, apply
from test_document_authoring_right import replace_model, execute, assert_failed
from test_document_composition_preservation import composition_project
from test_negative_relation_review_right import current


def reference_project(root, kind='requirement', maturity='draft'):
    """Stored state fixtures; no human approval or specialist pass is fabricated."""
    model = composition_project(root); values = model.artifacts
    original = next(value for value in values if value['id'] == ref('REQ'))
    target = original if kind == 'requirement' else record_value(kind, revision=7)
    target['maturity'] = maturity
    if kind == 'requirement': target['rationale'] = 'Preserve the original stored statement.'
    values = [value for value in values if value['id'] != ref('REQ')] + [target]
    for value in values:
        if value['artifact_type'] == 'content_block':
            value['relations'][0]['target'] = target['id']
    model = replace_model(root, model, values)
    if kind != 'requirement':
        (root / artifact_path('requirement', ref('REQ'), 'SR')).unlink()
    documents = tuple(ModelDocument(document.path,
        (json.dumps(json.loads(document.content), ensure_ascii=False, indent=3) + '\n').encode())
        for document in model.documents)
    model = TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files, **model.reservations)
    for document in documents: (root / document.path).write_bytes(document.content)
    return model, target


def evaluated(model, report):
    value = saved(report).data
    _, policy, gates = _execution_inputs(model, 'section.move', value['operations'],
        value['actor'], value['planned_at'], ())
    return assess_change_target(saved(report), model, policy=policy, gates=gates)


@pytest.mark.parametrize('case', ['move_document', 'reorder'])
@pytest.mark.parametrize('maturity', ['draft', 'approved'])
@pytest.mark.parametrize('kind', ['requirement', 'test', 'code_ref'])
def test_native_target_preserves_referenced_content_and_stored_state_without_faking_services(
        tmp_path, kind, maturity, case):
    root = tmp_path / 'project'; model, target = reference_project(root, kind, maturity)
    before = inventory(root); path = artifact_path(kind, target['id'], 'SR')
    original = model.source_files[path]
    with no_write_attempts():
        report = preview_case(model, case); assessment = evaluated(model, report)
    proposed = {document.path: document.content for document in assessment.documents}
    assert proposed[path] == original and sha256(proposed[path]).digest() == sha256(original).digest()
    assert json.loads(proposed[path]) == target
    assert target['revision'] == 7 and target['maturity'] == maturity
    assert target['id'] not in {entry['artifact']['id'] for entry in report['plan']['result_artifacts']}
    assert target['id'] not in {entry['artifact_id'] for entry in report['assessment']['lifecycle']['decisions']}
    assert not report['approval_granted'] and inventory(root) == before
    if kind == 'requirement' and maturity == 'draft':
        result = apply(root, model, report)
        assert result['write_state'] == 'committed' and result['completion']['current_target_verified']
        assert (root / path).read_bytes() == original
    else:
        stages = {stage['stage']: stage for stage in assessment.data['validation']['source_report']['stages']}
        required = {'requirement': 'review_currentness', 'test': 'evidence_currentness',
                    'code_ref': 'external_resources'}[kind]
        assert stages[required]['status'] == 'unavailable' and not assessment.target_validated
        if maturity == 'approved': assert stages['lifecycle']['status'] == 'unavailable'
        result = execute(model, report); assert_failed(result, report)
        # The generic native adapter conservatively retains unknown for a
        # TargetError; actual inventories independently establish preservation.
        assert result['write_state'] == 'unknown'
        assert result['diagnostics'][0]['reason'] == 'complete_target_validation_required'
        assert inventory(root) == before


def target_setup(root):
    model = composition_project(root, pretty=True); report = preview_case(model, 'move_document')
    return model, report, list(evaluated(model, report).documents)


def changed_document(documents, identity, change):
    result = []
    for document in documents:
        value = json.loads(document.content)
        if value['id'] == identity:
            change(value); document = ModelDocument(document.path, canonical_json_bytes(value))
        result.append(document)
    return result


@pytest.mark.parametrize('field,value', [('revision', 8), ('maturity', 'approved'),
    ('statement', 'Unrequested content edit.'), ('title', 'Unrequested title')])
def test_content_guard_rejects_artificial_revisions_and_stored_approval_edits(tmp_path, field, value):
    model, report, documents = target_setup(tmp_path / 'project')
    changed = changed_document(documents, ref('REQ'), lambda record: record.update({field: value}))
    with no_write_attempts(), pytest.raises(ModelError) as error:
        _preserve_composition_sources(model, changed, report['plan']['operations'])
    assert error.value.reason == 'document_composition_content_changed'


@pytest.mark.parametrize('field,value', [('title', 'Unrequested title'), ('purpose', 'Different purpose'),
    ('created_by', {'actor_type': 'human', 'actor_id': 'different'}),
    ('extensions', {'example.com/data': {'reference': ref('REQ')}}), ('maturity', 'approved')])
def test_owner_content_is_not_a_hidden_payload_of_a_section_move(tmp_path, field, value):
    model, report, documents = target_setup(tmp_path / 'project')
    changed = changed_document(documents, ref('DOC'), lambda record: record.update({field: value}))
    with no_write_attempts(), pytest.raises(ModelError) as error:
        _preserve_composition_sources(model, changed, report['plan']['operations'])
    assert error.value.reason == 'document_composition_owner_content_changed'


@pytest.mark.parametrize('case', ['change_position', 'drop_unrelated', 'extra_reference'])
def test_owner_relations_allow_only_the_exact_saved_contains_edit(tmp_path, case):
    model, report, documents = target_setup(tmp_path / 'project')
    def change(value):
        if case == 'change_position': value['relations'][-1]['position'] += 1
        elif case == 'drop_unrelated': value['relations'].pop(0)
        else:
            value['relations'].append({'relation_id': 'REL-' + '7' * 25 + '6',
                'id_scheme': 'random128-v1', 'type': 'references', 'target': ref('REQ'),
                'external_identities': [], 'extensions': {}})
    changed = changed_document(documents, ref('DOC', '1'), change)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        _preserve_composition_sources(model, changed, report['plan']['operations'])
    assert error.value.reason == 'document_composition_relations_changed'


@pytest.mark.parametrize('case', ['missing', 'duplicate', 'foreign_path'])
def test_preservation_guard_requires_the_exact_original_resource_inventory(tmp_path, case):
    model, report, documents = target_setup(tmp_path / 'project')
    if case == 'missing': documents.pop()
    elif case == 'duplicate': documents.append(documents[0])
    else: documents.append(ModelDocument('spec/foreign.json', documents[0].content))
    with no_write_attempts(), pytest.raises(ModelError) as error:
        _preserve_composition_sources(model, documents, report['plan']['operations'])
    assert error.value.reason == 'document_composition_inventory_changed'


def test_registered_document_gate_owns_its_original_operation_bytes(tmp_path):
    model, report, documents = target_setup(tmp_path / 'project')
    operations = deepcopy(report['plan']['operations'])
    gates = _document_gates(model, 'section.move', operations, (), block_semantics=True)
    operations[1]['relation']['position'] += 1
    with no_write_attempts():
        checked = validate_model(documents, profile=model.profile, gates=gates,
                                 resources=validation_resources(model))
    assert checked.data['model_valid'] and checked.complete
    changed = changed_document(documents, ref('DOC', '1'),
        lambda value: value['relations'][-1].update(position=operations[1]['relation']['position']))
    denied = validate_model(changed, profile=model.profile, gates=gates, resources=validation_resources(model))
    assert not denied.data['model_valid']
    assert 'document_composition_relations_changed' in {
        item['reason'] for stage in denied.data['stages'] for item in stage['diagnostics']}


def test_successive_real_moves_keep_shared_content_bytes_and_commit_each_owner_once(tmp_path):
    root = tmp_path / 'project'; model = composition_project(root, pretty=True)
    original = model.source_files; first = preview_case(model, 'move_document')
    apply(root, model, first); updated = current(root, model)
    edge = next(edge for value in updated.artifacts for edge in value['relations']
                if edge['type'] == 'contains' and edge['target'] == ref('SEC'))
    second = preview_section_move(updated, ref('SEC'), parent_id=ref('DOC'),
        relation_identity=RelationIdentity('REL-' + '7' * 25 + '5', 'random128-v1'),
        position=4, expected_relation_sha256=canonical_json_sha256(edge), reason='Move back explicitly.',
        actor=ACTOR, planned_at=TIME, change_plan_id='CP-second-move', request_id='second-move')
    assert second['target_validated']
    result = apply(root, updated, second, transaction='txn-second-move')
    assert result['write_state'] == 'committed'
    final = current(root, updated)
    owners = {ref('DOC'), ref('DOC', '1')}
    initial = {value['id']: value for value in model.artifacts}
    for value in final.artifacts:
        path = artifact_path(value['artifact_type'], value['id'], 'SR')
        if value['id'] in owners: assert value['revision'] == initial[value['id']]['revision'] + 2
        else: assert (root / path).read_bytes() == original[path]
    before = inventory(root)
    with no_write_attempts(): replay = apply(root, final, second, transaction='txn-second-replay')
    assert replay['replayed'] and replay['completion']['receipts'] == result['completion']['receipts']
    assert inventory(root) == before


@pytest.mark.parametrize('moved', [False, True])
def test_interrupted_owner_publication_never_rewrites_referenced_content(tmp_path, moved):
    root = tmp_path / 'project'; model = composition_project(root, pretty=True)
    report = preview_case(model, 'move_document'); original = model.source_files
    second = ref('DOC', '1') + '.json'; native = os.replace; calls = []
    def replace(source, destination, **kwargs):
        if str(destination) == second:
            calls.append(second)
            if moved: native(source, destination, **kwargs)
            raise OSError('injected owner publication interruption')
        return native(source, destination, **kwargs)
    authority = PublicationAuthority('owned-host', '1', lambda request: True)
    with patch.object(os, 'replace', side_effect=replace):
        result = execute(model, report, transaction='txn-owner-interrupted', authority=authority)
    assert_failed(result, report)
    assert calls == [second] and result['exit_code'] == 5 and result['write_state'] == 'unknown'
    assert result['recovery_required'] and result['diagnostics'][0]['published_count_acknowledged'] == 1
    candidates = {entry['artifact']['id']: entry['artifact'] for entry in report['plan']['result_artifacts']}
    for token in ('0', '1'):
        path = artifact_path('document', ref('DOC', token), 'SR')
        expected = canonical_json_bytes(candidates[ref('DOC', token)]) if token == '0' or moved else original[path]
        assert (root / path).read_bytes() == expected
    owners = {artifact_path('document', ref('DOC', token), 'SR') for token in ('0', '1')}
    for path, raw in original.items():
        if path not in owners: assert (root / path).read_bytes() == raw
    journal = json.loads((root / '.specroad/transactions/txn-owner-interrupted/journal.json').read_bytes())
    assert journal['state'] == 'committing' and journal['published_count'] == 1
    before = inventory(root)
    retry = execute(model, report, transaction='txn-owner-retry', authority=authority)
    assert_failed(retry, report)
    assert retry['diagnostics'][0]['reason'] == 'transaction_journal_blocks_lock' and inventory(root) == before


@pytest.mark.parametrize('field,value', [('revision', 8), ('maturity', 'approved')])
def test_rehashed_saved_plan_cannot_add_a_content_or_approval_write(tmp_path, field, value):
    root = tmp_path / 'project'; model = composition_project(root); report = preview_case(model, 'move_document')
    data = saved(report).data; data.pop('change_plan_sha256')
    target = next(artifact for artifact in model.artifacts if artifact['id'] == ref('REQ'))
    target[field] = value
    if field == 'maturity': target['rationale'] = 'Stored approval payload must not be smuggled.'
    data['result_artifacts'].append({'artifact': target, 'sha256': canonical_json_sha256(target)})
    replacements = {entry['artifact']['id']: entry['artifact'] for entry in data['result_artifacts']}
    after = [replacements.get(artifact['id'], artifact) for artifact in model.artifacts]
    data['expected_result']['model_root_sha256'] = model.manifest(after, data['base']['scope_descriptor']).sha256
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        prepare_change_plan(data)
    assert error.value.reason == 'result_owner_set_mismatch'
    # Even a correctly rehashed external plan is refused at the parser before
    # a typed plan can reach the native writer or any publication authority.
    data['change_plan_sha256'] = canonical_json_sha256(data)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        ChangePlan(canonical_json_bytes(data))
    assert error.value.reason == 'result_owner_set_mismatch' and inventory(root) == before
