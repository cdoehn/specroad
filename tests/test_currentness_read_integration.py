"""One explicit evidence/code/review observation across read-only consumers."""
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from specroad.cli.result_schemas import validate_result_document
from specroad.documents.builtin_views import resolve_builtin_view, BuiltinViewProviderError
from specroad.graph.comparison_values import ComparisonInputs
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.query import impact_artifact, trace_artifact, NormalizedQuery, query_records
from specroad.query.project_diff import diff_project
from specroad.query.semantic_diff import compare_semantic
from specroad.security import ProjectBoundary
from specroad.storage.record_artifact import RecordArtifact
from specroad.validation import validate_model, ValidationResources
from specroad.verification import (CurrentnessReadInput, prepare_currentness_read_input,
    prepare_verification_read_input, assess_code_reference, assess_verification_coverage)
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import ref, record_value
from support.relations import edge
from support.targets import model
from test_query_impact import mixed_graph
from test_verification_aggregation import scenario, NOW
from test_verification_coverage import records_for
from test_verification_evaluation import INPUTS
from test_verification_run_selection import observation


def verification_for(supplied, evaluation, configuration_id=None):
    return prepare_verification_read_input(supplied, evaluation,
        configuration_id=configuration_id, inputs=dict(INPUTS),
        input_roles={path: 'input' for path in INPUTS}, evaluated_at=NOW)


def case(root, *, code='current', evidence='passed'):
    records, evaluation, cfg, key = scenario(configured=False, policy='independent')
    coderef = record_value('code_ref', path='src/owned.data', file_sha256=sha256(b'KEEP\n').hexdigest())
    if code == 'relocated':
        coderef.update(reference_kind='line_range', start_line=1, end_line=1,
            encoding='utf-8', selection_sha256=sha256(b'KEEP\n').hexdigest())
    records[0]['relations'].append(edge('implemented_by', coderef['id'], 91))
    records.append(coderef)
    if evidence not in ('missing', 'no_evaluation'):
        item = observation(records, evaluation, key, run='ci:expected',
            result='failed' if evidence == 'failed' else 'passed')
        item['configuration_policy'] = 'independent'
        if evidence == 'stale':
            item['subjects'][0]['verification_context_sha256'] = 'f' * 64
        records.append(item)
    supplied = model(records)
    root.mkdir()
    for path, raw in supplied.source_files.items():
        put(root, path, raw)
    if code != 'missing':
        put(root, coderef['path'], {'current': b'KEEP\n', 'stale': b'CHANGED\n',
                                  'relocated': b'prefix\nKEEP\n'}[code])
    native = next(RecordArtifact(d.content, path=d.path) for d in supplied.documents
                  if d.path.endswith(coderef['id'] + '.json'))
    state = assess_code_reference(ProjectBoundary(root), native)
    verification = verification_for(supplied, None if evidence == 'no_evaluation' else evaluation, cfg)
    currentness = prepare_currentness_read_input(supplied, verification, code_states=[state])
    return supplied, verification, currentness, state


def consumed(supplied, currentness, root):
    records = records_for(supplied)
    compared = compare_semantic(ComparisonInputs(supplied.binding.project_id, records),
        ComparisonInputs(supplied.binding.project_id, records),
        before_configuration=supplied.configuration, after_configuration=supplied.configuration,
        before_currentness=currentness, after_currentness=currentness).data
    validation = validate_model(supplied.documents,
        resources=ValidationResources(supplied.configuration_bytes), currentness=currentness).data
    impact = impact_artifact(root, ref(), currentness=currentness)
    trace = trace_artifact(root, ref(), direction='both', depth=2, currentness=currentness)
    assert impact.exit_code == trace.exit_code == 0
    return {
        'validation': validation,
        'coverage': assess_verification_coverage(supplied, currentness=currentness).data,
        'verification': resolve_builtin_view(supplied, 'verification', currentness=currentness).data,
        'traceability': resolve_builtin_view(supplied, 'traceability', currentness=currentness).data,
        'impact': impact.as_dict()['result'], 'trace': trace.as_dict()['result'],
        'diff': compared}


@pytest.mark.parametrize('code', ['current', 'stale', 'missing', 'relocated'])
@pytest.mark.parametrize('evidence,expected', [
    ('passed', 'passed'), ('failed', 'failed'), ('stale', 'stale'),
    ('missing', 'incomplete'), ('no_evaluation', 'incomplete')])
