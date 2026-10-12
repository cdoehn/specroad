"""Direct current-project neighbours and observed review states, without writes."""
from copy import deepcopy
from unittest.mock import patch
import importlib
import json

import pytest

from specroad.changes import project_lock
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.model.canonical import canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.model.schema_catalog import SchemaCatalog
from specroad.query import impact_artifact
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.model import configuration_file, put
from support.portable import build_distribution
from support.processes import run_cli, run_python
from support.project_locks import options
from support.read_only import inventory, make_project, no_write_attempts
from support.relations import aid, artifact, edge, rid
from test_relation_review_status import review

impact_module = importlib.import_module('specroad.query.impact')


def history(source, target, relation, *, number, decision='confirmed'):
    return review(source, target, number=number, decision=decision,
                  relation_id=relation['relation_id'],
                  relation_content_sha256=canonical_json_sha256(relation))


def mixed_graph(*, rejected=True):
    start = domain_value('requirement', id=aid(), relations=[
        edge('addresses', aid('goal'), 1), edge('derived_from', aid('need'), 2),
        edge('depends_on', aid(number=2), 3), edge('derived_from', aid('source'), 4)])
    need = domain_value('need', id=aid('need'), relations=[])
    changed = domain_value('requirement', id=aid(number=2), relations=[])
    source = artifact('source', source_kind='document', locator='owned:source',
        captured_at='2026-01-01T00:00:00Z', relations=[edge('references', aid(number=4), 7)])
    reviews = [history(start, need, start['relations'][1], number=20),
               history(start, changed, start['relations'][2], number=21),
               history(start, source, start['relations'][3], number=22,
                       decision='rejected' if rejected else 'confirmed')]
    changed['statement'] = 'A changed endpoint assertion.'
    return [start, need, changed, source,
            domain_value('requirement', id=aid(number=3), relations=[edge('depends_on', aid(), 6)]),
            domain_value('requirement', id=aid(number=4), relations=[]),
            domain_value('goal', id=aid('goal'), relations=[]),
            domain_value('requirement', id=aid(number=5), relations=[edge('refines', aid(), 5)]),
            domain_value('goal', id=aid('goal', 3), relations=[]), *reviews]


def project(root, values=None, **configuration):
    root.mkdir()
    return make_project(root, *(mixed_graph() if values is None else values), **configuration)


def connections(data):
    return [(group['relation_type'], connection) for group in data['groups']
            for connection in group['connections']]


def test_all_direct_incoming_outgoing_neighbours_are_grouped_by_stored_type(tmp_path):
    root = project(tmp_path / 'project')
    outcome = impact_artifact(root, aid())
    assert outcome.exit_code == 1 and outcome.complete
    data = outcome.as_dict()['result']
    expected = {
        ('addresses', rid(1), aid('goal'), 'outgoing', 'unreviewed'),
        ('derived_from', rid(2), aid('need'), 'outgoing', 'current'),
        ('depends_on', rid(3), aid(number=2), 'outgoing', 'suspect'),
        ('derived_from', rid(4), aid('source'), 'outgoing', 'invalid'),
        ('refines', rid(5), aid(number=5), 'incoming', 'unreviewed'),
        ('depends_on', rid(6), aid(number=3), 'incoming', 'unreviewed')}
    assert {(kind, c['relation_id'], c['related_id'], c['direction'], c['review_status'])
            for kind, c in connections(data)} == expected
    assert [g['relation_type'] for g in data['groups']] == ['addresses', 'depends_on', 'derived_from', 'refines']
    for group in data['groups']:
        assert group['artifact_ids'] == sorted({c['related_id'] for c in group['connections']})
        assert group['connections'] == sorted(group['connections'], key=lambda c: (
            c['related_id'], c['direction'], c['relation_id']))
        assert all(c['related_present'] for c in group['connections'])
    assert aid(number=4) not in {c['related_id'] for _, c in connections(data)}
    assert data['artifact_id'] == aid() and data['depth'] == 1 and data['transitive'] is False
    assert data['coverage']['source_count'] == 12 and data['coverage']['relation_count'] == 7
    assert data['coverage']['review_record_count'] == 3 and not data['coverage']['atomic_snapshot']


