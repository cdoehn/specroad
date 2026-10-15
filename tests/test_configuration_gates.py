"""Explicit gates over original identities, real model validation and no writes."""
import copy
from unittest.mock import patch

import pytest

from specroad.configurations import validate_configured_model
from specroad.configurations.evaluation import ConfigurationEvaluationError
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument, ModelGate, assess_validation, validate_model
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.model_validation import doc, profile, title_gate, no_dependencies
from support.production_validation import inputs
from support.read_only import no_write_attempts
from support.records import record_value
from support.relations import aid, edge, rid
from support.srx import binary, expression_document, field, literal


def configuration(number=1, **changes):
    return record_value('configuration', id=aid('configuration', number), name='Variant ' + str(number), **changes)


def requirement(number=1, **changes):
    return domain_value('requirement', id=aid(number=number), language='en', **changes)


def condition(platform):
    return expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal(platform)))


def documents(values):
    return tuple(doc(value) for value in values)


def run(values, selected=aid('configuration'), **kwargs):
    return validate_configured_model(documents(values), configuration_id=selected, profile=profile(), **kwargs)


def stage(report, name='configuration'):
    return next(s for s in report.data['stages'] if s['stage'] == name)


def test_selected_gate_runs_the_existing_validator_without_approval_or_writes():
    report = run([configuration(), domain_value('goal')])
    assert report.passed and report.complete and stage(report)['status'] == 'passed'
    assert set(report.data['identified_ids']) == {aid('configuration'), domain_value('goal')['id']}
    assert all(report.data[key] is False for key in ('approval_granted', 'write_authorized',
                                                    'project_files_verified', 'atomic_snapshot'))


@pytest.mark.parametrize('selected', [None, '', 1, True, {}])
def test_missing_or_nonstring_selection_cannot_pick_the_only_configuration(selected):
    with pytest.raises(ConfigurationEvaluationError) as caught:
        run([configuration(), domain_value('goal')], selected=selected)
    assert caught.value.reason == 'configuration_id_required' and caught.value.code == 'SRV130'


def test_omitting_configuration_argument_is_a_structured_refusal():
    with pytest.raises(ConfigurationEvaluationError) as caught:
        validate_configured_model(documents([configuration()]), profile=profile())
    assert caught.value.reason == 'configuration_id_required'


def test_absent_selected_id_never_falls_back_to_an_available_variant():
    with pytest.raises(ConfigurationEvaluationError) as caught:
        run([configuration(), configuration(2)], selected=aid('configuration', 3))
    assert caught.value.reason == 'configuration_missing'


def test_empty_model_cannot_turn_a_configuration_gate_into_not_applicable():
    with pytest.raises(ConfigurationEvaluationError) as caught:
        run([])
    assert caught.value.reason == 'configuration_missing'


def test_one_requirement_is_reused_by_two_variants_without_a_copy_or_revision_change():
    values = [configuration(), configuration(2, selection={'platform': 'windows'}), requirement()]
    data = inputs(values); before = tuple((d.path, d.content) for d in data.documents)
    reports = [validate_configured_model(data.documents, configuration_id=aid('configuration', n),
                profile=data.profile, resources=data.resources) for n in (1, 2)]
    assert all(report.passed for report in reports)
    assert reports[0].data['input_sha256'] != reports[1].data['input_sha256']
    assert reports[0].data['source_bindings'] == reports[1].data['source_bindings']
    assert reports[0].data['identified_ids'].count(aid()) == 1
    assert before == tuple((d.path, d.content) for d in data.documents)
    assert values[-1]['id'] == aid() and values[-1]['revision'] == 1


@pytest.mark.parametrize('kind', ['verification', 'test', 'code_ref', 'content_block'])
def test_other_reusable_artifact_kinds_retain_their_single_original_identity(kind):
    value = record_value(kind)
    if kind == 'verification': value['subjects'] = [aid()]
    values = [configuration(), configuration(2, selection={'platform': 'windows'}), requirement(), value]
    before = copy.deepcopy(values)
    one = run(values); two = run(values, selected=aid('configuration', 2))
    assert stage(one)['status'] == stage(two)['status'] == 'passed'
    assert one.data['identified_ids'] == two.data['identified_ids']
    assert one.data['identified_ids'].count(value['id']) == 1
    assert one.data['source_bindings'] == two.data['source_bindings'] and values == before


def test_declared_dimension_default_is_allowed_only_after_explicit_selection():
    report = run([configuration(selection={}), domain_value('goal')])
    assert report.passed and stage(report)['status'] == 'passed'


def test_excluded_required_target_fails_the_real_gate_with_complete_path_evidence():
    values = [configuration(), requirement(relations=[edge('depends_on', aid(number=2))]),
              requirement(2, applicability=condition('windows'))]
    report = run(values); outcome = stage(report)
    assert outcome['status'] == 'failed' and not report.passed
    finding = outcome['diagnostics'][0]
    assert finding['code'] == 'SRV131' and finding['artifact_id'] == aid('configuration')
    assert finding['related_ids'] == [aid(), aid(number=2)]
    assert finding['dependency']['distance'] == 1
    assert [a['id'] for a in finding['dependency']['path']['artifacts']] == [aid(), aid(number=2)]
    assert [r['relation_id'] for r in finding['dependency']['path']['relations']] == [rid()]
    observed = assess_validation(report, documents=documents(values))
    assert any(d.code == 'SRV131' and d.related_ids == (aid(), aid(number=2)) for d in observed.diagnostics)


