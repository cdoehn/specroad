"""Policy error floors, complete input checks and native no-reapproval evidence."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from specroad.authoring.relation_status import relation_status_report
from specroad.authoring.review_status import relation_review_diagnostics
from specroad.changes import TargetError, TargetModel
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.profiles import ProfileResource, ProfileError, ProfileCompositionError, compose_profiles
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.model import put
from support.profile_composition import profile, composed
from support.read_only import inventory as file_inventory, no_write_attempts
from support.relations import aid, edge, rid
from test_negative_relation_review import negative_project, options, call
from test_negative_relation_review_right import current, coupled
from test_relation_authoring import receipt
from test_relation_review_status import endpoints, review
from test_relation_status_policy import bound, policy


@pytest.mark.parametrize('state', ['unreviewed', 'suspect'])
@pytest.mark.parametrize('severity,plain,strict', [('info', 0, 0), ('warning', 0, 1), ('error', 1, 1)])
def test_existing_diagnostic_query_honors_same_bound_policy_as_rich_report(state, severity, plain, strict):
    source, target = endpoints(); history = []
    if state == 'suspect':
        history.append(review(source, target)); source['statement'] = 'Changed statement.'
    owned = bound([source, target, *history], [policy(status=state, severity=severity)])
    for settings, expected in [({}, plain), ({'strict': True}, strict)]:
        legacy = relation_review_diagnostics(owned, **settings)
        rich = relation_status_report(owned, **settings)
        assert legacy['diagnostics'] == rich['diagnostics']
        assert legacy['exit_code'] == rich['exit_code'] == expected
        assert legacy['diagnostics'][0]['severity'] == severity
        assert legacy['validation_scope'] == 'supplied_relation_review_status_only'
        assert legacy['relation_statuses'][0] == {key: rich['relations'][0][key] for key in (
            'source_id', 'relation_id', 'target_id', 'status', 'reason',
            'selected_review_id', 'matching_review_ids', 'historical_review_ids')}


@pytest.mark.parametrize('kind,reason', [('missing', 'missing_relation_target'),
    ('self', 'self_relation_forbidden'), ('pair', 'relation_type_pair_forbidden'),
    ('canonical', 'noncanonical_symmetric_relation'), ('negative', 'current_review_rejected')])
@pytest.mark.parametrize('strict', [False, True])
def test_invalid_cannot_be_downgraded_by_permissive_active_profile(kind, reason, strict):
    source, target = endpoints()
    if kind == 'self':
        source['relations'] = [edge('depends_on', source['id'])]
    elif kind == 'pair':
        target = domain_value('need'); source['relations'] = [edge('addresses', target['id'])]
    elif kind == 'canonical':
        source['id'] = aid(number=2); target = domain_value('requirement', id=aid())
        source['relations'] = [edge('conflicts_with', target['id'])]
    records = [source] if kind == 'missing' else [source, target]
    if kind == 'negative': records.append(review(source, target, decision='rejected'))
    rows = [policy(kinds=('addresses', 'depends_on', 'conflicts_with'), status=state)
            for state in ('unreviewed', 'suspect')]
    owned = bound(records, rows, severity_overrides={'SRV025': 'info', 'SRV026': 'info'})
    before = dict(owned.source_files)
    with no_write_attempts():
        legacy = relation_review_diagnostics(owned, strict=strict)
        rich = relation_status_report(owned, source['id'], strict=strict)
    assert legacy['diagnostics'] == rich['diagnostics']
    for result in (legacy, rich):
        assert result['exit_code'] == 1 and result['status'] == 'failed'
        assert result['diagnostics'][0]['code'] == 'SRV027'
        assert result['diagnostics'][0]['severity'] == 'error'
        assert result['diagnostics'][0]['rationale'] == reason
        assert not result['approval_granted'] and not result['write_authorized']
    assert rich['relations'][0]['status'] == 'invalid'
    assert owned.source_files == before


@pytest.mark.parametrize('severity', ['info', 'warning'])
def test_global_invalid_downgrade_blocks_composition_before_query(severity):
    with pytest.raises(ProfileCompositionError) as error:
        composed(profile(severity_overrides={'SRV027': severity}))
    assert error.value.reason == 'profile_core_severity_lowered'


@pytest.mark.parametrize('value', [None, {}, 'unreviewed', [None]])
def test_malformed_review_policy_container_cannot_become_an_empty_policy(value):
    with pytest.raises(ProfileError):
        profile(relation_review_policy=value)


def test_default_composition_retains_original_absent_policy_projection():
    unchanged = composed()
    assert 'relation_review_policy' not in unchanged.data['merge']
    assert unchanged.relation_review_severity('addresses', 'draft', 'unreviewed') == 'warning'
    assert unchanged.relation_review_severity('addresses', 'draft', 'suspect') == 'warning'


def test_active_selection_excludes_inactive_policy_resources():
    permissive = profile('permissive', relation_review_policy=[policy()])
    strict = profile('strict', relation_review_policy=[policy(severity='error')])
    selected = composed(permissive, strict, project_profiles=[strict.key], cli_profiles=[permissive.key])
    assert selected.profile_chain == ('core@0.2.0', permissive.key)
    assert selected.relation_review_severity('addresses', 'draft', 'unreviewed') == 'info'


@pytest.mark.parametrize('reverse', [False, True])
def test_latest_history_projection_uses_exact_time_tie_and_highest_review_id(reverse):
    source, target = endpoints()
    older = review(source, target, number=20, time='2026-01-01T00:00:00.1Z')
    newer = review(source, target, number=21, time='2026-01-01T00:00:00.10Z', decision='rejected')
    records = [source, target, older, newer]
    if reverse: records.reverse()
    row = relation_status_report(bound(records))['relations'][0]
    assert row['latest_review']['id'] == row['selected_review']['id'] == newer['id']
    assert row['latest_review']['reviewed_at'] == '2026-01-01T00:00:00.10Z'
    assert row['status'] == 'invalid' and row['changes_since_latest_review'] == []


def test_passive_legacy_audit_gaps_remain_unknown_instead_of_invented():
    source, target = endpoints(); old = review(source, target)
    optional = ('source_id', 'target_id', 'source_revision', 'target_revision',
        'source_artifact_sha256', 'target_artifact_sha256')
    for key in (*optional, 'reviewed_at'): old.pop(key)
    row = relation_status_report(bound([source, target, old]))['relations'][0]
    assert row['status'] == 'current' and row['latest_review']['reviewed_at'] == old['created_at']
    assert all(row['latest_review'][key] is None for key in optional)
    assert row['current_source']['revision'] == source['revision']


def test_filter_does_not_hide_invalid_unrelated_history_input():
    source, target = endpoints(); invalid = review(source, target, relation_id=rid(2)); invalid.pop('decision')
    owned = bound([source, target, invalid])
    with no_write_attempts(), pytest.raises(ModelError):
        relation_status_report(owned, target['id'])


def test_filtered_report_excludes_other_edges_and_their_policy_failures():
    source, target = endpoints(); other = deepcopy(source)
    other['id'] = aid(number=2); other['maturity'] = 'proposed'
    other['relations'] = [edge('addresses', target['id'], number=2)]
    owned = bound([other, target, source], [policy(maturities=('draft',)),
        policy(maturities=('proposed',), severity='error')])
    selected = relation_status_report(owned, source['id'])
    incoming = relation_status_report(owned, target['id'])
    assert selected['exit_code'] == 0 and len(selected['diagnostics']) == 1
    assert [row['source_id'] for row in selected['relations']] == [source['id']]
    assert incoming['exit_code'] == 1 and len(incoming['diagnostics']) == 2
    assert [row['source_id'] for row in incoming['relations']] == sorted([source['id'], other['id']])


@pytest.mark.parametrize('query', [relation_review_diagnostics, relation_status_report])
def test_detached_effective_profile_cannot_change_owned_model_evaluation(query):
    source, target = endpoints(); owned = bound([source, target], [policy()])
    foreign = composed(profile(relation_review_policy=[policy(severity='error')]))
    object.__setattr__(owned, 'profile', foreign)
    with no_write_attempts(), pytest.raises(TargetError) as error:
        query(owned)
    assert error.value.reason == 'target_sources_changed'


def test_native_confirmation_and_retry_keep_requirement_proposed_and_bytes_unchanged(tmp_path):
    root = tmp_path / 'project'; original, source, _, gates = negative_project(root)
    core_data = original.profile_resources[0].data
    core_data['relation_review_policy'] = [policy(status=state) for state in ('unreviewed', 'suspect')]
    resource = ProfileResource(canonical_json_bytes(core_data))
    effective = compose_profiles([resource], core_key=resource.key, language_registry=original.language_registry)
    files = [ModelDocument(d.path, resource.source_bytes) if d.path == 'profiles/core.json' else d
             for d in original.resource_files]
    owned = TargetModel(original.configuration_bytes, original.binding, original.documents,
        profile=effective, resource_files=files, **original.reservations)
    for document in files: put(root, document.path, document.content)
    negative = call(owned, source, options(owned, gates)); live = current(root, owned)
    proposed = next(a for a in live.artifacts if a['id'] == source['id'])
    assert (proposed['maturity'], proposed['revision']) == ('proposed', 5)
    path = root / artifact_path('requirement', source['id'], 'SR')
    before = path.read_bytes(); old_review = (root / negative['path']).read_bytes()
    confirmed = coupled(live, proposed, gates, decision='confirmed', request='policy-confirmation')
    after = current(root, owned); inventory = file_inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError):
        rich = relation_status_report(after, source['id'], strict=True)
        legacy = relation_review_diagnostics(after, strict=True)
        replay = coupled(live, proposed, gates, decision='confirmed', request='policy-confirmation')
    row = next(r for r in rich['relations'] if r['relation_id'] == source['relations'][0]['relation_id'])
    assert row['status'] == 'current' and row['severity'] is None and row['required_repair'] == []
    assert row['source_maturity'] == 'proposed' and row['current_source']['revision'] == 5
    assert row['selected_review']['id'] == confirmed['review_id'] != negative['review_id']
    assert rich['diagnostics'] == legacy['diagnostics'] == []
    assert rich['exit_code'] == legacy['exit_code'] == 0
    assert not rich['approval_granted'] and not confirmed['approval_granted']
    assert path.read_bytes() == before and (path.stat().st_mode & 0o777) == 0o640
    assert (root / negative['path']).read_bytes() == old_review
    assert file_inventory(root) == inventory and replay['replayed']
    assert receipt(root, confirmed)['result_object']['published_paths'] == [confirmed['path']]
    assert replay['completion']['receipts'] == confirmed['completion']['receipts']
