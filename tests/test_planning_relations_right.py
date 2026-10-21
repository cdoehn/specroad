"""Planning graph boundaries and mandatory links at real writer gates."""
import json

import pytest

from specroad.authoring.relations import add_relation, remove_relation
from specroad.changes import ChangePlanError, TargetError, PublicationAuthority
from specroad.diagnostics import Diagnostic, ResultContractError
from specroad.graph.relation_obligations import RelationObligations, MinimumRelationRule
from specroad.lint.nonliteral import lint_core
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.model.relation_identity import RelationInventory
from specroad.planning import assess_planning_relations
from specroad.profiles import ProfileCompositionError
from specroad.validation import validate_model
from support.core_lint import sources
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.profiles import profile_data
from support.read_only import inventory, no_write_attempts
from support.relations import aid, edge
from support.targets import model, gate
from test_planning_relations import planning_values, stored


ALLOWED = [(kind, 'scheduled_for', target) for kind in ('capability', 'requirement', 'task')
           for target in ('release', 'milestone')] + [
    ('task', 'part_of', kind) for kind in ('release', 'milestone', 'capability')] + [
    ('milestone', 'part_of', 'release')] + [
    (kind, 'implemented_by', 'task') for kind in ('capability', 'requirement', 'decision')]


def endpoints(values, source_kind, target_kind):
    return (next(v for v in values if v['artifact_type'] == source_kind),
            next(v for v in values if v['artifact_type'] == target_kind))


@pytest.mark.parametrize('source_kind,kind,target_kind', ALLOWED)
def test_exact_planning_matrix_preserves_stored_direction_and_identity(source_kind, kind, target_kind):
    values = planning_values(); source, target = endpoints(values, source_kind, target_kind)
    if source_kind == 'milestone': source['relations'] = []
    relation = edge(kind, target['id'], number=100); source['relations'].append(relation)
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(): observed = assess_planning_relations(supplied).data
    actual, = [r for r in observed['relations'] if r['relation_id'] == relation['relation_id']]
    assert (actual['source_id'], actual['type'], actual['target_id']) == (source['id'], kind, target['id'])
    assert actual['relation_sha256'] == canonical_json_sha256(relation)
    assert supplied.source_files == before


@pytest.mark.parametrize('source_kind,kind,target_kind', [
    ('release', 'scheduled_for', 'milestone'), ('milestone', 'scheduled_for', 'release'),
    ('decision', 'scheduled_for', 'release'), ('task', 'scheduled_for', 'capability'),
    ('requirement', 'scheduled_for', 'task'), ('task', 'part_of', 'requirement'),
    ('release', 'part_of', 'milestone'), ('task', 'implemented_by', 'requirement'),
    ('milestone', 'implemented_by', 'task')])
def test_forbidden_planning_pairs_have_exact_source_locations(source_kind, kind, target_kind):
    values = planning_values(); source, target = endpoints(values, source_kind, target_kind)
    position = len(source['relations']); source['relations'].append(edge(kind, target['id'], number=100))
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises(ModelError) as error:
        assess_planning_relations(supplied)
    assert error.value.reason == 'relation_type_pair_forbidden'
    assert error.value.path == artifact_path(source_kind, source['id'], 'SR')
    assert error.value.pointer == '/relations/' + str(position) + '/target'
    assert supplied.source_files == before


@pytest.mark.parametrize('source_kind,kind,target_kind', [
    ('milestone', 'part_of', 'release'), ('requirement', 'scheduled_for', 'release'),
    ('requirement', 'implemented_by', 'task')])
def test_missing_planning_endpoints_are_not_synthesized(source_kind, kind, target_kind):
    values = planning_values(); source, _ = endpoints(values, source_kind, target_kind)
    if source_kind == 'milestone': source['relations'] = []
    position = len(source['relations']); source['relations'].append(edge(kind, aid(target_kind, 99), number=100))
    supplied = model(values)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        assess_planning_relations(supplied)
    assert error.value.reason == 'missing_relation_target'
    assert error.value.path == artifact_path(source_kind, source['id'], 'SR')
    assert error.value.pointer == '/relations/' + str(position) + '/target'


@pytest.mark.parametrize('other_release', [1, 2])
def test_two_milestone_links_are_not_deduplicated_or_arbitrarily_selected(other_release):
    values = planning_values(); milestone = values[2]
    milestone['relations'].append(edge('part_of', aid('release', other_release), number=100))
    with no_write_attempts(), pytest.raises(ModelError) as error:
        assess_planning_relations(model(values))
    assert error.value.reason == 'milestone_release_cardinality'
    assert error.value.path == artifact_path('milestone', milestone['id'], 'SR')
    assert error.value.pointer == '/relations'


def test_milestone_cannot_use_a_non_release_parent():
    values = planning_values(); milestone = values[2]
    milestone['relations'] = [edge('part_of', aid('capability', 1), number=100)]
    with no_write_attempts(), pytest.raises(ModelError) as error:
        assess_planning_relations(model(values))
    assert error.value.reason == 'milestone_release_reference'
    assert error.value.pointer == '/relations/0/target'


