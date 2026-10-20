"""Independent obligations cannot be narrowed by a successful-looking selection."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_admission import ScopeConfigurationDependencyError
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.verification import (RequiredChecksResolution, RequiredCheckAssessment,
    VerificationEvaluation, VerificationEvaluationError, resolve_required_checks,
    assess_required_check_coverage)
from support.artifacts import artifact_bytes
from support.domain import domain_value, relation
from support.read_only import no_write_attempts
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.records import record_value, ref
from support.srx import binary, expression_document, field, literal
from support.targets import model, SCOPE
from test_verification_contracts import referenced_test_records
from test_verification_evaluation import descriptor


def edge(target, number):
    return {**relation('verified_by', target), 'relation_id': 'REL-' + str(number).zfill(26)}


def project():
    records = referenced_test_records()
    records[0]['relations'].append(edge(ref('TEST'), 1))
    records.extend([
        domain_value('capability', relations=[edge(ref('TEST'), 2)]),
        domain_value('task', relations=[edge(ref('VER', '1'), 3)]),
        record_value('verification', id=ref('VER', '1'), subjects=[ref('TASK')]),
        record_value('test', id=ref('TEST', '1')),
        record_value('document')])
    return records


def checks():
    rows = [
        (ref('CAP'), ref('TEST'), ref('TEST'), 'overall', 'overall'),
        (ref(), ref('TEST'), ref('TEST'), 'overall', 'overall'),
        (ref(), ref('VER'), None, 'review', 'safety'),
        (ref(), ref('VER'), ref('TEST'), 'latency', 'performance'),
        (ref(), ref('VER'), ref('TEST'), 'safe-stop', 'safety'),
        (ref('TASK'), ref('VER', '1'), None, 'overall', 'overall')]
    return [dict(zip(('subject_artifact_id', 'contract_id', 'test_id', 'check_id', 'dimension'), row))
            for row in rows]


def selected(rows=None, **extra):
    return descriptor(required_runs=[{**{k: v for k, v in row.items() if k != 'dimension'},
        'run_ids': ['producer:expected']} for row in (checks() if rows is None else rows)], **extra)


def condition(platform):
    return expression_document(binary('eq', field('/effective_values/platform', 'configuration'),
                                      literal(platform)))


def configured(records, platform='linux'):
    records.append(record_value('configuration', selection={'platform': platform}))
    return resolve_configuration([SourceRelations(artifact_bytes(r)) for r in records], ref('CFG'))


def test_all_slots_and_direct_tests_of_every_subject_are_independent_required_keys():
    supplied = model(project()); before = supplied.source_files
    with no_write_attempts():
        result = resolve_required_checks(supplied, configuration_id=None)
        assessment = assess_required_check_coverage(supplied, selected(), configuration_id=None)
    data, coverage = result.data, assessment.data
    assert data['required_checks'] == checks()
    assert data['required_checks_sha256'] == canonical_json_sha256(checks())
    assert data['input_sha256'] == supplied._sources_sha256
    assert data['scope_descriptor'] == SCOPE
    assert data['scope_sha256'] == canonical_json_sha256(SCOPE)
    assert data['configuration_hash'] is None
    assert data['supplied_required_checks_complete']
    assert data['subjects_without_checks'] == data['unresolved_applicability'] == []
    assert [r['artifact_id'] for r in data['subjects']] == [ref('CAP'), ref(), ref('TASK')]
    assert len(data['contracts']) == 4
    assert coverage['required_set'] == data and coverage['required_set_sha256'] == result.sha256
    assert coverage['required_keys_match'] and coverage['coverage_status'] == 'ready'
    assert coverage['reasons'] == coverage['diagnostics'] == coverage['missing_checks'] == []
    assert coverage['verification_result'] is None
    assert supplied.source_files == before
    for flag in ('project_required_checks_complete', 'run_selection_evaluated',
            'full_verification_evaluated', 'external_run_verified', 'release_readiness_evaluated',
            'test_code_executed', 'write_authorized', 'approval_granted'):
        assert data[flag] is coverage[flag] is False
    assert not coverage['input_bytes_verified'] and not coverage['input_roles_checked']


@pytest.mark.parametrize('index', range(6))
def test_omitting_any_independently_required_key_is_incomplete(index):
    rows = checks(); missing = rows.pop(index)
    report = assess_required_check_coverage(model(project()), selected(rows), configuration_id=None).data
    assert report['required_set']['required_checks'] == checks()
    assert report['missing_checks'] == [missing]
    assert not report['required_keys_match']
    assert report['coverage_status'] == report['verification_result'] == 'incomplete'
    assert report['diagnostics'] == [{'code': 'SRV176', 'severity': 'warning',
                                     'reason': 'required_check_missing'}]


@pytest.mark.parametrize('field_name,value', [
    ('subject_artifact_id', ref('GOAL')), ('contract_id', ref('VER', '2')),
    ('test_id', ref('TEST', '1')), ('check_id', 'undeclared')])
def test_unknown_or_unrequired_descriptor_key_never_expands_project_obligations(field_name, value):
    rows = checks(); rows[0][field_name] = value
    with no_write_attempts(), pytest.raises(VerificationEvaluationError) as caught:
        assess_required_check_coverage(model(project()), selected(rows), configuration_id=None)
    assert caught.value.reason == 'unexpected_evaluation_required_key'
    assert caught.value.code == 'SRV175' and caught.value.exit_code == 3
    assert caught.value.pointer.startswith('/required_runs/')


def test_existing_unlinked_test_cannot_be_selected_as_a_required_contract():
    rows = checks() + [{'subject_artifact_id': ref(), 'contract_id': ref('TEST', '1'),
                        'test_id': ref('TEST', '1'), 'check_id': 'overall'}]
    with pytest.raises(VerificationEvaluationError) as caught:
        assess_required_check_coverage(model(project()), selected(rows), configuration_id=None)
    assert caught.value.reason == 'unexpected_evaluation_required_key'


def test_absent_evaluation_keeps_obligations_and_cannot_guess_an_expected_run():
    data = assess_required_check_coverage(model(project()), None, configuration_id=None).data
    assert data['evaluation_sha256'] is None
    assert data['missing_checks'] == checks() and data['required_set']['required_checks'] == checks()
    assert data['verification_result'] == 'incomplete'
    assert data['reasons'] == ['evaluation_required', 'required_check_missing']


def test_product_identity_and_run_selection_cannot_change_the_required_set():
    supplied = model(project()); first = selected()
    value = first.data; value['required_runs'][0]['run_ids'] = ['other:run', 'other:failed']
    other = VerificationEvaluation(canonical_json_bytes(value))
    changed_product = selected(inputs={'different.bin': b'other'}, subject_id='another-product')
    reports = [assess_required_check_coverage(supplied, item, configuration_id=None).data
               for item in (first, other, changed_product)]
    assert len({r['required_set_sha256'] for r in reports}) == 1
    assert len({r['evaluation_sha256'] for r in reports}) == 3
    assert all(r['verification_result'] is None and not r['run_selection_evaluated'] for r in reports)


@pytest.mark.parametrize('plan_status', ['not_planned', 'planned', 'running', 'not_applicable'])
def test_workflow_status_does_not_silently_remove_contract_slots(plan_status):
    records = project()
    for record in records:
        if 'verification_plan_status' in record:
            record['verification_plan_status'] = plan_status
    assert resolve_required_checks(model(records), configuration_id=None).data['required_checks'] == checks()


def test_selected_configuration_filters_subjects_independently_and_binds_effective_values():
    records = project(); records[0]['applicability'] = condition('windows')
    effective = configured(records)
    expected = [r for r in checks() if r['subject_artifact_id'] != ref()]
    result = resolve_required_checks(model(records), configuration_id=ref('CFG')).data
    assert result['required_checks'] == expected and result['supplied_required_checks_complete']
    assert result['configuration_hash'] == effective.sha256
    assert result['scope_descriptor'] == {**SCOPE, 'configuration_id': ref('CFG')}
    assert [r['status'] for r in result['subjects']] == ['applicable', 'excluded', 'applicable']
    report = assess_required_check_coverage(model(records), selected(expected, configuration=effective),
                                            configuration_id=ref('CFG')).data
    assert report['coverage_status'] == 'ready' and report['verification_result'] is None
    with pytest.raises(VerificationEvaluationError):
        assess_required_check_coverage(model(records), selected(configuration=effective),
                                       configuration_id=ref('CFG'))


@pytest.mark.parametrize('where', [0, 1, 2])
def test_conditional_subject_contract_or_test_without_configuration_stays_required_and_unresolved(where):
    records = project(); records[where]['applicability'] = condition('linux')
    data = assess_required_check_coverage(model(records), selected(), configuration_id=None).data
    assert data['required_set']['required_checks'] == checks()
    assert data['required_set']['unresolved_applicability'] == [records[where]['id']]
    assert not data['required_set']['supplied_required_checks_complete']
    assert data['required_keys_match'] and data['coverage_status'] == 'incomplete'
    assert data['reasons'] == ['verification_applicability_unresolved']


@pytest.mark.parametrize('where', [1, 2])
def test_excluded_required_dependency_is_a_native_scope_error_not_a_removed_slot(where):
    records = project(); records[where]['applicability'] = condition('windows'); configured(records)
    with pytest.raises(ScopeConfigurationDependencyError) as caught:
        resolve_required_checks(model(records), configuration_id=ref('CFG'))
    assert caught.value.code == 'SRV141' and caught.value.exit_code == 3
    assert caught.value.target_id == records[where]['id'] and caught.value.configuration_id == ref('CFG')


@pytest.mark.parametrize('configuration_id', [None, ref('CFG')])
def test_descriptor_configuration_is_compared_to_the_independent_selection(configuration_id):
    records = project(); effective = configured(records)
    supplied = model(records)
    evaluation = selected(configuration=effective if configuration_id is None else None)
    data = assess_required_check_coverage(supplied, evaluation, configuration_id=configuration_id).data
    assert data['required_keys_match'] and data['verification_result'] == 'incomplete'
    assert data['reasons'] == ['evaluation_configuration_mismatch']


def test_same_configuration_id_with_changed_effective_values_does_not_reuse_the_descriptor_binding():
    records = project(); effective = configured(records)
    evaluation = selected(configuration=effective)
    records[-1]['selection']['platform'] = 'windows'
    data = assess_required_check_coverage(model(records), evaluation, configuration_id=ref('CFG')).data
    assert data['required_set']['configuration_hash'] != effective.sha256
    assert data['reasons'] == ['evaluation_configuration_mismatch']


def test_applicable_subject_without_contract_cannot_create_a_vacuous_complete_set():
    records = project(); records.append(domain_value('requirement', id=ref('REQ', '2')))
    data = assess_required_check_coverage(model(records), selected(), configuration_id=None).data
    assert data['required_set']['subjects_without_checks'] == [ref('REQ', '2')]
    assert data['required_set']['required_checks'] == checks()
    assert data['reasons'] == ['verification_contract_missing']
    assert data['coverage_status'] == 'incomplete'


@pytest.mark.parametrize('which', ['unknown-target', 'missing-slot', 'unknown-test', 'undeclared-subject'])
def test_native_contract_and_reference_failures_never_produce_partial_success(which):
    records = project()
    if which == 'unknown-target': records[0]['relations'][0]['target'] = ref('VER', '2')
    if which == 'missing-slot': del records[1]['evidence_slots']
    if which == 'unknown-test': records[1]['evidence_slots'][0]['test_id'] = ref('TEST', '2')
    if which == 'undeclared-subject': records[1]['subjects'] = [ref('CAP')]
    with no_write_attempts(), pytest.raises(ModelError):
        assess_required_check_coverage(model(records), selected(), configuration_id=None)


@pytest.mark.parametrize('change', ['oracle', 'slot', 'relation'])
def test_actual_model_edits_change_the_independent_binding(change):
    records = project(); before = resolve_required_checks(model(records), configuration_id=None)
    if change == 'oracle': records[1]['oracle'] = 'A changed criterion'
    if change == 'slot': records[1]['evidence_slots'][0]['check_id'] = 'new-latency'
    if change == 'relation': records[0]['relations'].pop()
    after = resolve_required_checks(model(records), configuration_id=None)
    assert before.sha256 != after.sha256
    assert before.data['input_sha256'] != after.data['input_sha256']
    assert (before.data['required_checks'] == after.data['required_checks']) is (change == 'oracle')


def test_supply_order_and_descriptor_order_do_not_change_normalized_results():
    records = project(); first = selected()
    value = first.data; value['required_runs'].reverse()
    other = VerificationEvaluation(canonical_json_bytes(value))
    a = assess_required_check_coverage(model(records), first, configuration_id=None)
    b = assess_required_check_coverage(model(records[::-1]), other, configuration_id=None)
    assert a.data == b.data and a.sha256 == b.sha256


def test_results_are_owned_values_and_cannot_be_truthy_success_shortcuts():
    supplied = model(project())
    for result in (resolve_required_checks(supplied, configuration_id=None),
                   assess_required_check_coverage(supplied, selected(), configuration_id=None)):
        original = deepcopy(result.data); changed = result.data; changed.clear()
        assert result.data == original and result.sha256 == sha256(canonical_json_bytes(original)).hexdigest()
        with pytest.raises(TypeError): bool(result)
        with pytest.raises(FrozenInstanceError): result._encoded = b'{}'
    for cls in (RequiredChecksResolution, RequiredCheckAssessment):
        with pytest.raises(TypeError): cls()


def test_raw_descriptor_bytes_override_tampered_cached_selection():
    evaluation = selected(checks()[:-1])
    object.__setattr__(evaluation, '_encoded', selected().canonical_bytes)
    data = assess_required_check_coverage(model(project()), evaluation, configuration_id=None).data
    assert data['missing_checks'] == [checks()[-1]] and data['verification_result'] == 'incomplete'


def test_changed_model_source_binding_is_not_accepted_as_old_inventory():
    supplied = model(project()); object.__setattr__(supplied, '_sources_sha256', 'f' * 64)
    with pytest.raises(ModelError) as caught:
        resolve_required_checks(supplied, configuration_id=None)
    assert caught.value.reason == 'target_sources_changed'


def test_no_files_or_processes_are_opened_by_required_set_resolution(monkeypatch):
    supplied, evaluation = model(project()), selected()
    def no_read(*args, **kwargs):
        raise AssertionError('Required checks must use only supplied bytes')
    with no_write_attempts(), monkeypatch.context() as patch:
        patch.setattr('builtins.open', no_read); patch.setattr('io.open', no_read)
        data = assess_required_check_coverage(supplied, evaluation, configuration_id=None).data
    assert data['coverage_status'] == 'ready'


@pytest.mark.parametrize('value', [{}, None, 'current-project'])
def test_required_set_requires_a_native_owned_model(value):
    with pytest.raises(ModelError) as caught:
        resolve_required_checks(value, configuration_id=None)
    assert caught.value.reason == 'verification_target_model_required'


@pytest.mark.parametrize('value', [{}, b'{}', True])
def test_coverage_rejects_untyped_descriptors(value):
    with pytest.raises(VerificationEvaluationError) as caught:
        assess_required_check_coverage(model(project()), value, configuration_id=None)
    assert caught.value.reason == 'typed_verification_evaluation_required'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_required_keys_and_coverage_are_identical_in_fresh_core_and_pyz(mode, tmp_path):
    supplied, evaluation = model(project()), selected()
    expected = assess_required_check_coverage(supplied, evaluation, configuration_id=None).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.verification import VerificationEvaluation, assess_required_check_coverage
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += 'evaluation=VerificationEvaluation(' + repr(evaluation.source_bytes) + ')\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
print(json.dumps(assess_required_check_coverage(owned,evaluation,configuration_id=None).data))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
