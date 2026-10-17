"""Mutation strategies, retained stale guards and real interrupted publication."""
from copy import deepcopy
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring.documents import preview_block_add, preview_section_remove
from specroad.authoring.execution import execute_authoring_plan
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.authoring.plans import preview_authoring_request
from specroad.changes import ChangeOperation, PublicationAuthority, prepare_change_plan
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.paths import artifact_path
from specroad.model.relation_values import RelationIdentity
from specroad.validation import ModelGate
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from test_document_authoring import ACTOR, TIME, saved, apply
from test_document_authoring_right import reasons, replace_model, assert_failed
from test_document_mutations import (OPTIONS, mutation_project, mutation, retire,
    prepared_block, confirm_and_replay, assert_stored)
from test_document_structure import contains
from test_negative_relation_review_right import current


def index(model):
    return {value['id']: value for value in model.artifacts}


def moves(model):
    children = sorted((e for e in index(model)[ref('SEC')]['relations'] if e['type'] == 'contains'),
                      key=lambda e: (e['position'], e['target'], e['relation_id']))
    return [{'target': e['target'], 'relation_identity': RelationIdentity('REL-' + str(5 + n) * 26,
        'random128-v1'), 'position': 20 + n, 'expected_relation_sha256': canonical_json_sha256(e)}
        for n, e in enumerate(children)]


def execute(model, report, *, transaction='txn-mutation-right', authority=None, gates=()):
    return execute_authoring_plan(saved(report), model, command_id=report['command_id'],
        transaction_id=transaction, gates=gates, authority=authority or PublicationAuthority(
            'unused-host', '1', lambda request: pytest.fail('invalid request reached publication authority')))


@pytest.mark.parametrize('case', ['boolean', 'missing', 'both', 'unused_retirements', 'unused_moves',
    'no_moves', 'wrong_moves_type', 'wrong_retirements_type', 'move_empty'])
def test_strategy_inputs_are_explicit_and_never_silently_discarded(tmp_path, case):
    root = tmp_path / 'project'; model = mutation_project(root); values = index(model)
    op = retire(values[ref('SEC')]); before = inventory(root)
    options = {'boolean': {'cascade': 1}, 'missing': {},
        'both': {'cascade': True, 'move_children_to': ref('SEC', '2')},
        'unused_retirements': {'child_retirements': [retire(values[ref('BLOCK')])]},
        'unused_moves': {'child_moves': moves(model)},
        'no_moves': {'move_children_to': ref('SEC', '2')},
        'wrong_moves_type': {'move_children_to': ref('SEC', '2'), 'child_moves': {}},
        'wrong_retirements_type': {'cascade': True, 'child_retirements': None},
        'move_empty': {'move_children_to': ref('SEC', '2')}}[case]
    if case == 'move_empty': op = retire(values[ref('SEC', '1')])
    with no_write_attempts(), pytest.raises(ModelError):
        preview_section_remove(model, op, **OPTIONS, **options)
    assert inventory(root) == before


@pytest.mark.parametrize('destination', [ref('SEC'), ref('SEC', '1'), ref('SEC', '7'), ref('DOC'), ref('GOAL')])
def test_child_destination_must_be_an_existing_section_outside_the_removed_tree(tmp_path, destination):
    root = tmp_path / 'project'; model = mutation_project(root); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        preview_section_remove(model, retire(index(model)[ref('SEC')]),
            move_children_to=destination, child_moves=moves(model), **OPTIONS)
    assert error.value.reason == 'document_children_destination_required' and inventory(root) == before


def test_children_cannot_be_moved_under_a_retired_destination(tmp_path):
    root = tmp_path / 'project'; model = mutation_project(root); values = model.artifacts
    next(v for v in values if v['id'] == ref('SEC', '2'))['maturity'] = 'retired'
    model = replace_model(root, model, values); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        mutation(model, 'move')
    assert error.value.reason == 'document_children_destination_required' and inventory(root) == before


@pytest.mark.parametrize('owner,guard', [('root', 'expected_revision'), ('root', 'expected_sha256'),
    ('child', 'expected_revision'), ('child', 'expected_sha256'), ('relation', 'expected_relation_sha256')])