def test_all_consumers_share_exact_states_without_subject_writes(tmp_path, code, evidence, expected):
    root = tmp_path / 'project'
    supplied, verification, currentness, state = case(root, code=code, evidence=evidence)
    before = inventory(root)
    with no_write_attempts():
        reports = consumed(supplied, currentness, root)
    assert inventory(root) == before
    for name, report in reports.items():
        observed = report['currentness']['after'] if name == 'diff' else report['currentness']
        assert observed == currentness.observation
        data = observed['observation']
        assert data['code_states'][0]['state'] == code
        assert data['code_states'][0]['assessment_sha256'] == state.sha256
        assert data['coverage']['totals']['verification_results'] == {expected: 1}
        assert data['coverage']['summary'] == verification.summary
        assert data['coverage']['selection_status'] == ('missing' if evidence == 'no_evaluation' else 'selected')
        assert not any(data[k] for k in ('project_files_verified', 'atomic_snapshot',
            'external_run_verified', 'release_readiness_evaluated', 'source_code_executed',
            'write_authorized', 'approval_granted'))
    assert reports['traceability']['rows'][0]['verification_result'] == expected
    assert reports['traceability']['rows'][0]['release_readiness'] is None
    assert reports['traceability']['computed_reports']['verification']['status'] == 'computed'
    assert reports['traceability']['computed_reports']['verification']['result'] == currentness.data['coverage']
    assert reports['verification']['rows'][0]['verification_result'] == expected
    with no_write_attempts():
        page = query_records(records_for(supplied), NormalizedQuery(
            evaluation=currentness.verification.data['evaluation'],
            filters={'type': ['requirement'], 'verification_result': [expected]},
            select=['/verification_result']), project=supplied.configuration.data,
            verification=currentness.verification)
    assert page.data['total'] == 1 and page.data['items'][0]['id'] == ref()
    assert page.evaluation_binding == verification.summary
    assert reports['validation']['checks_complete'] is False
    assert reports['validation']['model_valid'] is not True
    assert reports['diff']['changed'] is False
    for name in ('impact', 'trace', 'diff'):
        validate_result_document('artifact-' + name + '-v1', reports[name])


def test_code_only_change_is_a_diff_even_with_identical_model_bytes(tmp_path):
    left, _, before, _ = case(tmp_path / 'before')
    right, _, after, _ = case(tmp_path / 'after', code='stale')
    assert left.source_files == right.source_files
    with no_write_attempts():
        result = diff_project(tmp_path / 'after', str(tmp_path / 'before'), against_kind='local',
            before_currentness=before, after_currentness=after)
    assert result.exit_code == 0
    data = result.as_dict()['result']
    assert data['changes'] == [] and data['changed'] is True
    assert data['categories'] == ['currentness_changed']
    assert data['currentness'] == {'before': before.observation, 'after': after.observation, 'changed': True}
    assert data['evidence_currency']['before_sha256'] == data['evidence_currency']['after_sha256']
    assert data['currentness_inputs'] == {'before_sha256': before.sha256, 'after_sha256': after.sha256}


def test_missing_and_stale_code_remain_distinct_in_diff(tmp_path):
    _, _, missing, _ = case(tmp_path / 'before', code='missing')
    _, _, stale, _ = case(tmp_path / 'after', code='stale')
    result = diff_project(tmp_path / 'after', str(tmp_path / 'before'), against_kind='local',
        before_currentness=missing, after_currentness=stale)
    assert result.exit_code == 0
    data = result.as_dict()['result']['currentness']
    assert data['before']['observation']['code_states'][0]['reason'] == 'target_missing'
    assert data['after']['observation']['code_states'][0]['reason'] == 'file_changed'


def test_review_groups_keep_all_four_states_and_affected_endpoints(tmp_path):
    supplied = model(mixed_graph())
    value = prepare_currentness_read_input(supplied, verification_for(supplied, None))
    expected = {'current': 1, 'unreviewed': 4, 'suspect': 1, 'invalid': 1}
    observations = [
        assess_verification_coverage(supplied, currentness=value).data,
        resolve_builtin_view(supplied, 'traceability', currentness=value).data,
        resolve_builtin_view(supplied, 'verification', currentness=value).data,
        validate_model(supplied.documents, resources=ValidationResources(supplied.configuration_bytes),
                       currentness=value).data]
    for report in observations:
        data = report['currentness']['observation']
        for state, count in expected.items():
            group = data['review_groups'][state]
            assert len(group['relation_ids']) == count
            assert group['affected_ids'] == sorted({r[k] for r in data['relation_reviews']['relations']
                if r['status'] == state for k in ('source_id', 'target_id')})


