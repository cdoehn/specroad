"""Review precedence, excluded metadata and typed machine diagnostics."""
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from specroad.authoring.review_status import relation_review_diagnostics
from specroad.changes import TargetModel
from specroad.diagnostics import (Diagnostic, ResultContractError, assess_diagnostics,
                                  diagnostic_schema)
from specroad.graph.relations import SourceRelations
from specroad.graph.review_status import RelationReviewStatuses
from specroad.model._schema import validate_builtin
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.read_only import inventory as file_inventory, no_write_attempts
from support.relations import aid, edge, rid, external
from test_relation_authoring import stored_project
from test_relation_review_status import sources, endpoints, review, assess


@pytest.mark.parametrize('kind,reason', [
    ('missing', 'missing_relation_target'), ('self', 'self_relation_forbidden'),
    ('pair', 'relation_type_pair_forbidden'), ('canonical', 'noncanonical_symmetric_relation'),
])
def test_structural_invalid_dominates_even_hash_matching_confirmed_review(kind, reason):
    source, target = endpoints()
    if kind == 'self':
        source['relations'][0].update(type='depends_on', target=source['id']); target = source
    elif kind == 'pair': source['relations'][0]['type'] = 'verified_by'
    elif kind == 'canonical':
        source = domain_value('goal', id=aid('goal', 2),
            relations=[edge('conflicts_with', target['id'])])
    record = review(source, target)
    values = [source, record] if kind in ('missing', 'self') else [source, target, record]
    result = RelationReviewStatuses(sources(*values)); status = result.for_relation(source['id'], rid())
    assert (status.status, status.reason, status.selected_review_id) == ('invalid', reason, None)
    assert status.matching_review_ids == ()
    finding, = result.diagnostics
    assert (finding.code, finding.severity, finding.category) == ('SRV027', 'error', 'relation_structure')
    assert finding.rationale == reason and record['id'] not in finding.related_ids
    assert assess_diagnostics(result.diagnostics).exit_code == 1
    with pytest.raises(ResultContractError):
        Diagnostic.from_dict({**finding.as_dict(), 'severity': 'warning'})


@pytest.mark.parametrize('field', ['relation_content_sha256', 'source_context_sha256', 'target_context_sha256'])
def test_newer_nonmatching_confirmation_cannot_hide_current_rejection(field):
    source, target = endpoints(); rejected = review(source, target, decision='rejected')
    newer = review(source, target, number=21, time='2027-01-01T00:00:00Z', **{field: '0' * 64})
    result = RelationReviewStatuses(sources(source, target, newer, rejected))
    status = result.for_relation(source['id'], rid())
    assert status.status == 'invalid' and status.reason == 'current_review_rejected'
    assert status.selected_review_id == rejected['id']
    finding, = result.diagnostics
    assert finding.category == 'review_outcome' and finding.severity == 'error'
    assert rejected['id'] in finding.related_ids and newer['id'] not in finding.related_ids


def test_later_current_confirmation_removes_only_the_previous_outcome_finding():
    source, target = endpoints(); rejected = review(source, target, decision='rejected')
    confirmed = review(source, target, number=21, time='2027-01-01T00:00:00Z')
    before = canonical_json_bytes([source, target, rejected, confirmed])
    result = RelationReviewStatuses(sources(source, target, rejected, confirmed))
    assert result.for_relation(source['id'], rid()).status == 'current'
    assert result.diagnostics == () and result.approval_granted is False
    assert canonical_json_bytes([source, target, rejected, confirmed]) == before


@pytest.mark.parametrize('endpoint', ['source', 'target'])
@pytest.mark.parametrize('field,value', [
    ('maturity', 'proposed'), ('revision', 99), ('created_at', '2025-01-01T00:00:00Z'),
    ('updated_at', '2027-01-01T00:00:00Z'),
    ('created_by', {'actor_type': 'human', 'actor_id': 'old-author'}),
    ('updated_by', {'actor_type': 'tool', 'actor_id': 'metadata-service'}),
    ('tags', ['internal']),
])
def test_excluded_lifecycle_audit_and_tags_do_not_make_review_suspect(endpoint, field, value):
    source, target = endpoints(); record = review(source, target)
    (source if endpoint == 'source' else target)[field] = deepcopy(value)
    result = RelationReviewStatuses(sources(source, target, record))
    assert result.for_relation(source['id'], rid()).status == 'current'
    assert result.diagnostics == ()