def test_review_groups_explain_original_endpoints_and_current_rejection(tmp_path):
    root = project(tmp_path / 'project'); outcome = impact_artifact(root, aid())
    data = outcome.as_dict()['result']; groups = data['review_groups']
    assert groups == {
        'unreviewed': {'relation_ids': [rid(1), rid(5), rid(6)],
                      'affected_ids': sorted([aid(), aid('goal'), aid(number=5), aid(number=3)])},
        'current': {'relation_ids': [rid(2)], 'affected_ids': sorted([aid(), aid('need')])},
        'suspect': {'relation_ids': [rid(3)], 'affected_ids': sorted([aid(), aid(number=2)])},
        'invalid': {'relation_ids': [rid(4)], 'affected_ids': sorted([aid(), aid('source')])}}
    rows = {c['relation_id']: c for _, c in connections(data)}
    assert rows[rid(2)]['selected_review_id'] == aid('relation_review', 20)
    assert rows[rid(2)]['matching_review_ids'] == [aid('relation_review', 20)]
    assert rows[rid(3)]['selected_review_id'] is None and rows[rid(3)]['matching_review_ids'] == []
    assert rows[rid(3)]['historical_review_ids'] == [aid('relation_review', 21)]
    assert rows[rid(4)]['review_reason'] == 'current_review_rejected'
    assert rows[rid(4)]['selected_review_id'] == aid('relation_review', 22)
    assert rows[rid(5)]['source_id'] == aid(number=5) and rows[rid(5)]['target_id'] == aid()
    findings = {next(name for name in d.related_ids if name.startswith('REL-')): d for d in outcome.diagnostics}
    assert set(findings) == {rid(1), rid(3), rid(4), rid(5), rid(6)}
    assert (findings[rid(4)].code, findings[rid(4)].severity, findings[rid(4)].category) == (
        'SRV027', 'error', 'review_outcome')
    assert findings[rid(3)].code == 'SRV026' and findings[rid(1)].code == 'SRV025'
    summary = outcome.as_dict()['summary']
    assert summary['complete'] and not summary['approval_granted'] and not summary['write_authorized']
    assert not summary['full_semantic_validation'] and not summary['profile_policy_applied']


@pytest.mark.parametrize('kind,reason', [('missing', 'missing_relation_target'),
    ('self', 'self_relation_forbidden'), ('pair', 'relation_type_pair_forbidden'),
    ('canonical', 'noncanonical_symmetric_relation')])
def test_structural_invalid_edges_remain_visible_with_exact_cause(tmp_path, kind, reason):
    start = domain_value('requirement', id=aid(), relations=[edge('addresses', aid('goal'))])
    target = domain_value('goal', id=aid('goal'), relations=[])
    if kind == 'self':
        start['relations'][0].update(type='depends_on', target=aid())
    elif kind == 'pair':
        start['relations'][0]['type'] = 'verified_by'
    elif kind == 'canonical':
        start = domain_value('goal', id=aid('goal', 2), relations=[edge('conflicts_with', aid('goal'))])
    values = [start] if kind == 'missing' else [start, target]
    root = project(tmp_path / 'project', values)
    outcome = impact_artifact(root, start['id']); assert outcome.exit_code == 1 and outcome.complete
    data = outcome.as_dict()['result']; rows = [c for _, c in connections(data)]
    assert len(rows) == (2 if kind == 'self' else 1)
    assert all(c['review_status'] == 'invalid' and c['review_reason'] == reason for c in rows)
    assert all(c['selected_review_id'] is None and not c['matching_review_ids'] for c in rows)
    assert {c['related_present'] for c in rows} == {kind != 'missing'}
    assert data['review_groups']['invalid']['relation_ids'] == [rid()]
    finding, = outcome.diagnostics
    assert (finding.code, finding.severity, finding.category, finding.rationale) == (
        'SRV027', 'error', 'relation_structure', reason)


def test_symmetric_edge_keeps_one_normative_identity_and_physical_direction(tmp_path):
    values = [domain_value('goal', id=aid('goal'), relations=[edge('conflicts_with', aid())]),
              domain_value('requirement', id=aid(), relations=[])]
    root = project(tmp_path / 'project', values)
    for start, related, direction in [(aid(), aid('goal'), 'incoming'), (aid('goal'), aid(), 'outgoing')]:
        outcome = impact_artifact(root, start); assert outcome.exit_code == 0
        (kind, row), = connections(outcome.as_dict()['result'])
        assert (kind, row['relation_id'], row['related_id'], row['direction']) == (
            'conflicts_with', rid(), related, direction)
        assert row['source_id'] == aid('goal') and row['target_id'] == aid()


def test_distinct_relation_identities_to_one_neighbour_are_all_retained(tmp_path):
    values = [domain_value('requirement', id=aid(), relations=[edge('depends_on', aid(number=2), 1),
              edge('depends_on', aid(number=2), 2), edge('refines', aid(number=2), 3)]),
              domain_value('requirement', id=aid(number=2), relations=[])]
    root = project(tmp_path / 'project', values)
    data = impact_artifact(root, aid()).as_dict()['result']
    assert {c['relation_id'] for _, c in connections(data)} == {rid(1), rid(2), rid(3)}
    assert [g['artifact_ids'] for g in data['groups']] == [[aid(number=2)], [aid(number=2)]]


