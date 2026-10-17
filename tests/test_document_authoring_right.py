"""Document authoring refuses invalid/stale targets without partial publication."""
from copy import deepcopy
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring.documents import preview_section_add, preview_section_move
from specroad.authoring.execution import execute_authoring_plan
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.authoring.plans import preview_authoring_request
from specroad.changes import PublicationAuthority, TargetModel, prepare_change_plan
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.paths import artifact_path
from specroad.model.relation_values import RelationIdentity
from specroad.validation import ModelDocument, ModelGate
from support.read_only import inventory, no_write_attempts
from support.domain import relation
from support.records import record_value, ref
from test_authoring_inputs import fields
from test_document_authoring import ACTOR, TIME, document_project, preview_case, saved, apply
from test_document_structure import contains
from test_negative_relation_review_right import current


def reasons(report):
    return {item['reason'] for stage in report['assessment']['validation']['source_report']['stages']
            for item in stage['diagnostics']}


def execute(model, report, *, authority=None, gates=(), transaction='txn-right'):
    return execute_authoring_plan(saved(report), model, command_id=report['command_id'],
        transaction_id=transaction, gates=gates, authority=authority or PublicationAuthority(
            'unreached-document-host', '1', lambda request: pytest.fail('invalid target reached authority')))


def assert_failed(result, report):
    assert result['status'] == 'failed' and result['exit_code'] != 0
    assert result['command_id'] == result['audit']['command_id'] == report['command_id']
    assert result['audit']['plan_integrity_checked'] and result['plan_sha256'] == report['plan_sha256']
    assert result['target_model_root_sha256'] is None and result['completion'] is None
    assert not result['current_target_verified'] and not result['approval_granted']
    assert not result['retry_safe'] and not result['automatic_retry'] and not result['automatic_rollback']


def replace_model(root, model, values, **reservations):
    rebuilt = TargetModel(model.configuration_bytes, model.binding,
        [ModelDocument(artifact_path(v['artifact_type'], v['id'], 'SR'), canonical_json_bytes(v)) for v in values],
        profile=model.profile, resource_files=model.resource_files, **{**model.reservations, **reservations})
    for path, raw in rebuilt.source_files.items():
        target = root / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    return rebuilt


def section_request(model, command, parent, *, edge=None, expected=None):
    edge = edge or RelationIdentity('REL-' + '3' * 26, 'random128-v1')
    options = dict(actor=ACTOR, planned_at=TIME, change_plan_id='CP-right', request_id='right-request')
    if command == 'section.add':
        return preview_section_add(model, normalize_artifact_create_input('section', fields('section')),
            identity=ArtifactIdentity(ref('SEC', '3'), 'random128-v1', 'section', 'SR'), parent_id=parent,
            relation_identity=edge, position=5, **options)
    original = next(e for v in model.artifacts for e in v['relations']
                    if e['type'] == 'contains' and e['target'] == ref('SEC'))
    return preview_section_move(model, ref('SEC'), parent_id=parent, relation_identity=edge,
        position=5, reason='Explicit move.', expected_relation_sha256=(
            canonical_json_sha256(original) if expected is None else expected), **options)


@pytest.mark.parametrize('command', ['section.add', 'section.move'])
@pytest.mark.parametrize('parent,reason', [(ref('SEC', '7'), 'missing_operation_source'),
                                        (ref('GOAL'), 'relation_type_pair_forbidden')])
def test_invalid_parent_never_creates_or_detaches_a_section(tmp_path, command, parent, reason):
    root = tmp_path / 'project'; model = document_project(root); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error: section_request(model, command, parent)
    assert error.value.reason == reason and inventory(root) == before