@pytest.mark.parametrize('defect,reason', [('reverse', 'noncanonical_symmetric_relation'),
                                        ('duplicate', 'duplicate_symmetric_relation')])
def test_unreported_symmetric_edges_still_use_the_common_graph_boundary(defect, reason):
    values = planning_values(); first, second = values[:2]
    if defect == 'reverse': second['relations'] = [edge('duplicates', first['id'], number=100)]
    else: first['relations'] = [edge('duplicates', second['id'], number=n) for n in (100, 101)]
    supplied = model(values); before = supplied.source_files
    with no_write_attempts(), pytest.raises(ModelError) as error:
        assess_planning_relations(supplied)
    assert error.value.reason == reason and error.value.pointer == '/relations'
    assert supplied.source_files == before


def test_supersedes_cycle_reports_original_relation_witnesses():
    values = planning_values(); first, second = values[:2]
    first['relations'] = [edge('supersedes', second['id'], number=100)]
    second['relations'] = [edge('supersedes', first['id'], number=101)]
    with no_write_attempts(), pytest.raises(ModelError) as error:
        assess_planning_relations(model(values))
    assert error.value.reason == 'relation_hierarchy_cycle'
    assert set(error.value.diagnostic()['relation_ids']) == {edge(number=n)['relation_id'] for n in (100, 101)}


def test_task_can_have_multiple_explicit_schedules_without_inheriting_milestone_cardinality():
    values = planning_values(); task = values[4]
    task['relations'] = [edge('scheduled_for', aid('release', n), number=100 + n) for n in (1, 2)]
    with no_write_attempts(): result = assess_planning_relations(model(values)).data
    actual = [r for r in result['relations'] if r['source_id'] == task['id']]
    assert {r['target_id'] for r in actual} == {aid('release', 1), aid('release', 2)}
    assert len(actual) == 2 and len({r['relation_id'] for r in actual}) == 2


@pytest.mark.parametrize('maturity', ['draft', 'proposed', 'in_review', 'approved', 'rejected', 'superseded', 'retired'])
def test_core_task_minimum_applies_at_approval_without_inventing_inverse_links(maturity):
    task = domain_value('task', maturity=maturity); records = sources([task])
    with no_write_attempts(): result = RelationObligations(records)
    if maturity != 'approved':
        assert result.checks == () and result.diagnostics == ()
        return
    check, = result.checks
    assert check.rule_id == 'core:task-implementation' and check.artifact_id == task['id']
    assert check.minimum == 1 and check.actual == 0 and not check.satisfied
    assert check.direction == 'incoming' and check.relation_types == ('implemented_by',)
    assert check.relation_ids == check.endpoint_ids == ()
    assert result.has_errors and not result.approval_granted and not result.review_status_checked


@pytest.mark.parametrize('subject_kind', ['requirement', 'decision', 'capability'])
def test_only_requirement_or_decision_implementation_fulfills_task_minimum(subject_kind):
    task = domain_value('task', maturity='approved')
    subject = domain_value(subject_kind, relations=[edge('implemented_by', task['id'], number=100)])
    with no_write_attempts(): result = RelationObligations(sources([task, subject]))
    check, = result.checks
    valid = subject_kind in ('requirement', 'decision')
    assert check.satisfied is valid and result.has_errors is (not valid)
    assert check.relation_ids == ((edge(number=100)['relation_id'],) if valid else ())
    assert check.endpoint_ids == ((subject['id'],) if valid else ())


@pytest.mark.parametrize('severity', ['info', 'warning', 'error'])
def test_permissive_profile_minimum_cannot_remove_core_task_obligation(severity):
    records = sources([domain_value('task', maturity='approved')])
    rule = MinimumRelationRule('profile:optional-task', artifact_types=['task'],
        relation_types=['implemented_by'], direction='incoming', minimum=0, severity=severity)
    with no_write_attempts(): result = RelationObligations(records, profile_rules=[rule])
    finding, = result.diagnostics
    assert finding['rule_id'] == 'core:task-implementation' and finding['severity'] == 'error'
    assert result.has_errors


@pytest.mark.parametrize('severity', ['info', 'warning'])
def test_core_task_error_cannot_be_downgraded_by_profile_or_diagnostic(severity):
    with pytest.raises(ProfileCompositionError):
        model([domain_value('task')], profiles=[profile_data(profile_id='core',
            severity_overrides={'core:task-implementation': severity})])
    with pytest.raises(ResultContractError):
        Diagnostic('CUSTOM', severity, 'planning', 'Missing link', rule_id='core:task-implementation')