def test_isolated_artifact_has_complete_empty_groups_and_unknown_start_is_error(tmp_path):
    root = project(tmp_path / 'project', [domain_value('goal', id=aid('goal'), relations=[])])
    outcome = impact_artifact(root, aid('goal')); assert outcome.exit_code == 0 and outcome.complete
    data = outcome.as_dict()['result']; assert data['groups'] == []
    assert all(group == {'relation_ids': [], 'affected_ids': []} for group in data['review_groups'].values())
    unknown = impact_artifact(root, aid()); assert unknown.exit_code == 3 and not unknown.complete
    assert unknown.as_dict()['result'] is None


def test_unrelated_invalid_relation_is_outside_the_direct_assessment(tmp_path):
    values = [domain_value('goal', id=aid('goal'), relations=[]),
              domain_value('requirement', id=aid(), relations=[edge('depends_on', aid(number=999))])]
    root = project(tmp_path / 'project', values)
    outcome = impact_artifact(root, aid('goal'))
    assert outcome.exit_code == 0 and outcome.complete and not outcome.diagnostics
    assert outcome.as_dict()['result']['groups'] == []
    assert outcome.as_dict()['result']['coverage']['relation_count'] == 1
    assert outcome.as_dict()['summary']['full_semantic_validation'] is False


@pytest.mark.parametrize('field', ['statement', 'tags', 'maturity'])
def test_currentness_uses_endpoint_context_not_unrelated_workflow_metadata(tmp_path, field):
    start = domain_value('requirement', id=aid(), relations=[edge('addresses', aid('goal'))])
    target = domain_value('goal', id=aid('goal'), relations=[])
    record = review(start, target)
    target[field] = {'statement': 'Changed assertion.', 'tags': ['changed'], 'maturity': 'proposed'}[field]
    root = project(tmp_path / 'project', [start, target, record])
    outcome = impact_artifact(root, aid()); assert outcome.exit_code == 0
    row = connections(outcome.as_dict()['result'])[0][1]
    assert row['review_status'] == ('suspect' if field == 'statement' else 'current')


def test_new_matching_confirmation_replaces_rejection_without_mutating_history(tmp_path):
    start = domain_value('requirement', id=aid(), relations=[edge('addresses', aid('goal'))])
    target = domain_value('goal', id=aid('goal'), relations=[])
    rejected = review(start, target, decision='rejected')
    confirmed = review(start, target, number=21, time='2027-01-01T00:00:00Z')
    root = project(tmp_path / 'project', [start, target, rejected, confirmed]); before = inventory(root)
    outcome = impact_artifact(root, aid()); assert outcome.exit_code == 0
    row = connections(outcome.as_dict()['result'])[0][1]
    assert row['review_status'] == 'current' and row['selected_review_id'] == confirmed['id']
    assert row['historical_review_ids'] == [rejected['id'], confirmed['id']]
    assert inventory(root) == before


def test_incoming_count_targets_do_not_truncate_direct_neighbours(tmp_path):
    values = [domain_value('goal', id=aid('goal'), relations=[])] + [
        domain_value('requirement', id=aid(number=n), relations=[edge('addresses', aid('goal'), n)])
        for n in range(1, 130)]
    root = project(tmp_path / 'project', values, resource_limits={'artifact_count': 1, 'relation_count': 1})
    outcome = impact_artifact(root, aid('goal')); assert outcome.exit_code == 0
    rows = connections(outcome.as_dict()['result'])
    assert len(rows) == 129 and {c['related_id'] for _, c in rows} == {aid(number=n) for n in range(1, 130)}


@pytest.mark.parametrize('change', ['review', 'unrelated', 'configuration', 'membership'])
def test_changes_after_calculation_prevent_stale_success(tmp_path, change):
    values = mixed_graph(rejected=False); root = project(tmp_path / 'project', values)
    original = impact_module._impact_rows

    def changed(records, start):
        result = original(records, start)
        if change == 'configuration':
            configuration_file(root, resource_limits={'artifact_count': 7})
        elif change == 'membership':
            value = domain_value('goal', id=aid('goal', 99), relations=[])
            put(root, artifact_path('goal', value['id'], 'SR'), artifact_bytes(value))
        else:
            value = deepcopy(values[-1] if change == 'review' else values[5])
            value['reason' if change == 'review' else 'statement'] = 'Changed after calculation.'
            put(root, artifact_path(value['artifact_type'], value['id'], 'SR'), artifact_bytes(value))
        return result

    with patch.object(impact_module, '_impact_rows', changed):
        outcome = impact_artifact(root, aid())
    assert outcome.exit_code == 6 and not outcome.complete and outcome.as_dict()['result'] is None