@pytest.mark.parametrize('parent', [ref('SEC'), ref('SEC', '1')])
def test_self_or_descendant_move_is_rejected_before_any_publication(tmp_path, parent):
    root = tmp_path / 'project'; model = document_project(root); before = inventory(root)
    if parent == ref('SEC'):
        with no_write_attempts(), pytest.raises(ModelError) as error: section_request(model, 'section.move', parent)
        assert error.value.reason == 'self_relation_forbidden'
    else:
        with no_write_attempts(): report = section_request(model, 'section.move', parent)
        assert not report['target_validated'] and 'relation_hierarchy_cycle' in reasons(report)
        result = execute(model, report); assert_failed(result, report)
    assert inventory(root) == before


def test_stale_original_relation_hash_cannot_be_replaced_by_a_current_hash(tmp_path):
    root = tmp_path / 'project'; model = document_project(root); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        section_request(model, 'section.move', ref('DOC', '1'), expected='0' * 64)
    assert error.value.reason == 'expected_relation_hash_mismatch' and inventory(root) == before


@pytest.mark.parametrize('command', ['section.add', 'section.move'])
@pytest.mark.parametrize('token', ['0', '1', '2'])
def test_existing_relation_identity_is_never_reused_even_after_removal(tmp_path, command, token):
    root = tmp_path / 'project'; model = document_project(root); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        section_request(model, command, ref('DOC', '1'),
                        edge=RelationIdentity('REL-' + token * 26, 'random128-v1'))
    assert error.value.reason == 'relation_identity_exists' and inventory(root) == before


@pytest.mark.parametrize('reserved', ['artifact', 'relation'])
def test_historical_identity_reservations_survive_document_convenience_adapters(tmp_path, reserved):
    root = tmp_path / 'project'; model = document_project(root)
    options = ({'reserved_artifact_ids': [ref('SEC', '3')]} if reserved == 'artifact'
               else {'reserved_relation_ids': ['REL-' + '3' * 26]})
    model = replace_model(root, model, model.artifacts, **options); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error: section_request(model, 'section.add', ref('DOC'))
    assert error.value.reason == ('creation_identity_exists' if reserved == 'artifact' else 'relation_identity_exists')
    assert inventory(root) == before


@pytest.mark.parametrize('case', ['supporting_document', 'root_section', 'move_document'])
@pytest.mark.parametrize('failure', ['host_denial', 'ai_actor', 'ci_request'])
def test_structured_failure_retains_the_actual_document_command_and_plan_audit(tmp_path, case, failure):
    root = tmp_path / 'project'; model = document_project(root); options = {}
    if failure == 'ai_actor': options['actor'] = {'actor_type': 'ai', 'actor_id': 'caller'}
    if failure == 'ci_request': options.update(actor={'actor_type': 'ci', 'actor_id': 'caller'}, request_id=None)
    report = preview_case(model, case, **options); before = inventory(root)
    authority = PublicationAuthority('denied-host', '1', lambda request: False)
    result = execute(model, report, authority=authority); assert_failed(result, report)
    assert result['exit_code'] == (2 if failure == 'ci_request' else 7)
    assert result['audit']['planned_created_ids'] == report['audit']['created_ids']
    assert inventory(root) == before


@pytest.mark.parametrize('changed', ['source', 'unrelated', 'profile', 'configuration'])
def test_changed_live_bytes_block_saved_move_without_erasing_the_external_change(tmp_path, changed):
    root = tmp_path / 'project'; model = document_project(root); report = preview_case(model, 'move_document')
    paths = {'source': artifact_path('document', ref('DOC'), 'SR'),
             'unrelated': artifact_path('goal', ref('GOAL'), 'SR'),
             'profile': 'profiles/core.json', 'configuration': 'specroad.json'}
    path = root / paths[changed]; path.write_bytes(path.read_bytes() + b'\n'); before = inventory(root)
    result = execute(model, report); assert_failed(result, report)
    assert result['exit_code'] == 6 and inventory(root) == before


def permissive_document_host():
    # Deliberately permissive trusted-host fixture, used ONLY to prove that
    # native invariant refusals cannot be bypassed by this host service.
    return ModelGate('document_model', 'adversarial-host-v1',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}),
        lambda c: c.result())


