"""Appendix J decisions from owned histories, without writes or approval."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from specroad.authoring.review_status import relation_review_status
from specroad.changes import TargetModel, TargetError
from specroad.graph.relations import SourceRelations
from specroad.graph.review_status import RelationReviewStatuses
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.artifacts import common_artifact
from support.domain import domain_value
from support.read_only import inventory as file_inventory, no_write_attempts
from support.relations import aid, edge, rid
from test_relation_authoring import stored_project
from test_relation_review_authoring import call, options

TIME = '2026-10-10T23:40:00Z'
ACTOR = {'actor_type': 'human', 'actor_id': 'status-fixture-reviewer'}


def sources(*values):
    return tuple(SourceRelations(canonical_json_bytes(value)) for value in values)


def endpoints():
    target = domain_value('goal', id=aid('goal'))
    source = domain_value('requirement', id=aid(),
        relations=[edge('addresses', target['id'])])
    return source, target


def review(source, target, *, number=20, decision='confirmed', time=TIME, **changes):
    # Independent fixture projection from Appendix J, not the status service.
    excluded = {'revision', 'created_at', 'created_by', 'updated_at', 'updated_by',
        'maturity', 'implementation_status', 'verification_plan_status', 'risk_status',
        'validation_status', 'issue_status', 'proposal_status', 'evidence_state',
        'baseline_state', 'review_state', 'relations', 'tags'}
    relation = source['relations'][0]
    value = common_artifact('relation_review', 'RREV', id=aid('relation_review', number),
        maturity='approved', review_state='recorded', created_at=time, updated_at=time,
        created_by=ACTOR, updated_by=ACTOR, reviewer=ACTOR, reviewed_at=time,
        decision=decision, reason='Inspected the relation and both endpoints.',
        context_hash_algorithm='relation_context_hash-v1', relation_id=relation['relation_id'],
        relation_content_sha256=canonical_json_sha256({k: v for k, v in relation.items()
            if k not in ('created_at', 'created_by')}))
    for name, endpoint in (('source', source), ('target', target)):
        value.update({name + '_id': endpoint['id'], name + '_revision': endpoint['revision'],
            name + '_artifact_sha256': canonical_json_sha256(endpoint),
            name + '_context_sha256': canonical_json_sha256({k: v for k, v in endpoint.items()
                if k not in excluded})})
    value.update(changes)
    return value


def assess(source, target, *history):
    return RelationReviewStatuses(sources(source, target, *history)).for_relation(
        source['id'], source['relations'][0]['relation_id'])


def test_empty_inventory_has_no_invented_status_or_approval():
    result = RelationReviewStatuses(())
    assert result.data == {'validation_scope': 'supplied_relation_review_status_only',
        'approval_granted': False, 'relations': []}


def test_unreviewed_relation_has_no_selected_or_historical_review():
    source, target = endpoints()
    assert assess(source, target).as_fields() == {
        'source_id': source['id'], 'relation_id': rid(), 'target_id': target['id'],
        'status': 'unreviewed', 'reason': None, 'selected_review_id': None,
        'matching_review_ids': [], 'historical_review_ids': []}


def test_matching_confirmed_review_is_current_without_stored_status():
    source, target = endpoints(); record = review(source, target)
    original = deepcopy((source, target, record))
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError):
        result = assess(source, target, record)
    assert result.status == 'current' and result.reason is None
    assert result.selected_review_id == record['id']
    assert result.matching_review_ids == result.historical_review_ids == (record['id'],)
    assert (source, target, record) == original
    assert 'review_status' not in source['relations'][0]


@pytest.mark.parametrize('endpoint', ['source', 'target'])
def test_changed_endpoint_statement_makes_previous_review_suspect(endpoint):
    source, target = endpoints(); record = review(source, target)
    (source if endpoint == 'source' else target)['statement'] = 'A new reviewed assertion.'
    result = assess(source, target, record)
    assert result.status == 'suspect' and result.selected_review_id is None
    assert result.matching_review_ids == () and result.historical_review_ids == (record['id'],)


def test_changed_relation_rationale_keeps_history_and_becomes_suspect():
    source, target = endpoints(); record = review(source, target)
    source['relations'][0]['rationale'] = 'A changed justification.'
    assert assess(source, target, record).status == 'suspect'


def test_retargeted_relation_does_not_reuse_previous_endpoint_review():
    source, target = endpoints(); record = review(source, target)
    target['id'] = aid('goal', 2); source['relations'][0]['target'] = target['id']
    assert assess(source, target, record).status == 'suspect'


def test_unrelated_relation_history_does_not_turn_unreviewed_into_suspect():
    source, target = endpoints(); record = review(source, target, relation_id=rid(2))
    result = assess(source, target, record)
    assert result.status == 'unreviewed' and result.historical_review_ids == ()


@pytest.mark.parametrize('decision', ['confirmed', 'rejected'])
def test_newer_nonmatching_review_does_not_override_matching_review(decision):
    source, target = endpoints(); older = review(source, target)
    newer = review(source, target, number=21, time='2027-01-01T00:00:00Z',
        decision=decision, source_context_sha256='0' * 64)
    result = assess(source, target, newer, older)
    assert result.status == 'current' and result.selected_review_id == older['id']
    assert result.matching_review_ids == (older['id'],)
    assert result.historical_review_ids == (older['id'], newer['id'])


@pytest.mark.parametrize('decision,expected,reason', [
    ('confirmed', 'current', None), ('rejected', 'invalid', 'current_review_rejected')])
def test_newest_matching_decision_wins_without_changing_history(decision, expected, reason):
    source, target = endpoints()
    older = review(source, target, decision='rejected' if decision == 'confirmed' else 'confirmed')
    newer = review(source, target, number=21, decision=decision, time='2027-01-01T00:00:00Z')
    before = canonical_json_bytes([older, newer])
    result = assess(source, target, newer, older)
    assert (result.status, result.reason, result.selected_review_id) == (expected, reason, newer['id'])
    assert canonical_json_bytes([older, newer]) == before


@pytest.mark.parametrize('reverse', [False, True])
def test_equal_timestamp_uses_highest_review_id_not_input_order(reverse):
    source, target = endpoints()
    history = [review(source, target), review(source, target, number=21, decision='rejected')]
    if reverse: history.reverse()
    result = assess(source, target, *history)
    assert result.status == 'invalid' and result.reason == 'current_review_rejected'
    assert result.selected_review_id == aid('relation_review', 21)


@pytest.mark.parametrize('older,newer,tie', [
    ('2026-01-01T00:00:00Z', '2026-01-01T00:00:00.000000001Z', False),
    ('2026-01-01T00:00:00.09Z', '2026-01-01T00:00:00.1Z', False),
    ('2026-01-01T00:00:00.1Z', '2026-01-01T00:00:00.10Z', True),
    ('2026-01-01t00:00:00Z', '2026-01-01T00:00:00.000Z', True),
])
def test_timestamp_order_is_exact_and_equivalent_spellings_use_id(older, newer, tie):
    source, target = endpoints()
    first = review(source, target, number=22, time=older, decision='rejected')
    second = review(source, target, number=21, time=newer)
    result = assess(source, target, second, first)
    assert result.selected_review_id == (first['id'] if tie else second['id'])
    assert result.status == ('invalid' if tie else 'current')


def test_passive_legacy_record_uses_creation_time_when_reviewed_at_is_absent():
    source, target = endpoints(); record = review(source, target); record.pop('reviewed_at')
    assert assess(source, target, record).selected_review_id == record['id']


@pytest.mark.parametrize('field', ['source_artifact_sha256', 'target_artifact_sha256',
                                  'source_revision', 'target_revision'])
def test_audit_hashes_and_revisions_are_not_currentness_selectors(field):
    source, target = endpoints(); record = review(source, target)
    record[field] = 99 if field.endswith('revision') else '0' * 64
    assert assess(source, target, record).status == 'current'


def test_missing_target_is_structurally_invalid_despite_confirming_history():
    source, target = endpoints(); record = review(source, target)
    result = RelationReviewStatuses(sources(source, record)).for_relation(source['id'], rid())
    assert (result.status, result.reason) == ('invalid', 'missing_relation_target')
    assert result.selected_review_id is None and result.matching_review_ids == ()


def test_forbidden_endpoint_type_pair_is_invalid():
    source, target = endpoints(); source['relations'][0]['type'] = 'verified_by'
    result = assess(source, target)
    assert (result.status, result.reason) == ('invalid', 'relation_type_pair_forbidden')


def test_schema_invalid_review_cannot_be_used_as_confirming_evidence():
    source, target = endpoints(); record = review(source, target)
    record['reviewer'] = {'actor_type': 'ai', 'actor_id': 'model'}
    with pytest.raises(ModelError): assess(source, target, record)


def test_duplicate_history_identity_is_rejected_before_selection():
    source, target = endpoints(); record = review(source, target)
    with pytest.raises(ModelError) as error: assess(source, target, record, deepcopy(record))
    assert error.value.reason == 'duplicate_artifact_id'


def test_duplicate_relation_identity_in_two_sources_is_rejected():
    source, target = endpoints()
    other = domain_value('requirement', id=aid(number=2), relations=deepcopy(source['relations']))
    with pytest.raises(ModelError) as error: RelationReviewStatuses(sources(source, target, other))
    assert error.value.reason == 'duplicate_relation_id'


def test_result_is_deterministic_detached_and_read_only():
    source, target = endpoints(); record = review(source, target)
    records = sources(source, target, record); before = tuple(r.source_bytes for r in records)
    with no_write_attempts():
        result = RelationReviewStatuses(iter(records))
        reverse = RelationReviewStatuses(reversed(records))
        assert result.data == reverse.data
        detached = result.data; detached['relations'][0]['historical_review_ids'].clear()
        detached['relations'][0]['status'] = 'invalid'
        assert result.statuses[0].status == 'current'
        assert result.statuses[0].historical_review_ids == (record['id'],)
        with pytest.raises(FrozenInstanceError): result.statuses[0].status = 'invalid'
    assert tuple(r.source_bytes for r in records) == before
    assert result.approval_granted is False


def test_query_reads_an_actual_native_review_without_any_write(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    written = call(model, source, options(model))
    documents = (*model.documents, ModelDocument(written['path'], (root / written['path']).read_bytes()))
    observed = TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files, **model.reservations)
    before = file_inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError):
        result = relation_review_status(observed, source['id'], source['relations'][0]['relation_id'])
        other = relation_review_status(observed, source['id'], source['relations'][1]['relation_id'])
    assert result['status'] == 'current' and result['selected_review_id'] == written['review_id']
    assert result['approval_granted'] is False
    assert result['validation_scope'] == 'supplied_relation_review_status_only'
    assert other['status'] == 'unreviewed'
    assert file_inventory(root) == before


def test_query_requires_native_model_before_inspection():
    with pytest.raises(TargetError) as error: relation_review_status({}, aid(), rid())
    assert error.value.reason == 'target_model_required'


@pytest.mark.parametrize('source_id,relation_id,reason', [
    (aid(number=2), rid(), 'review_source_missing'),
    (aid(), rid(2), 'review_relation_missing'),
])
def test_unknown_selected_relation_never_creates_a_status(source_id, relation_id, reason):
    source, target = endpoints(); result = RelationReviewStatuses(sources(source, target))
    with pytest.raises(ModelError) as error: result.for_relation(source_id, relation_id)
    assert error.value.reason == reason