def test_each_retained_original_guard_is_checked_without_refreshing_it(tmp_path, owner, guard):
    root = tmp_path / 'project'; model = mutation_project(root); values = index(model)
    primary = retire(values[ref('SEC')]); child = retire(values[ref('SEC', '1')]); block = retire(values[ref('BLOCK')])
    if owner in ('root', 'child'):
        data = (primary if owner == 'root' else child).data
        data[guard] = 999 if guard == 'expected_revision' else '0' * 64
        if owner == 'root': primary = ChangeOperation(data)
        else: child = ChangeOperation(data)
        options = {'cascade': True, 'child_retirements': [child, block]}
    else:
        children = moves(model); children[-1][guard] = '0' * 64
        options = {'move_children_to': ref('SEC', '2'), 'child_moves': children}
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError):
        preview_section_remove(model, primary, **OPTIONS, **options)
    assert inventory(root) == before


@pytest.mark.parametrize('token,historical', [('1', False), ('4', False), ('5', True)])
def test_child_reparenting_never_reuses_removed_live_or_reserved_relation_ids(tmp_path, token, historical):
    root = tmp_path / 'project'; model = mutation_project(root)
    relation_id = 'REL-' + token * 26
    if historical: model = replace_model(root, model, model.artifacts, reserved_relation_ids=[relation_id])
    children = moves(model); children[0]['relation_identity'] = RelationIdentity(relation_id, 'random128-v1')
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        preview_section_remove(model, retire(index(model)[ref('SEC')]),
            move_children_to=ref('SEC', '2'), child_moves=children, **OPTIONS)
    assert error.value.reason == 'relation_identity_exists' and inventory(root) == before


@pytest.mark.parametrize('shared', ['within', 'outside'])
def test_cascade_retires_each_shared_block_once_and_never_retires_an_outside_owner_child(tmp_path, shared):
    root = tmp_path / 'project'; model = mutation_project(root); values = model.artifacts
    other = ref('SEC', '1') if shared == 'within' else ref('SEC', '2')
    next(v for v in values if v['id'] == other)['relations'].append(contains(ref('BLOCK'), '5', 7))
    model = replace_model(root, model, values); before = inventory(root)
    if shared == 'outside':
        with no_write_attempts(), pytest.raises(ModelError) as error: mutation(model, 'cascade')
        assert error.value.reason == 'document_removal_shared_child' and inventory(root) == before
        return
    report = mutation(model, 'cascade'); assert report['target_validated']
    assert [op['target'] for op in report['plan']['operations']] == [ref('SEC'), ref('SEC', '1'), ref('BLOCK')]
    expected = index(model); touched = {ref('SEC'), ref('SEC', '1'), ref('BLOCK')}
    for identity in touched:
        value = expected[identity]; value['revision'] += 1; value['maturity'] = 'retired'
        value['updated_at'] = TIME; value['updated_by'] = ACTOR
    confirm_and_replay(root, model, report)
    assert_stored(root, expected, before, {artifact_path(expected[i]['artifact_type'], i, 'SR') for i in touched})


@pytest.mark.parametrize('corruption', ['missing_pair', 'multiple_destinations', 'wrong_source',
    'wrong_child', 'noncontains', 'extra_retire', 'reordered_cascade'])
def test_saved_operations_cannot_hide_an_incomplete_or_conflicting_strategy(tmp_path, corruption):
    root = tmp_path / 'project'; model = mutation_project(root)
    report = mutation(model, 'cascade' if corruption == 'reordered_cascade' else 'move')
    operations = deepcopy(report['plan']['operations'])
    if corruption == 'missing_pair': del operations[-2:]
    elif corruption == 'multiple_destinations': operations[-1]['source'] = ref('SEC', '1')
    elif corruption == 'wrong_source': operations[1]['source'] = ref('SEC', '1')
    elif corruption == 'wrong_child': operations[2]['relation']['target'] = ref('BLOCK')
    elif corruption == 'noncontains':
        operations[2]['relation']['type'] = 'references'; operations[2]['relation'].pop('position')
    elif corruption == 'extra_retire': operations.append(retire(index(model)[ref('BLOCK')]).data)
    else: operations[1], operations[2] = operations[2], operations[1]
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError):
        preview_authoring_request(model, 'section.remove', operations, **OPTIONS)
    assert inventory(root) == before