@pytest.mark.parametrize('bad', ['omitted', 'duplicate', 'dict', 'callback', 'extra', 'other_bytes'])
def test_code_inventory_must_be_complete_native_and_exactly_bound(tmp_path, bad):
    supplied, verification, _, state = case(tmp_path / 'project')
    states = [state]
    if bad == 'omitted': states = []
    if bad == 'duplicate': states = [state, state]
    if bad == 'dict': states = [state.data]
    if bad == 'callback': states = lambda: [state]
    if bad in ('extra', 'other_bytes'):
        changed = state.data['reference']
        if bad == 'extra': changed['id'] = ref('CODE', '1')
        else: changed['title'] = 'Other source bytes'
        states.append(assess_code_reference(ProjectBoundary(tmp_path / 'project'),
            RecordArtifact(canonical_json_bytes(changed))))
    with pytest.raises(ModelError):
        prepare_currentness_read_input(supplied, verification, code_states=states)


@pytest.mark.parametrize('consumer', ['validation', 'coverage', 'verification', 'traceability', 'impact', 'trace', 'diff'])
def test_foreign_record_bytes_are_rejected_without_partial_observation(tmp_path, consumer):
    root = tmp_path / 'project'
    supplied, _, value, _ = case(root)
    changed = [r.data for r in records_for(supplied)]
    next(r for r in changed if r['id'] == ref())['statement'] = 'Different subject'
    other = model(changed)
    if consumer in ('impact', 'trace', 'diff'):
        for path, raw in other.source_files.items(): put(root, path, raw)
        if consumer == 'impact': result = impact_artifact(root, ref(), currentness=value)
        elif consumer == 'trace':
            result = trace_artifact(root, ref(), direction='both', depth=2, currentness=value)
        else:
            result = diff_project(root, str(root), against_kind='local',
                before_currentness=value, after_currentness=value)
        assert result.exit_code == 3 and result.as_dict()['result'] is None
        return
    with pytest.raises(ModelError):
        if consumer == 'validation':
            validate_model(other.documents, resources=ValidationResources(other.configuration_bytes), currentness=value)
        elif consumer == 'coverage': assess_verification_coverage(other, currentness=value)
        else: resolve_builtin_view(other, consumer, currentness=value)


@pytest.mark.parametrize('consumer', ['impact', 'trace', 'diff'])
def test_opaque_currentness_dict_is_not_a_native_provider(tmp_path, consumer):
    root = tmp_path / 'project'
    _, _, value, _ = case(root)
    if consumer == 'impact': result = impact_artifact(root, ref(), currentness=value.data)
    elif consumer == 'trace':
        result = trace_artifact(root, ref(), direction='out', depth=1, currentness=value.data)
    else:
        result = diff_project(root, str(root), against_kind='local',
            before_currentness=value, after_currentness=value.data)
    assert result.exit_code == 3 and result.as_dict()['result'] is None


def test_snapshot_is_owned_deterministic_and_not_a_live_or_release_claim(tmp_path):
    supplied, verification, value, state = case(tmp_path / 'project')
    original = value.observation
    altered = value.data; altered['code_states'][0]['state'] = 'missing'
    assert value.observation == original and value.sha256 == canonical_json_sha256(value.data)
    assert prepare_currentness_read_input(supplied, verification, code_states=[state]).sha256 == value.sha256
    with pytest.raises(TypeError): bool(value)
    with pytest.raises(TypeError): CurrentnessReadInput(value.data)
    with pytest.raises(FrozenInstanceError): value._encoded = b'{}'
    put(tmp_path / 'project', 'src/owned.data', b'changed after observation')
    assert value.observation == original and value.data['project_files_verified'] is False
    with pytest.raises(BuiltinViewProviderError):
        resolve_builtin_view(supplied, 'roadmap', currentness=value)


def test_conflicting_verification_input_cannot_override_bound_currentness(tmp_path):
    supplied, _, value, _ = case(tmp_path / 'project')
    other = verification_for(supplied, None)
    for consumer in ('coverage', 'verification'):
        with pytest.raises(ModelError, match='currentness_verification_mismatch'):
            if consumer == 'coverage': assess_verification_coverage(supplied, other, currentness=value)
            else: resolve_builtin_view(supplied, 'verification', verification=other, currentness=value)


def test_diff_requires_both_independently_bound_sides(tmp_path):
    supplied, _, value, _ = case(tmp_path / 'project')
    result = diff_project(tmp_path / 'project', str(tmp_path / 'project'), against_kind='local',
                          after_currentness=value)
    assert result.exit_code == 3 and result.as_dict()['result'] is None


def test_selected_configuration_cannot_be_silently_ignored(tmp_path):
    root = tmp_path / 'project'
    supplied, _, value, _ = case(root)
    result = impact_artifact(root, ref(), currentness=value, configuration_id=ref('CFG'))
    assert result.exit_code == 3 and result.as_dict()['result'] is None
    with pytest.raises(ModelError, match='currentness_project_configuration_required'):
        validate_model(supplied.documents, currentness=value)