def test_host_service_cannot_approve_an_include_cycle_created_by_a_section_move(tmp_path):
    root = tmp_path / 'project'; model = document_project(root); values = model.artifacts
    block = record_value('content_block', block_kind='include_document', payload={'mode': 'section'},
        relations=[{**relation('references', ref('SEC', '2')), 'relation_id': 'REL-' + '5' * 26}])
    next(v for v in values if v['id'] == ref('SEC', '1'))['relations'].append(contains(block['id'], '4'))
    model = replace_model(root, model, values + [block]); before = inventory(root)
    gates = (permissive_document_host(),)
    report = preview_case(model, 'move_section', gates=gates)
    assert not report['target_validated'] and 'document_include_cycle' in reasons(report)
    result = execute(model, report, gates=gates); assert_failed(result, report)
    assert inventory(root) == before


@pytest.mark.parametrize('corruption', ['missing_primary', 'unowned_section', 'two_parents'])
def test_unrelated_document_invariant_cannot_be_hidden_by_a_permissive_host(tmp_path, corruption):
    root = tmp_path / 'project'; model = document_project(root); values = model.artifacts
    primary = next(v for v in values if v['id'] == ref('DOC'))
    secondary = next(v for v in values if v['id'] == ref('DOC', '1'))
    if corruption == 'missing_primary': primary['document_role'] = 'supporting'
    elif corruption == 'unowned_section': values.append(record_value('section', id=ref('SEC', '6')))
    else: secondary['relations'].append(contains(ref('SEC', '1'), '6'))
    model = replace_model(root, model, values); before = inventory(root); gates = (permissive_document_host(),)
    report = preview_case(model, 'root_section', gates=gates)
    assert not report['target_validated']
    expected = 'document_primary_missing' if corruption == 'missing_primary' else 'document_section_parent_cardinality'
    assert expected in reasons(report)
    result = execute(model, report, gates=gates); assert_failed(result, report)
    assert inventory(root) == before


def test_host_cannot_replace_the_mandatory_document_authoring_gate(tmp_path):
    root = tmp_path / 'project'; model = document_project(root); before = inventory(root)
    gate = ModelGate('extension:document-authoring', 'attempted-override',
        lambda c: c.dependency_result({key: [] for key in c.subjects}), lambda c: c.result())
    with no_write_attempts(), pytest.raises(ModelError) as error:
        preview_case(model, 'root_section', gates=(gate,))
    assert error.value.reason == 'document_authoring_gate_override' and inventory(root) == before


@pytest.mark.parametrize('corruption,reason', [
    ('wrong_create_type', 'document_empty_creation_required'),
    ('creation_relations', 'document_empty_creation_required'),
    ('wrong_new_target', 'document_created_section_target_required'),
    ('noncontains_addition', 'document_contains_relation_required'),
    ('other_removed_child', 'document_original_section_relation_required')])
def test_raw_operation_sequence_cannot_bypass_document_command_shape(tmp_path, corruption, reason):
    root = tmp_path / 'project'; model = document_project(root)
    case = 'move_document' if corruption == 'other_removed_child' else 'root_section'
    report = preview_case(model, case); operations = deepcopy(report['plan']['operations'])
    if corruption == 'wrong_create_type':
        creation = preview_case(model, 'supporting_document')['plan']['operations'][0]
        operations[0] = creation; operations[1]['relation']['target'] = creation['artifact']['id']
    elif corruption == 'creation_relations': operations[0]['artifact']['relations'] = [contains(ref('SEC'), '6')]
    elif corruption == 'wrong_new_target': operations[1]['relation']['target'] = ref('SEC')
    elif corruption == 'noncontains_addition':
        operations[1]['relation']['type'] = 'references'; operations[1]['relation'].pop('position')
    else:
        original = next(e for v in model.artifacts if v['id'] == ref('DOC', '1') for e in v['relations'])
        operations[0].update(source=ref('DOC', '1'), relation_id=original['relation_id'],
                             expected_sha256=canonical_json_sha256(original))
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        preview_authoring_request(model, report['command_id'], operations, actor=ACTOR, planned_at=TIME,
                                  change_plan_id='CP-raw')
    assert error.value.reason == reason and inventory(root) == before


