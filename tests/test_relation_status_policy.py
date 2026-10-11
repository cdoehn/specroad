"""Profile-bound review findings and repair facts, without display assertions."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from specroad.authoring.relation_status import relation_status_report
from specroad.changes import TargetError
from specroad.model.canonical import canonical_json_sha256
from specroad.profiles import ProfileError, ProfileCompositionError
from support.profile_composition import profile, composed
from support.profiles import profile_data
from support.read_only import no_write_attempts
from support.relations import aid, edge, rid
from support.targets import model
from test_relation_review_status import endpoints, review


def policy(*, kinds=('addresses',), maturities=(), status='unreviewed', severity='info'):
    return {'relation_types': list(kinds), 'maturities': list(maturities),
        'status': status, 'severity': severity}


def bound(artifacts, rows=(), **changes):
    return model(artifacts, profiles=[profile_data(profile_id='core'),
        profile_data(profile_id='review-policy', relation_review_policy=list(rows), **changes)])


@pytest.mark.parametrize('status', ['unreviewed', 'suspect'])
@pytest.mark.parametrize('maturity,severity,exit_code', [
    ('draft', 'info', 0), ('proposed', 'warning', 0), ('in_review', 'error', 1)])
def test_source_maturity_selects_bound_policy_and_actual_diagnostic(status, maturity, severity, exit_code):
    source, target = endpoints()
    history = [review(source, target)] if status == 'suspect' else []
    if history:
        source['statement'] = 'Changed requirement.'
    source['maturity'] = maturity
    rows = [policy(maturities=(m,), status=status, severity=s)
        for m, s in [('draft', 'info'), ('proposed', 'warning'), ('in_review', 'error')]]
    current = bound([source, target, *history], rows)
    result = relation_status_report(current)
    row = result['relations'][0]
    assert (row['status'], row['source_maturity'], row['severity']) == (status, maturity, severity)
    assert result['diagnostics'][0]['severity'] == severity and result['exit_code'] == exit_code
    assert result['profile'] == current.profile.binding()
    assert not result['approval_granted'] and not result['write_authorized']


def test_relation_type_and_source_maturity_are_independent_selectors():
    p = composed(profile(relation_review_policy=[policy(maturities=('draft',))]))
    assert p.relation_review_severity('addresses', 'draft', 'unreviewed') == 'info'
    assert p.relation_review_severity('depends_on', 'draft', 'unreviewed') == 'warning'
    assert p.relation_review_severity('addresses', 'proposed', 'unreviewed') == 'warning'
    assert p.relation_review_severity('addresses', 'draft', 'suspect') == 'warning'


def test_target_maturity_does_not_replace_source_policy_selector():
    source, target = endpoints(); target['maturity'] = 'in_review'
    result = relation_status_report(bound([source, target], [policy(maturities=('draft',)),
        policy(maturities=('in_review',), severity='error')]))
    assert result['relations'][0]['severity'] == 'info' and result['exit_code'] == 0


@pytest.mark.parametrize('status,code', [('unreviewed', 'SRV025'), ('suspect', 'SRV026')])
def test_later_global_override_supersedes_earlier_scoped_policy(status, code):
    scoped = profile('scoped', relation_review_policy=[policy(status=status)])
    global_ = profile('global', severity_overrides={code: 'error'})
    assert composed(scoped, global_).relation_review_severity('addresses', 'draft', status) == 'error'
    assert composed(global_, scoped).relation_review_severity('addresses', 'draft', status) == 'info'
    assert composed(global_, scoped).relation_review_severity('depends_on', 'draft', status) == 'error'


def test_later_scoped_policy_wins_and_same_profile_specificity_beats_global():
    earlier = profile('earlier', relation_review_policy=[policy(severity='error')])
    later = profile('later', severity_overrides={'SRV025': 'warning'},
        relation_review_policy=[policy(maturities=('draft',))])
    p = composed(earlier, later)
    assert p.relation_review_severity('addresses', 'draft', 'unreviewed') == 'info'
    assert p.relation_review_severity('addresses', 'proposed', 'unreviewed') == 'warning'
    assert p.relation_review_severity('depends_on', 'draft', 'unreviewed') == 'warning'


def test_scoped_policy_changes_effective_hash_and_returns_detached_values():
    a = composed(profile(relation_review_policy=[policy()]))
    b = composed(profile(relation_review_policy=[policy(severity='error')]))
    assert a.sha256 != b.sha256
    a.data['merge']['relation_review_policy'][0]['severity'] = 'error'
    assert a.relation_review_severity('addresses', 'draft', 'unreviewed') == 'info'
    assert a.sha256 == canonical_json_sha256(a.data)


@pytest.mark.parametrize('changes', [
    {'relation_types': []}, {'relation_types': ['unknown']}, {'relation_types': ['addresses', 'addresses']},
    {'maturities': ['unknown']}, {'maturities': ['draft', 'draft']}, {'maturities': 'draft'},
    {'status': 'invalid'}, {'status': 'current'}, {'status': []}, {'severity': 'silent'},
    {'severity': None}, {'unknown': True}])
def test_invalid_policy_documents_are_rejected_before_composition(changes):
    with pytest.raises(ProfileError):
        profile(relation_review_policy=[{**policy(), **changes}])


@pytest.mark.parametrize('second', [policy(), policy(maturities=('draft',), severity='error')])
def test_overlapping_policy_cells_in_one_profile_are_rejected(second):
    with pytest.raises(ProfileError) as error:
        profile(relation_review_policy=[policy(), second])
    assert error.value.reason == 'profile_duplicate_review_policy'


@pytest.mark.parametrize('selector', [
    ('unknown', 'draft', 'suspect'), ('addresses', 'unknown', 'suspect'),
    ('addresses', 'draft', 'silent'), ([], 'draft', 'suspect')])
def test_untyped_or_unknown_lookup_selectors_are_not_silent_defaults(selector):
    with pytest.raises(ProfileCompositionError):
        composed().relation_review_severity(*selector)


@pytest.mark.parametrize('severity', ['info', 'warning', 'error'])
def test_current_has_no_finding_and_invalid_stays_error(severity):
    p = composed(profile(relation_review_policy=[policy(severity=severity)]))
    assert p.relation_review_severity('addresses', 'draft', 'current') is None
    assert p.relation_review_severity('addresses', 'draft', 'invalid') == 'error'


def test_unreviewed_reports_current_revisions_without_invented_history():
    source, target = endpoints(); source['revision'] = 7; target['revision'] = 3
    result = relation_status_report(bound([source, target]))
    row = result['relations'][0]
    assert row['current_source']['revision'] == 7 and row['current_target']['revision'] == 3
    assert row['selected_review'] is row['latest_review'] is None
    assert row['changes_since_latest_review'] == []
    assert row['required_repair'] == ['record_human_review']


@pytest.mark.parametrize('changed,key', [
    ('source', 'source_context_sha256'), ('target', 'target_context_sha256'),
    ('relation', 'relation_content_sha256')])
def test_suspect_explains_context_change_and_bound_reviewed_revisions(changed, key):
    source, target = endpoints(); source['revision'] = 7; target['revision'] = 3
    history = review(source, target)
    if changed == 'relation':
        source['relations'][0]['rationale'] = 'New rationale.'
        source['revision'] = 8
    else:
        endpoint = source if changed == 'source' else target
        endpoint['statement'] = 'A different statement.'; endpoint['revision'] += 1
    row = relation_status_report(bound([source, target, history]))['relations'][0]
    assert row['status'] == 'suspect' and row['changes_since_latest_review'] == [key]
    assert row['latest_review']['decision'] == 'confirmed' and row['selected_review'] is None
    assert row['latest_review']['source_revision'] == 7 and row['latest_review']['target_revision'] == 3
    assert row['current_source']['revision'] == source['revision']
    assert row['current_target']['revision'] == target['revision']
    assert row['required_repair'] == ['review_changed_context']


def test_audit_only_revision_difference_is_displayed_without_repair():
    source, target = endpoints(); history = review(source, target)
    source['revision'] += 1; source['updated_at'] = '2027-01-01T00:00:00Z'
    row = relation_status_report(bound([source, target, history]))['relations'][0]
    assert row['status'] == 'current' and row['severity'] is None
    assert row['current_source']['revision'] == history['source_revision'] + 1
    assert row['selected_review']['source_revision'] == history['source_revision']
    assert row['changes_since_latest_review'] == row['required_repair'] == []


def test_latest_history_is_distinct_from_the_review_that_controls_status():
    source, target = endpoints(); matching = review(source, target)
    later = review(source, target, number=21, decision='rejected', time='2027-01-01T00:00:00Z',
        source_context_sha256='0' * 64)
    result = relation_status_report(bound([source, target, later, matching]))
    row = result['relations'][0]
    assert row['status'] == 'current' and result['diagnostics'] == []
    assert row['selected_review']['id'] == matching['id']
    assert row['latest_review']['id'] == later['id'] and row['latest_review']['decision'] == 'rejected'
    assert row['changes_since_latest_review'] == ['source_context_sha256']
    assert row['required_repair'] == []


def test_negative_review_and_missing_target_have_distinct_repairs():
    source, target = endpoints(); history = review(source, target, decision='rejected')
    negative = relation_status_report(bound([source, target, history]))
    missing = relation_status_report(bound([source, history]))
    assert negative['relations'][0]['required_repair'] == ['resolve_rejection_and_record_new_human_review']
    assert missing['relations'][0]['required_repair'] == ['repair_relation_structure', 'record_human_review']
    assert missing['relations'][0]['current_target'] is None
    for result in (negative, missing):
        assert result['exit_code'] == 1 and result['diagnostics'][0]['severity'] == 'error'
        assert not result['approval_granted'] and not result['write_authorized']


def test_sorted_rows_retain_original_diagnostic_positions():
    source, target = endpoints()
    source['relations'] = [edge('addresses', target['id'], number=2),
        edge('addresses', target['id'], number=1)]
    result = relation_status_report(bound([target, source]))
    assert [row['relation_id'] for row in result['relations']] == [rid(1), rid(2)]
    positions = {next(i for i in d['related_ids'] if i.startswith('REL-')): d['location']['pointer']
        for d in result['diagnostics']}
    assert positions == {rid(1): '/relations/1', rid(2): '/relations/0'}


@pytest.mark.parametrize('endpoint', ['source', 'target'])
def test_artifact_filter_includes_outgoing_and_incoming_relations(endpoint):
    source, target = endpoints(); identity = (source if endpoint == 'source' else target)['id']
    result = relation_status_report(bound([source, target]), identity)
    assert result['artifact_filter'] == identity and len(result['relations']) == 1


def test_existing_unconnected_artifact_and_empty_project_have_empty_reports():
    source, target = endpoints(); unrelated = deepcopy(target); unrelated['id'] = aid('goal', 2)
    assert relation_status_report(bound([source, target, unrelated]), unrelated['id'])['relations'] == []
    empty = relation_status_report(bound([]))
    assert empty['relations'] == empty['diagnostics'] == [] and empty['exit_code'] == 0
    assert empty['validation_scope'] == 'supplied_relation_status_policy_only'


@pytest.mark.parametrize('selector,reason', [(True, 'review_artifact_identity_required'),
    (aid('goal', 20), 'review_artifact_missing')])
def test_unknown_filter_cannot_pass_as_an_empty_success(selector, reason):
    source, target = endpoints()
    with pytest.raises(TargetError) as error:
        relation_status_report(bound([source, target]), selector)
    assert error.value.reason == reason


def test_snapshot_and_report_are_owned_and_query_attempts_no_writes():
    source, target = endpoints(); current = bound([source, target], [policy()])
    before = dict(current.source_files)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError):
        first = relation_status_report(current)
        first['relations'][0]['current_source']['revision'] = 99
        second = relation_status_report(current)
    assert second['relations'][0]['current_source']['revision'] == source['revision']
    assert current.source_files == before and source['maturity'] == 'draft'


@pytest.mark.parametrize('settings,exit_code', [({}, 0), ({'strict': True}, 1), ({'fail_on': 'warning'}, 1)])
def test_failure_threshold_changes_exit_without_rewriting_policy_severity(settings, exit_code):
    source, target = endpoints()
    result = relation_status_report(bound([source, target], [policy(severity='warning')]), **settings)
    assert result['exit_code'] == exit_code
    assert result['relations'][0]['severity'] == result['diagnostics'][0]['severity'] == 'warning'


def test_report_rejects_an_unbound_model_before_observation():
    with pytest.raises(TargetError) as error:
        relation_status_report({})
    assert error.value.reason == 'target_model_required'