@pytest.mark.parametrize('fail_on,strict', [('error', False), ('warning', False), ('error', True)])
def test_core_lint_retains_missing_task_link_as_blocking_finding(fail_on, strict):
    task = domain_value('task', maturity='approved')
    with no_write_attempts(): result = lint_core(sources([task]), fail_on=fail_on, strict=strict)
    finding, = result['diagnostics']
    assert finding['code'] == 'SRV030' and finding['severity'] == 'error'
    assert finding['rule_id'] == 'core:task-implementation' and finding['origin'] == 'core_rule'
    assert finding['path'] == artifact_path('task', task['id'], 'SR') and finding['pointer'] == '/relations'
    assert not result['core_checks_passed'] and not result['approval_granted']


def test_common_model_validation_cannot_be_overridden_by_successful_host_gates():
    task = domain_value('task', maturity='approved'); supplied = model([task])
    with no_write_attempts():
        result = validate_model(supplied.documents, profile=supplied.profile,
            gates=[gate('lifecycle'), gate('language_policy'), gate('extension:permissive')])
    stage, = [s for s in result.data['stages'] if s['stage'] == 'minimum_relations']
    assert stage['status'] == 'failed' and not result.passed
    assert stage['diagnostics'][0]['rule_id'] == 'core:task-implementation'


def options(calls):
    def authorize(request): calls.append(request); return True
    return dict(actor={'actor_type': 'human', 'actor_id': 'planning-editor'},
        planned_at='2026-10-21T14:00:00Z', change_plan_id='CP-planning-right',
        transaction_id='planning-right', request_id='planning-right',
        authority=PublicationAuthority('planning-host', '1', authorize))


@pytest.mark.parametrize('defect', ['multiple_release', 'missing_release', 'wrong_schedule', 'missing_target'])
def test_native_writer_rejects_invalid_planning_without_authorization_or_file_changes(tmp_path, defect):
    values = planning_values(); root = tmp_path / 'project'; supplied = stored(root, values)
    before = inventory(root); calls = []; opts = options(calls)
    ids = RelationInventory([r['relation_id'] for a in supplied.artifacts for r in a['relations']], (), ())
    with pytest.raises(ChangePlanError) as error:
        if defect == 'missing_release':
            source = values[2]; relation = source['relations'][0]
            remove_relation(supplied, source['id'], relation['relation_id'],
                expected_sha256=canonical_json_sha256(relation), reason='Remove assignment.', **opts)
        elif defect == 'multiple_release':
            add_relation(supplied, values[2]['id'], 'part_of', values[1]['id'], inventory=ids, **opts)
        elif defect == 'wrong_schedule':
            add_relation(supplied, values[4]['id'], 'scheduled_for', values[5]['id'], inventory=ids, **opts)
        else:
            add_relation(supplied, values[4]['id'], 'scheduled_for', aid('release', 99), inventory=ids, **opts)
    assert error.value.reason == {'multiple_release': 'milestone_release_cardinality',
        'missing_release': 'milestone_release_cardinality', 'wrong_schedule': 'relation_type_pair_forbidden',
        'missing_target': 'missing_relation_target'}[defect]
    assert calls == [] and inventory(root) == before


@pytest.mark.parametrize('remaining_kind', [None, 'capability', 'requirement', 'decision'])
def test_removing_last_required_incoming_task_link_is_blocked_by_common_writer(tmp_path, remaining_kind):
    task = domain_value('task', maturity='approved')
    source = domain_value('requirement', id=aid('requirement', 1),
        relations=[edge('implemented_by', task['id'], number=100)])
    values = [source, task]
    if remaining_kind is not None:
        values.append(domain_value(remaining_kind, id=aid(remaining_kind, 2),
            relations=[edge('implemented_by', task['id'], number=101)]))
    root = tmp_path / 'project'; supplied = stored(root, values); before = inventory(root)
    calls = []; relation = source['relations'][0]
    def remove():
        return remove_relation(supplied, source['id'], relation['relation_id'],
            expected_sha256=canonical_json_sha256(relation), reason='Remove one implementation link.',
            gates=[gate('lifecycle')], **options(calls))
    if remaining_kind not in ('requirement', 'decision'):
        with pytest.raises(TargetError) as error: remove()
        assert error.value.reason == 'complete_target_validation_required'
        assert calls == [] and inventory(root) == before
    else:
        result = remove()
        assert result['write_state'] == 'committed' and calls
        source_path = artifact_path('requirement', source['id'], 'SR')
        actual = json.loads((root / source_path).read_bytes())
        assert actual['relations'] == [] and actual['revision'] == source['revision'] + 1
        for name, raw in supplied.source_files.items():
            if name != source_path: assert (root / name).read_bytes() == raw


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_missing_approved_task_link_is_equally_blocking_in_isolated_core_and_pyz(tmp_path, mode):
    task = domain_value('task', maturity='approved')
    body = '''import json
from specroad.graph.relations import SourceRelations
from specroad.lint.nonliteral import lint_core
value = ''' + repr(task) + '''
result=lint_core([SourceRelations(json.dumps(value).encode())])
print(json.dumps({'passed':result['core_checks_passed'],'findings':[
 [d['rule_id'],d['code'],d['severity'],d['actual']] for d in result['diagnostics']]}))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'passed': False,
        'findings': [['core:task-implementation', 'SRV030', 'error', 0]]}