def test_non_draft_document_history_still_requires_its_real_lifecycle_service(tmp_path):
    root = tmp_path / 'project'; model = document_project(root); values = model.artifacts
    next(v for v in values if v['id'] == ref('DOC', '1'))['maturity'] = 'proposed'
    model = replace_model(root, model, values); before = inventory(root)
    report = preview_case(model, 'move_document')
    stages = report['assessment']['validation']['source_report']['stages']
    assert not report['target_validated'] and any(s['stage'] == 'lifecycle' and s['status'] == 'unavailable' for s in stages)
    result = execute(model, report); assert_failed(result, report)
    assert inventory(root) == before


@pytest.mark.parametrize('moved', [False, True])
def test_interrupted_second_owner_write_retains_real_partial_state_and_recovery(tmp_path, moved):
    root = tmp_path / 'project'; model = document_project(root); report = preview_case(model, 'move_document')
    native = os.replace; calls = []; original = model.source_files
    def replace(src, dst, **kwargs):
        if str(dst) == ref('DOC', '1') + '.json':
            calls.append(str(dst))
            if moved: native(src, dst, **kwargs)
            raise OSError('injected second-owner interruption')
        return native(src, dst, **kwargs)
    authority = PublicationAuthority('owned-document-host', '1', lambda request: True)
    with patch.object(os, 'replace', side_effect=replace): result = execute(model, report, authority=authority)
    assert_failed(result, report)
    assert result['exit_code'] == 5 and result['write_state'] == 'unknown' and result['recovery_required']
    assert calls == [ref('DOC', '1') + '.json']
    assert result['diagnostics'][0]['reason'] == 'publication_io_failure'
    assert result['diagnostics'][0]['published_count_acknowledged'] == 1
    candidates = {v['artifact']['id']: v['artifact'] for v in report['plan']['result_artifacts']}
    first = artifact_path('document', ref('DOC'), 'SR'); second = artifact_path('document', ref('DOC', '1'), 'SR')
    assert (root / first).read_bytes() == canonical_json_bytes(candidates[ref('DOC')])
    assert (root / second).read_bytes() == (canonical_json_bytes(candidates[ref('DOC', '1')]) if moved else original[second])
    for path, raw in original.items():
        if path not in (first, second): assert (root / path).read_bytes() == raw
    journal = json.loads((root / '.specroad/transactions/txn-right/journal.json').read_bytes())
    assert journal['state'] == 'committing' and journal['published_count'] == 1
    retained = inventory(root); retry = execute(model, report, authority=authority, transaction='txn-retry')
    assert_failed(retry, report)
    assert retry['diagnostics'][0]['reason'] == 'transaction_journal_blocks_lock' and inventory(root) == retained


def test_conflicting_retry_preserves_original_document_receipt_and_ownership(tmp_path):
    root = tmp_path / 'project'; model = document_project(root); report = preview_case(model, 'move_document')
    first = apply(root, model, report); fresh = current(root, model); before = inventory(root)
    value = saved(report).data; value.pop('change_plan_sha256')
    value['operations'][1]['relation']['position'] = 33
    conflict = prepare_change_plan(value)
    with no_write_attempts():
        result = execute_authoring_plan(conflict, fresh, command_id='section.move', transaction_id='txn-conflict',
            authority=PublicationAuthority('unused', '1', lambda request: pytest.fail('replay authorized')))
    assert result['status'] == 'failed' and result['command_id'] == 'section.move' and result['exit_code'] == 6
    assert result['diagnostics'][0]['reason'] == 'request_operations_conflict'
    with no_write_attempts(): repeated = apply(root, fresh, report, transaction='txn-retry')
    assert repeated['replayed'] and repeated['completion']['receipts'] == first['completion']['receipts']
    assert inventory(root) == before