@pytest.mark.parametrize('endpoint,field,value', [
    ('source', 'title', 'A different source'), ('target', 'title', 'A different target'),
    ('target', 'owner', 'operations'),
    ('source', 'extensions', {'vendor.review': {'review_relevant': True}}),
    ('target', 'extensions', {'vendor.review': {'review_relevant': True}}),
])
def test_review_relevant_fields_make_history_suspect(endpoint, field, value):
    source, target = endpoints(); record = review(source, target)
    (source if endpoint == 'source' else target)[field] = deepcopy(value)
    result = RelationReviewStatuses(sources(source, target, record))
    assert result.for_relation(source['id'], rid()).status == 'suspect'
    finding, = result.diagnostics
    assert (finding.code, finding.severity, finding.category) == ('SRV026', 'warning', 'relation_review')


def test_new_unrelated_relation_does_not_invalidate_existing_current_review():
    source, target = endpoints(); record = review(source, target)
    other = domain_value('goal', id=aid('goal', 2))
    source['relations'].append(edge('addresses', other['id'], number=2))
    result = RelationReviewStatuses(sources(source, target, other, record))
    assert result.for_relation(source['id'], rid()).status == 'current'
    assert result.for_relation(source['id'], rid(2)).status == 'unreviewed'
    finding, = result.diagnostics
    assert finding.code == 'SRV025' and finding.severity == 'warning'
    assert rid(2) in finding.related_ids and rid() not in finding.related_ids


@pytest.mark.parametrize('older,newer', [
    ('2026-01-01T00:00:00.00000000000000000001Z', '2026-01-01T00:00:00.00000000000000000002Z'),
    ('2024-06-30T23:59:59.999999999Z', '2024-06-30T23:59:60Z'),
    ('2024-06-30T23:59:60Z', '2024-07-01T00:00:00Z'),
])
def test_exact_timestamp_precedence_preserves_supported_precision_and_rollover(older, newer):
    source, target = endpoints()
    previous = review(source, target, number=22, time=older)
    latest = review(source, target, number=21, time=newer, decision='rejected')
    result = assess(source, target, latest, previous)
    assert result.status == 'invalid' and result.selected_review_id == latest['id']


def test_diagnostic_points_to_stored_position_even_when_statuses_are_sorted():
    source, target = endpoints(); other = domain_value('goal', id=aid('goal', 2))
    source['relations'] = [edge('addresses', other['id'], number=2), source['relations'][0]]
    path = artifact_path('requirement', source['id'], 'SR')
    records = (SourceRelations(canonical_json_bytes(source), path=path), *sources(target, other))
    result = RelationReviewStatuses(records)
    assert [value.relation_id for value in result.statuses] == [rid(), rid(2)]
    pointers = {next(key for key in d.related_ids if key.startswith('REL-')): d.location['pointer']
        for d in result.diagnostics}
    assert pointers == {rid(2): '/relations/0', rid(): '/relations/1'}
    for finding in result.diagnostics:
        assert finding.path == path and finding.artifact_id == source['id']
        assert finding.origin == 'core_rule'
        validate_builtin(finding.as_dict(), diagnostic_schema())
        assert set(finding.location) == {'pointer'}


def test_diagnostics_and_projections_do_not_follow_caller_mutation():
    source, target = endpoints(); record = review(source, target, decision='rejected')
    result = RelationReviewStatuses(sources(source, target, record)); finding, = result.diagnostics
    detached = finding.as_dict(); detached['location']['pointer'] = '/wrong'; detached['related_ids'].clear()
    assert finding.location['pointer'] == '/relations/0'
    assert record['id'] in finding.related_ids
    with pytest.raises(TypeError): finding.location['pointer'] = '/wrong'
    with pytest.raises(FrozenInstanceError): finding.severity = 'warning'
    assert result.data['relations'][0]['reason'] == 'current_review_rejected'


