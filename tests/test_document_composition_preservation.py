"""Actual section moves preserve referenced records and exact source bytes."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.authoring.execution import execute_authoring_plan
from specroad.changes import PublicationAuthority
from specroad.documents import compose_document, resolve_artifact_reference
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument, ModelGate
from specroad.changes import TargetModel
from support.domain import domain_value, relation
from support.read_only import inventory, no_write_attempts
from support.records import block_value, ref
from test_document_authoring import ACTOR, TIME, document_project, preview_case, saved, apply
from test_document_authoring_right import replace_model, reasons
from test_document_mutations import assert_stored, confirm_and_replay
from test_document_structure import contains
from test_negative_relation_review_right import current


def composition_project(root, *, pretty=False):
    model = document_project(root); values = model.artifacts
    for value in values:
        if value['id'] == ref('SEC'): value['relations'].append(contains(ref('BLOCK'), '4', 7))
        if value['id'] == ref('SEC', '1'): value['relations'].append(contains(ref('BLOCK', '1'), '5', 1))
    for token, edge in (('0', '6'), ('1', '7')):
        block = block_value('artifact_ref'); block['id'] = ref('BLOCK', token); block['revision'] = 3
        block['relations'] = [{**relation('references', ref('REQ')), 'relation_id': 'REL-' + edge * 26}]
        values.append(block)
    values.append(domain_value('requirement', revision=7, title='Gemeinsam referenzierter Inhalt'))
    model = replace_model(root, model, values)
    if pretty:
        documents = [ModelDocument(document.path,
            (json.dumps(json.loads(document.content), ensure_ascii=False, indent=3) + '\n').encode())
            for document in model.documents]
        model = TargetModel(model.configuration_bytes, model.binding, documents,
            profile=model.profile, resource_files=model.resource_files, **model.reservations)
        for document in documents: (root / document.path).write_bytes(document.content)
    return model


@pytest.mark.parametrize('case', ['move_document', 'move_section', 'reorder', 'promote'])
@pytest.mark.parametrize('pretty', [False, True])
def test_actual_move_changes_only_relation_owners_and_preserves_all_content_bytes(tmp_path, case, pretty):
    root = tmp_path / 'project'; model = composition_project(root, pretty=pretty)
    before = inventory(root); sources = model.source_files
    with no_write_attempts(): report = preview_case(model, case)
    assert report['target_validated'] and report['exit_code'] == 0 and inventory(root) == before
    removal, addition = report['plan']['operations']; expected = {v['id']: v for v in model.artifacts}
    owners = {removal['source'], addition['source']}
    expected[removal['source']]['relations'] = [e for e in expected[removal['source']]['relations']
        if e['relation_id'] != removal['relation_id']]
    expected[addition['source']]['relations'].append(addition['relation'])
    for identity in owners:
        value = expected[identity]; value['revision'] += 1
        value['updated_at'] = TIME; value['updated_by'] = ACTOR
    declared = {entry['artifact']['id'] for entry in report['plan']['result_artifacts']}
    assert declared == owners
    result = confirm_and_replay(root, model, report)
    changed = {artifact_path(expected[i]['artifact_type'], i, 'SR') for i in owners}
    assert_stored(root, expected, before, changed)
    assert result['audit']['created_ids'] == [addition['relation']['relation_id']]
    observed = current(root, model)
    for token in ('0', '1'):
        resolved = resolve_artifact_reference(observed, ref('BLOCK', token))
        path = artifact_path('requirement', ref('REQ'), 'SR')
        assert resolved.target_source_bytes == sources[path] == (root / path).read_bytes()
        assert resolved.target_record == expected[ref('REQ')]
        assert resolved.data['target']['revision'] == 7
        assert resolved.data['target']['source_sha256'] == sha256(sources[path]).hexdigest()
    composed = [compose_document(observed, ref('DOC', token)) for token in ('0', '1')]
    for block in (ref('BLOCK'), ref('BLOCK', '1')):
        rows = [row for composition in composed for row in composition.data['occurrences'] if row['artifact_id'] == block]
        assert len(rows) == 1 and rows[0]['revision'] == 3


@pytest.mark.parametrize('case', ['move_document', 'reorder'])
def test_referenced_content_changed_after_preview_blocks_saved_move_without_erasing_change(tmp_path, case):
    root = tmp_path / 'project'; model = composition_project(root, pretty=True); report = preview_case(model, case)
    path = root / artifact_path('requirement', ref('REQ'), 'SR')
    path.write_bytes(path.read_bytes() + b'\n'); before = inventory(root)
    result = execute_authoring_plan(saved(report), model, command_id='section.move',
        transaction_id='txn-stale-reference', authority=PublicationAuthority('unused', '1',
            lambda request: pytest.fail('stale reference reached publication')))
    assert result['status'] == 'failed' and result['exit_code'] == 6
    assert result['write_state'] == 'not_committed' and inventory(root) == before


def test_move_checks_actual_block_semantics_even_with_a_permissive_host(tmp_path):
    root = tmp_path / 'project'; model = composition_project(root); values = model.artifacts
    block = next(v for v in values if v['id'] == ref('BLOCK'))
    block.update(block_kind='prose', payload={'markdown': '<script>active</script>'}, relations=[])
    model = replace_model(root, model, values); before = inventory(root)
    host = ModelGate('document_model', 'adversarial',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}), lambda c: c.result())
    report = preview_case(model, 'move_document', gates=(host,))
    assert not report['target_validated'] and report['exit_code'] == 1
    assert any(reason.startswith('prose_') for reason in reasons(report))
    result = execute_authoring_plan(saved(report), model, command_id='section.move',
        transaction_id='txn-invalid-prose', gates=(host,), authority=PublicationAuthority(
            'unused', '1', lambda request: pytest.fail('invalid prose reached publication')))
    assert result['status'] == 'failed' and inventory(root) == before
