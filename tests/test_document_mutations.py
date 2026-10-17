"""Saved block/removal plans, real publication and retained graph inventories."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from specroad.authoring.documents import (preview_block_add, preview_block_update,
    preview_block_remove, preview_section_remove)
from specroad.authoring.execution import execute_authoring_plan
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.authoring.plans import preview_authoring_request
from specroad.changes import AuthoringError, PublicationAuthority, TargetError
from specroad.changes.lifecycle_inputs import normalize_retire_input
from specroad.changes.update_inputs import normalize_artifact_update_input
from specroad.changes.receipt_values import TransactionReceipt
from specroad.documents import assess_document_structure
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.paths import artifact_path
from specroad.model.relation_values import RelationIdentity
from specroad.query import NormalizedQuery
from specroad.validation import ModelGate
from support.domain import relation
from support.inspection import inspection_project
from support.read_only import inventory, no_write_attempts
from support.records import block_value, record_value, ref
from test_authoring_inputs import GENERATED
from test_document_authoring import ACTOR, TIME, document_project, saved, apply
from test_document_authoring_right import reasons, replace_model
from test_document_structure import contains, section
from test_negative_relation_review_right import current

KINDS = ('prose', 'artifact_ref', 'query', 'table', 'admonition', 'page_break', 'include_document')
OPTIONS = dict(actor=ACTOR, planned_at=TIME, change_plan_id='CP-mutation', request_id='mutation-request')


def prepared_block(kind):
    value = block_value(kind)
    if kind == 'artifact_ref':
        value['relations'] = [{**relation('references', ref('GOAL')), 'relation_id': 'REL-' + '7' * 26}]
    elif kind == 'include_document':
        value['relations'] = [{**relation('references', ref('DOC', '1')), 'relation_id': 'REL-' + '7' * 26}]
    elif kind == 'query':
        value['payload'] = {'query': NormalizedQuery(filters={'type': ['goal']}).data,
                           'columns': [{'field': '/title'}], 'empty_policy': 'error'}
        value['relations'] = []
    elif kind == 'table':
        value['payload'] = {'columns': [{'field': 'value', 'heading': 'Value', 'data_type': 'number'}], 'rows': [[7]]}
    return normalize_artifact_create_input('content_block', {k: v for k, v in value.items() if k not in GENERATED})


def add(model, kind='prose', **overrides):
    return preview_block_add(model, prepared_block(kind),
        identity=ArtifactIdentity(ref('BLOCK', '3'), 'random128-v1', 'content_block', 'SR'),
        parent_id=ref('SEC'), relation_identity=RelationIdentity('REL-' + '3' * 26, 'random128-v1'),
        position=9, **{**OPTIONS, **overrides})


def mutation_project(root, *, maturity='draft'):
    model = document_project(root)
    values = model.artifacts
    for value in values:
        if value['id'] == ref('SEC'):
            value['relations'].append(contains(ref('BLOCK'), '4', 3))
    values.append(record_value('content_block', maturity=maturity))
    return replace_model(root, model, values)


def retire(value):
    return normalize_retire_input(value, reason='Remove explicitly.',
        expected_revision=value['revision'], expected_sha256=canonical_json_sha256(value))


def mutation(model, case, **overrides):
    index = {v['id']: v for v in model.artifacts}; options = {**OPTIONS, **overrides}
    block = index[ref('BLOCK')]
    if case == 'update':
        op = normalize_artifact_update_input(block,
            patch=[{'op': 'replace', 'path': '/payload/markdown', 'value': 'Updated **content**.'}],
            expected_revision=block['revision'], expected_sha256=canonical_json_sha256(block))
        return preview_block_update(model, op, **options)
    if case == 'block_remove':
        return preview_block_remove(model, retire(block), **options)
    if case == 'empty':
        return preview_section_remove(model, retire(index[ref('SEC', '1')]), **options)
    root = index[ref('SEC')]
    if case == 'cascade':
        return preview_section_remove(model, retire(root), cascade=True,
            child_retirements=[retire(index[ref('SEC', '1')]), retire(block)], **options)
    assert case == 'move'
    children = sorted((e for e in root['relations'] if e['type'] == 'contains'),
                      key=lambda e: (e['position'], e['target'], e['relation_id']))
    moves = [{'target': e['target'], 'relation_identity': RelationIdentity('REL-' + str(5 + n) * 26,
        'random128-v1'), 'position': 20 + n, 'expected_relation_sha256': canonical_json_sha256(e)}
        for n, e in enumerate(children)]
    return preview_section_remove(model, retire(root), move_children_to=ref('SEC', '2'),
                                  child_moves=moves, **options)


def assert_stored(root, expected, before, changed):
    for value in expected.values():
        assert json.loads((root / artifact_path(value['artifact_type'], value['id'], 'SR')).read_bytes()) == value
    after = {row[0]: row[1:] for row in inventory(root)}
    for path, *row in before:
        if path not in changed:
            assert after[path] == tuple(row)
    assert {str(p.relative_to(root)) for p in (root / 'spec').rglob('*.json')} == {
        artifact_path(v['artifact_type'], v['id'], 'SR') for v in expected.values()}


def confirm_and_replay(root, model, report):
    result = apply(root, model, report)
    assert result['write_state'] == 'committed' and result['completion']['current_target_verified']
    receipt = TransactionReceipt((root / result['completion']['receipts']['transaction']['path']).read_bytes()).data
    assert receipt['operations'] == report['plan']['operations']
    assert receipt['journal']['plan_sha256'] == report['plan_sha256']
    before = inventory(root)
    with no_write_attempts(): repeated = apply(root, model, report, transaction='txn-repeat')
    assert repeated['replayed'] and not repeated['completion']['current_target_verified']
    assert repeated['completion']['receipts'] == result['completion']['receipts'] and inventory(root) == before
    return result


@pytest.mark.parametrize('kind', KINDS)
def test_seven_block_kinds_are_saved_and_published_with_native_semantics(tmp_path, kind):
    root = tmp_path / 'project'; model = document_project(root); before = inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('prepared identities only')):
        report = add(model, kind)
    assert inventory(root) == before and report['target_validated'] and report['exit_code'] == 0
    assert report['write_state'] == 'not_committed' and not report['approval_granted']
    creation, edge = report['plan']['operations']
    expected = {v['id']: v for v in model.artifacts}
    block = creation['artifact']; assert block['maturity'] == 'draft' and block['revision'] == 1
    assert {k: v for k, v in block.items() if k not in GENERATED} == prepared_block(kind).fields
    expected[block['id']] = block
    parent = expected[ref('SEC')]
    parent['relations'].append(edge['relation']); parent['revision'] += 1
    parent['updated_at'] = TIME; parent['updated_by'] = ACTOR
    confirm_and_replay(root, model, report)
    assert_stored(root, expected, before, {artifact_path(v['artifact_type'], v['id'], 'SR') for v in (block, parent)})


@pytest.mark.parametrize('case', ['update', 'block_remove', 'empty', 'cascade', 'move'])
def test_removal_and_update_preserve_ids_children_and_original_ownership(tmp_path, case):
    root = tmp_path / 'project'; model = mutation_project(root); before = inventory(root)
    with no_write_attempts(): report = mutation(model, case)
    assert inventory(root) == before and report['target_validated'] and report['exit_code'] == 0
    expected = {v['id']: v for v in model.artifacts}; touched = set()
    if case == 'update':
        expected[ref('BLOCK')]['payload']['markdown'] = 'Updated **content**.'; touched.add(ref('BLOCK'))
    elif case == 'block_remove': touched.add(ref('BLOCK'))
    elif case == 'empty': touched.add(ref('SEC', '1'))
    elif case == 'cascade': touched.update((ref('SEC'), ref('SEC', '1'), ref('BLOCK')))
    else:
        touched.update((ref('SEC'), ref('SEC', '2')))
        expected[ref('SEC')]['relations'] = []
        expected[ref('SEC', '2')]['relations'] = [contains(ref('SEC', '1'), '5', 20), contains(ref('BLOCK'), '6', 21)]
        for edge in expected[ref('SEC', '2')]['relations']:
            edge['created_at'] = TIME; edge['created_by'] = ACTOR
    retired = touched if case not in ('update', 'move') else ({ref('SEC')} if case == 'move' else set())
    for identity in touched:
        value = expected[identity]; value['revision'] += 1
        value['updated_at'] = TIME; value['updated_by'] = ACTOR
        if identity in retired: value['maturity'] = 'retired'
    confirm_and_replay(root, model, report)
    changed = {artifact_path(expected[i]['artifact_type'], i, 'SR') for i in touched}
    assert_stored(root, expected, before, changed)
    observed = current(root, model)
    assess_document_structure(observed).require_document(ref('DOC'))
    assert next(v for v in observed.artifacts if v['id'] == ref('DOC'))['relations'] == next(
        v for v in model.artifacts if v['id'] == ref('DOC'))['relations']


@pytest.mark.parametrize('case,expected', [('update', 'proposed'), ('block_remove', 'retired')])
def test_native_approved_content_and_retirement_policy_is_preserved(tmp_path, case, expected):
    root = tmp_path / 'project'; model = mutation_project(root, maturity='approved')
    report = mutation(model, case); assert report['target_validated']
    confirm_and_replay(root, model, report)
    value = json.loads((root / artifact_path('content_block', ref('BLOCK'), 'SR')).read_bytes())
    assert value['maturity'] == expected and value['revision'] == 2


@pytest.mark.parametrize('strategy', ['none', 'both', 'missing_child', 'extra_retirement'])
def test_incomplete_or_conflicting_section_removal_never_writes(tmp_path, strategy):
    root = tmp_path / 'project'; model = mutation_project(root); before = inventory(root)
    index = {v['id']: v for v in model.artifacts}
    choices = {'none': {}, 'both': {'cascade': True, 'move_children_to': ref('SEC', '2')},
        'missing_child': {'cascade': True, 'child_retirements': [retire(index[ref('SEC', '1')])]},
        'extra_retirement': {'cascade': True, 'child_retirements': [retire(index[ref('SEC', '1')]),
            retire(index[ref('BLOCK')]), retire(index[ref('SEC', '2')])]}}
    with no_write_attempts(), pytest.raises(ModelError):
        preview_section_remove(model, retire(index[ref('SEC')]), **OPTIONS, **choices[strategy])
    assert inventory(root) == before


@pytest.mark.parametrize('case', ['update', 'block_remove', 'empty', 'cascade', 'move'])
def test_saved_mutation_requires_actual_publication_authority(tmp_path, case):
    root = tmp_path / 'project'; model = mutation_project(root); report = mutation(model, case)
    before = inventory(root)
    result = execute_authoring_plan(saved(report), model, command_id=report['command_id'],
        transaction_id='txn-denied', authority=PublicationAuthority('denied', '1', lambda request: False))
    assert result['status'] == 'failed' and result['exit_code'] == 7
    assert result['command_id'] == result['audit']['command_id'] == report['command_id']
    assert result['write_state'] == 'not_committed' and inventory(root) == before


@pytest.mark.parametrize('bad', ['prose', 'table', 'include'])
def test_host_document_gate_cannot_bypass_native_block_semantics(tmp_path, bad):
    root = tmp_path / 'project'; model = document_project(root)
    prepared = prepared_block({'prose': 'prose', 'table': 'table', 'include': 'include_document'}[bad]).fields
    if bad == 'prose': prepared['payload']['markdown'] = '<script>active</script>'
    elif bad == 'table': prepared['payload']['rows'] = [['not a number']]
    else: prepared['relations'][0]['target'] = ref('DOC')
    gate = ModelGate('document_model', 'adversarial-host',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}), lambda c: c.result())
    before = inventory(root)
    report = preview_block_add(model, normalize_artifact_create_input('content_block', prepared),
        identity=ArtifactIdentity(ref('BLOCK', '3'), 'random128-v1', 'content_block', 'SR'),
        parent_id=ref('SEC'), relation_identity=RelationIdentity('REL-' + '3' * 26, 'random128-v1'),
        position=9, gates=(gate,), **OPTIONS)
    assert not report['target_validated'] and report['exit_code'] == 1
    with pytest.raises(TargetError): apply(root, model, report, gates=(gate,))
    assert inventory(root) == before


@pytest.mark.parametrize('case', ['update', 'block_remove', 'empty', 'cascade', 'move'])
def test_saved_command_cannot_mutate_an_unrelated_target(tmp_path, case):
    root = tmp_path / 'project'; model = mutation_project(root); report = mutation(model, case)
    operations = deepcopy(report['plan']['operations']); operations[0]['target'] = ref('GOAL')
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError):
        preview_authoring_request(model, report['command_id'], operations, **OPTIONS)
    assert inventory(root) == before