def model_with_history(tmp_path, *, rejected=False):
    model, source, goals = stored_project(tmp_path / 'project', with_edges=True)
    if not rejected: return model, source
    value = review(source, goals[0], decision='rejected')
    path = artifact_path('relation_review', value['id'], 'SR')
    # Supplied immutable historical record, deliberately no negative writer claim.
    model = TargetModel(model.configuration_bytes, model.binding,
        (*model.documents, ModelDocument(path, canonical_json_bytes(value))),
        profile=model.profile, resource_files=model.resource_files, **model.reservations)
    return model, source


@pytest.mark.parametrize('policy,exit_code', [({}, 0), ({'strict': True}, 1), ({'fail_on': 'warning'}, 1)])
def test_read_only_query_policy_changes_failure_threshold_not_warning_severity(tmp_path, policy, exit_code):
    model, source = model_with_history(tmp_path); before = file_inventory(tmp_path)
    with no_write_attempts(): result = relation_review_diagnostics(model, **policy)
    assert result['exit_code'] == exit_code and result['checks_complete'] is True
    assert result['validation_scope'] == 'supplied_relation_review_status_only'
    assert result['checked_ids'] == [source['id']]
    assert {value['code'] for value in result['diagnostics']} == {'SRV025'}
    assert {value['severity'] for value in result['diagnostics']} == {'warning'}
    assert result['approval_granted'] is result['write_authorized'] is False
    assert file_inventory(tmp_path) == before


@pytest.mark.parametrize('policy', [{}, {'strict': True}, {'fail_on': 'warning'}])
def test_rejected_outcome_remains_error_for_every_query_failure_policy(tmp_path, policy):
    model, source = model_with_history(tmp_path, rejected=True); before = file_inventory(tmp_path)
    with no_write_attempts(): result = relation_review_diagnostics(model, **policy)
    assert result['exit_code'] == 1 and result['status'] == 'failed'
    errors = [value for value in result['diagnostics'] if value['severity'] == 'error']
    assert len(errors) == 1
    assert (errors[0]['code'], errors[0]['category']) == ('SRV027', 'review_outcome')
    assert errors[0]['rationale'] == 'current_review_rejected'
    assert errors[0]['artifact_id'] == source['id']
    statuses = {value['relation_id']: value['status'] for value in result['relation_statuses']}
    assert statuses == {rid(10): 'invalid', rid(11): 'unreviewed'}
    assert result['approval_granted'] is result['write_authorized'] is False
    assert file_inventory(tmp_path) == before


@pytest.mark.parametrize('bad', [None, {}, 'records', b'records', [object()]])
def test_untyped_history_input_never_produces_a_passing_observation(bad):
    with pytest.raises(ModelError): RelationReviewStatuses(bad)


def test_duplicate_external_relation_identity_is_not_hidden_by_history():
    source, target = endpoints(); record = review(source, target)
    key = external(); source['relations'][0]['external_identities'] = [key]
    other = domain_value('goal', id=aid('goal', 2))
    source['relations'].append(edge('addresses', other['id'], number=2, external_identities=[deepcopy(key)]))
    with pytest.raises(ModelError) as error: RelationReviewStatuses(sources(source, target, other, record))
    assert error.value.reason == 'duplicate_external_relation_identity'


def test_mixed_project_prefix_is_rejected_without_partial_status():
    source, target = endpoints(); other = domain_value('goal', id=aid('goal', 3, project='XX'))
    with pytest.raises(ModelError) as error: RelationReviewStatuses(sources(source, target, other))
    assert error.value.reason == 'mixed_project_prefix'


def test_schema_invalid_unrelated_record_prevents_false_complete_assessment():
    source, target = endpoints(); other = domain_value('goal', id=aid('goal', 2));other.pop('statement')
    with pytest.raises(ModelError) as error: RelationReviewStatuses(sources(source, target, other))
    assert error.value.reason == 'missing_field'