@pytest.mark.parametrize('case', ['update', 'block_remove', 'cascade', 'move'])
@pytest.mark.parametrize('changed', ['artifact', 'profile'])
def test_live_bytes_changed_after_preview_are_preserved_and_refuse_publication(tmp_path, case, changed):
    root = tmp_path / 'project'; model = mutation_project(root); report = mutation(model, case)
    path = (artifact_path('content_block', ref('BLOCK'), 'SR') if changed == 'artifact'
            else next(p for p in model.source_files if p.startswith('profiles/') and p.endswith('.json')))
    (root / path).write_bytes((root / path).read_bytes() + b'\n')
    before = inventory(root)
    result = execute(model, report); assert_failed(result, report)
    assert result['exit_code'] == 6 and result['write_state'] == 'not_committed'
    assert inventory(root) == before


@pytest.mark.parametrize('moved', [False, True])
def test_interrupted_cascade_preserves_actual_published_records_and_recovery(tmp_path, moved):
    root = tmp_path / 'project'; model = mutation_project(root); report = mutation(model, 'cascade')
    original = model.source_files; calls = []; native = os.replace
    # Native publication order is by target path: the block precedes sections.
    second = ref('SEC') + '.json'
    def replace(source, destination, **kwargs):
        if str(destination) == second:
            calls.append(second)
            if moved: native(source, destination, **kwargs)
            raise OSError('injected cascade interruption')
        return native(source, destination, **kwargs)
    authority = PublicationAuthority('owned-host', '1', lambda request: True)
    with patch.object(os, 'replace', side_effect=replace): result = execute(model, report, authority=authority)
    assert_failed(result, report)
    assert result['exit_code'] == 5 and result['write_state'] == 'unknown' and result['recovery_required']
    assert calls == [second] and result['diagnostics'][0]['published_count_acknowledged'] == 1
    candidate = {v['artifact']['id']: v['artifact'] for v in report['plan']['result_artifacts']}
    first_path = artifact_path('content_block', ref('BLOCK'), 'SR')
    second_path = artifact_path('section', ref('SEC'), 'SR')
    assert (root / first_path).read_bytes() == canonical_json_bytes(candidate[ref('BLOCK')])
    assert (root / second_path).read_bytes() == (canonical_json_bytes(candidate[ref('SEC')]) if moved else original[second_path])
    for path, raw in original.items():
        if path not in (first_path, second_path): assert (root / path).read_bytes() == raw
    journal = json.loads((root / '.specroad/transactions/txn-mutation-right/journal.json').read_bytes())
    assert journal['state'] == 'committing' and journal['published_count'] == 1
    retained = inventory(root); retry = execute(model, report, transaction='txn-retry', authority=authority)
    assert_failed(retry, report)
    assert retry['diagnostics'][0]['reason'] == 'transaction_journal_blocks_lock' and inventory(root) == retained


def test_conflicting_saved_retry_preserves_retirement_receipt_and_all_source_bytes(tmp_path):
    root = tmp_path / 'project'; model = mutation_project(root); report = mutation(model, 'block_remove')
    first = apply(root, model, report); fresh = current(root, model); before = inventory(root)
    value = saved(report).data; value.pop('change_plan_sha256'); value['operations'][0]['reason'] = 'Different intent.'
    conflict = prepare_change_plan(value)
    with no_write_attempts():
        result = execute_authoring_plan(conflict, fresh, command_id='block.remove', transaction_id='txn-conflict',
            authority=PublicationAuthority('unused', '1', lambda request: pytest.fail('conflict authorized')))
    assert result['status'] == 'failed' and result['exit_code'] == 6
    assert result['diagnostics'][0]['reason'] == 'request_operations_conflict'
    repeated = apply(root, fresh, report, transaction='txn-replay')
    assert repeated['replayed'] and repeated['completion']['receipts'] == first['completion']['receipts']
    assert inventory(root) == before


def test_unrelated_non_draft_history_is_not_certified_by_mutation_lifecycle_gate(tmp_path):
    root = tmp_path / 'project'; model = mutation_project(root); values = model.artifacts
    next(v for v in values if v['id'] == ref('DOC', '1'))['maturity'] = 'proposed'
    model = replace_model(root, model, values); before = inventory(root)
    report = mutation(model, 'block_remove')
    assert not report['target_validated'] and 'document_mutation_lifecycle_service_required' in reasons(report)
    result = execute(model, report); assert_failed(result, report)
    assert inventory(root) == before