@pytest.mark.parametrize('bad', ['malformed_unrelated', 'invalid_review'])
def test_unreadable_inventory_or_malformed_review_cannot_be_partial_success(tmp_path, bad):
    values = mixed_graph(); root = project(tmp_path / 'project', values)
    value = deepcopy(values[-1] if bad == 'invalid_review' else values[5])
    raw = b'{' if bad == 'malformed_unrelated' else artifact_bytes({**value, 'decision': 'maybe'})
    put(root, artifact_path(value['artifact_type'], value['id'], 'SR'), raw)
    outcome = impact_artifact(root, aid())
    assert outcome.exit_code == 3 and not outcome.complete and outcome.as_dict()['result'] is None


def test_active_writer_and_unresolved_journal_block_before_impact(tmp_path):
    root = project(tmp_path / 'project')
    (root / '.specroad/locks').mkdir(parents=True)
    with project_lock(root, **options()):
        with patch.object(impact_module, '_impact_rows', side_effect=AssertionError('unsafe read')):
            outcome = impact_artifact(root, aid())
        assert outcome.exit_code == 5
    put(root, '.specroad/transactions/pending.json', b'{}')
    with patch.object(impact_module, '_impact_rows', side_effect=AssertionError('unsafe read')):
        outcome = impact_artifact(root, aid())
    assert outcome.exit_code == 5


@pytest.mark.parametrize('rejected', [False, True])
def test_python_cli_request_and_native_process_deliver_identical_machine_results(tmp_path, rejected):
    root = project(tmp_path / 'project', mixed_graph(rejected=rejected))
    direct = impact_artifact(root, aid())
    cli = dispatch_result(['impact', aid(), '--project', str(root), '--format=json'])
    request = execute_request({'command_id': 'impact',
        'arguments': {'id': aid()}, 'options': {'--project': str(root), '--format': 'json'}}).result
    process = run_cli(['impact', aid(), '--project', str(root), '--format=json'], root, capture=True)
    assert direct.exit_code == cli.exit_code == request.exit_code == process.returncode == int(rejected)
    assert direct.as_dict()['result'] == cli.as_dict()['result'] == request.as_dict()['result'] == json.loads(process.stdout)['result']
    assert direct.complete and cli.complete and request.complete


def test_portable_zipapp_returns_the_same_complete_impact(tmp_path):
    root = project(tmp_path / 'project', mixed_graph(rejected=False))
    build_distribution(tmp_path / 'distribution')
    process = run_python(['-I', '-S', '-B', str(tmp_path / 'distribution/specroad.pyz'),
                         'impact', aid(), '--project', str(root), '--format=json'], root, capture=True)
    assert process.returncode == 0
    assert json.loads(process.stdout)['result'] == impact_artifact(root, aid()).as_dict()['result']


def test_public_impact_attempts_no_writes_processes_entropy_stdin_or_writer_lock(tmp_path):
    root = project(tmp_path / 'project'); before = inventory(root)
    with no_write_attempts(), patch('builtins.input', side_effect=AssertionError('stdin')), \
            patch('secrets.token_bytes', side_effect=AssertionError('entropy')), \
            patch('specroad.changes.locking.LockFiles.acquire', side_effect=AssertionError('lock')):
        direct = impact_artifact(root, aid())
        cli = dispatch_result(['impact', aid(), '--project', str(root)])
    assert direct.exit_code == cli.exit_code == 1 and direct.complete and cli.complete
    assert inventory(root) == before and not (root / '.specroad').exists()


def test_machine_results_are_owned_and_registry_describes_actual_scope(tmp_path):
    root = project(tmp_path / 'project'); outcome = impact_artifact(root, aid())
    expected = outcome.as_dict()['result']; changed = outcome.as_dict()['result']
    changed['groups'].clear(); changed['review_groups']['invalid']['relation_ids'].clear()
    assert outcome.as_dict()['result'] == expected == impact_artifact(root, aid()).as_dict()['result']
    registry = builtin_registry(); command = registry.resolve('impact')
    assert command.command_class.value == 'read_only' and command.preflight_profile.value == 'project_read'
    assert command.effect_scope.value == 'none' and command.requires_project
    description = dispatch_result(['command', 'describe', 'impact']).as_dict()['result']
    assert description['stdout']['result_schema'] == 'artifact-impact-v1'
    assert description['work']['continuation_supported'] is False
    schema = SchemaCatalog(registry).show('artifact-impact-v1')['schema']
    assert set(schema['required']) == set(expected) and schema['additionalProperties'] is False
    assert dispatch_result(['impact', '--project', str(root)]).exit_code == 2
    assert dispatch_result(['impact', aid(), '--depth=2', '--project', str(root)]).exit_code == 2