def test_explicit_child_override_changes_the_gate_result_without_changing_references():
    values = [configuration(), configuration(2, parent=aid('configuration'), dimensions=[],
              selection={'platform': 'windows'}), requirement(relations=[edge('depends_on', aid(number=2))]),
              requirement(2, applicability=condition('windows'))]
    before = copy.deepcopy(values)
    assert stage(run(values))['status'] == 'failed'
    assert stage(run(values, selected=aid('configuration', 2)))['status'] == 'passed'
    assert values == before


def test_excluded_origin_does_not_create_a_variant_dependency():
    values = [configuration(), requirement(applicability=condition('windows'),
        relations=[edge('depends_on', aid(number=2))]), requirement(2, applicability=condition('windows'))]
    assert stage(run(values))['status'] == 'passed'


def test_invalid_applicability_is_a_failed_gate_with_srv130_and_source_location():
    values = [configuration(), requirement(applicability=expression_document(literal('invalid')))]
    report = run(values); finding = stage(report)['diagnostics'][0]
    assert finding['code'] == 'SRV130' and finding['reason'] == 'invalid_applicability'
    assert finding['path'] == aid() + '.json' and finding['pointer'].startswith('/applicability')
    assert stage(report)['status'] == 'failed'


def test_ordinary_validator_keeps_its_unavailable_configuration_service_boundary():
    values = [configuration(), domain_value('goal')]
    assert stage(validate_model(documents(values), profile=profile()))['status'] == 'unavailable'
    assert stage(run(values))['status'] == 'passed'


def test_configuration_success_does_not_invent_a_missing_language_service():
    report = run([configuration(), requirement()])
    assert stage(report)['status'] == 'passed'
    assert stage(report, 'language_policy')['status'] == 'unavailable'
    assert not report.passed and not report.complete


def test_additional_registered_gates_still_run_and_can_fail():
    report = run([configuration(), domain_value('goal', title='forbidden')], gates=(title_gate(),))
    assert stage(report)['status'] == 'passed'
    assert stage(report, 'extension:titles')['status'] == 'failed' and not report.passed


def test_a_caller_cannot_replace_the_selected_configuration_check():
    fake = ModelGate('configuration', 'fake', no_dependencies, lambda context: context.result())
    with pytest.raises(ModelError) as caught:
        run([configuration()], gates=(fake,))
    assert caught.value.reason == 'duplicate_validation_gate'


def test_each_invocation_rechecks_actual_applicability_instead_of_reusing_a_pass():
    values = [configuration(), requirement(relations=[edge('depends_on', aid(number=2))]), requirement(2)]
    first = run(values)
    values[-1]['applicability'] = condition('windows')
    second = run(values)
    assert stage(first)['status'] == 'passed' and stage(second)['status'] == 'failed'
    assert first.data['input_sha256'] != second.data['input_sha256']


def test_selected_validation_subject_cannot_hide_a_configuration_conflict_elsewhere():
    unrelated = domain_value('goal')
    values = [configuration(), unrelated, requirement(relations=[edge('depends_on', aid(number=2))]),
              requirement(2, applicability=condition('windows'))]
    report = run(values, selected_ids=(unrelated['id'],))
    assert stage(report)['status'] == 'failed'
    assert report.data['checked_ids'] == sorted(v['id'] for v in values)


def test_loaded_source_bytes_and_revision_inventory_are_read_only():
    values = [configuration(), requirement()]; supplied = documents(values)
    before = tuple((d.path, d.content) for d in supplied)
    with no_write_attempts():
        with patch('pathlib.Path.read_bytes', side_effect=AssertionError('Unexpected source reopening')):
            report = validate_configured_model(supplied, configuration_id=aid('configuration'), profile=profile())
    assert stage(report)['status'] == 'passed' and before == tuple((d.path, d.content) for d in supplied)


def test_input_enumeration_order_does_not_change_bound_validation():
    values = [configuration(), configuration(2), requirement()]
    assert run(values).data == run(values[::-1]).data


def test_report_mutation_cannot_change_a_subsequent_observation():
    report = run([configuration(), domain_value('goal')]); changed = report.data
    changed['stages'].clear(); changed['identified_ids'].clear()
    assert report.passed and report.data['stages'] and report.data['identified_ids']
    with pytest.raises(TypeError): bool(report)


def test_domain_schema_failures_remain_blocking_before_semantic_gate_success():
    value = requirement(); del value['statement']
    report = run([configuration(), value])
    assert not report.passed and not report.complete
    assert stage(report, 'schema_types_identity_fields')['status'] == 'failed'


def test_invalid_configuration_is_not_a_successful_empty_gate():
    with pytest.raises(ConfigurationEvaluationError):
        run([configuration(selection={'platform': 'unsupported'})])


def test_inputs_must_be_real_loaded_documents():
    with pytest.raises(ModelError) as caught:
        validate_configured_model([configuration()], configuration_id=aid('configuration'))
    assert caught.value.reason == 'validation_documents_required'
