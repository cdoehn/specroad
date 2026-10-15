"""Selection refusals, owned source bindings and unchanged variant identities."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from specroad.configurations import validate_configured_model
from specroad.configurations.evaluation import ConfigurationEvaluationError
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument, validate_model
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.model_validation import doc, profile, title_gate
from support.portable import build_distribution
from support.processes import run_python
from support.production_validation import inputs
from support.read_only import no_write_attempts
from support.records import record_value
from support.relations import aid, edge, rid
from support.srx import binary, expression_document, field, literal


def configuration(number=1, **changes):
    return record_value('configuration', id=aid('configuration', number), name='Variant ' + str(number), **changes)


def requirement(number=1, **changes):
    changes.setdefault('language', 'en')
    return domain_value('requirement', id=aid(number=number), **changes)


def condition(value):
    return expression_document(binary('eq', field('/effective_values/platform', 'configuration'), literal(value)))


def documents(values):
    return tuple(doc(value) for value in values)


def run(values, selected=aid('configuration'), **kwargs):
    return validate_configured_model(documents(values), configuration_id=selected, profile=profile(), **kwargs)


def stage(report):
    return next(s for s in report.data['stages'] if s['stage'] == 'configuration')


@pytest.mark.parametrize('inventory', ['empty', 'one', 'several', 'conditional_only'])
def test_no_inventory_shape_makes_an_implicit_selection_succeed(inventory):
    values = {'empty': [], 'one': [configuration()], 'several': [configuration(), configuration(2)],
              'conditional_only': [requirement(applicability=condition('linux'))]}[inventory]
    with pytest.raises(ConfigurationEvaluationError) as caught:
        run(values, selected=None)
    assert caught.value.reason == 'configuration_id_required'


@pytest.mark.parametrize('selected', [aid('goal'), 'linux', 'Variant 1', '  ', 'null'])
def test_names_types_and_display_values_cannot_stand_in_for_a_configuration_id(selected):
    with pytest.raises(ConfigurationEvaluationError) as caught:
        run([configuration()], selected=selected)
    assert caught.value.reason == 'configuration_missing'


def test_missing_selection_fails_before_any_other_registered_gate_can_supply_a_pass():
    calls = []
    gate = title_gate(dependencies=lambda context: calls.append(context))
    with pytest.raises(ConfigurationEvaluationError):
        run([configuration(), domain_value('goal')], selected=None, gates=(gate,))
    assert not calls


def test_deterministic_invalid_configuration_choice_uses_identity_not_caller_order():
    one = configuration(); two = configuration(2)
    one['name'] = two['name'] = ''
    errors = []
    for values in ([one, two], [two, one]):
        with pytest.raises(ConfigurationEvaluationError) as caught:
            run(values)
        errors.append(caught.value.diagnostic())
    assert errors[0] == errors[1] and errors[0]['path'] == aid('configuration') + '.json'


def test_duplicate_source_labels_cannot_be_resolved_as_two_distinct_documents():
    supplied = (doc(configuration(), 'same.json'), doc(configuration(2), 'same.json'))
    with pytest.raises(ModelError) as caught:
        validate_configured_model(supplied, configuration_id=aid('configuration'))
    assert caught.value.reason == 'duplicate_validation_source'


def test_duplicate_identity_is_not_a_second_variant_copy():
    value = requirement()
    supplied = (doc(configuration()), doc(value, 'one.json'), doc(value, 'two.json'))
    with pytest.raises(ConfigurationEvaluationError) as caught:
        validate_configured_model(supplied, configuration_id=aid('configuration'))
    assert caught.value.reason == 'duplicate_configuration_inventory_id'


@pytest.mark.parametrize('field,value', [('content', 'not bytes'), ('path', ''), ('path', None)])
def test_reconstructed_documents_reject_forged_cached_fields(field, value):
    supplied = doc(configuration()); object.__setattr__(supplied, field, value)
    with pytest.raises(ModelError):
        validate_configured_model((supplied,), configuration_id=aid('configuration'))


def test_owned_documents_survive_a_provider_replacing_its_original_record_during_delegation():
    selected = doc(configuration()); supplied = [selected, doc(domain_value('goal'))]
    before = selected.content
    def delegate(owned, **kwargs):
        object.__setattr__(selected, 'content', artifact_bytes(configuration(selection={'platform': 'invalid'})))
        supplied.clear()
        return validate_model(owned, **kwargs)
    with patch('specroad.validation.validate_model', side_effect=delegate):
        report = validate_configured_model(supplied, configuration_id=aid('configuration'), profile=profile())
    assert report.passed and stage(report)['status'] == 'passed'
    assert selected.content != before and len(report.data['source_bindings']) == 2


@pytest.mark.parametrize('change', ['revision', 'choice', 'parent_revision'])
def test_gate_rechecks_the_selected_manifest_at_the_model_pipeline_boundary(change):
    parent = configuration(); child = configuration(2, parent=parent['id'], dimensions=[], selection={})
    supplied = documents([parent, child, domain_value('goal')])
    def delegate(loaded, **kwargs):
        changed = []
        for source in loaded:
            value = json.loads(source.content)
            target = parent['id'] if change == 'parent_revision' else child['id']
            if value['id'] == target:
                if change == 'choice': value['selection'] = {'platform': 'windows'}
                else: value['revision'] += 1
                source = ModelDocument(source.path, artifact_bytes(value))
            changed.append(source)
        return validate_model(tuple(changed), **kwargs)
    with patch('specroad.validation.validate_model', side_effect=delegate):
        report = validate_configured_model(supplied, configuration_id=child['id'], profile=profile())
    assert stage(report)['status'] == 'failed' and not report.passed
    assert stage(report)['diagnostics'][0]['reason'] == 'configuration_gate_binding_changed'
    assert stage(report)['diagnostics'][0]['code'] == 'SRV130'


def test_original_json_formatting_does_not_create_a_false_configuration_binding_mismatch():
    supplied = documents([configuration(), domain_value('goal')])
    def delegate(loaded, **kwargs):
        formatted = tuple(ModelDocument(d.path, json.dumps(json.loads(d.content), indent=3).encode()) for d in loaded)
        return validate_model(formatted, **kwargs)
    with patch('specroad.validation.validate_model', side_effect=delegate):
        report = validate_configured_model(supplied, configuration_id=aid('configuration'), profile=profile())
    assert report.passed


def test_same_selected_values_at_distinct_revisions_produce_distinct_bindings():
    one = [configuration(), domain_value('goal')]; two = copy.deepcopy(one); two[0]['revision'] += 1
    before = copy.deepcopy((one, two)); first, second = run(one), run(two)
    assert first.passed and second.passed and first.data['input_sha256'] != second.data['input_sha256']
    assert (one, two) == before


def test_parent_and_child_selection_stay_distinct_even_with_equal_effective_values():
    values = [configuration(), configuration(2, parent=aid('configuration'), dimensions=[], selection={})]
    assert run(values).data['input_sha256'] != run(values, selected=aid('configuration', 2)).data['input_sha256']


def test_two_concurrent_variants_keep_separate_results_over_the_same_original_model():
    values = [configuration(), configuration(2, selection={'platform': 'windows'}),
              requirement(relations=[edge('depends_on', aid(number=2))]),
              requirement(2, applicability=condition('windows'))]
    supplied = documents(values); before = tuple((d.path, d.content) for d in supplied); p = profile()
    def observe(n):
        report = validate_configured_model(supplied, configuration_id=aid('configuration', n), profile=p)
        return n, stage(report)['status'], report.data['input_sha256']
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(observe, [1, 2] * 8))
    assert {state for n, state, binding in outputs if n == 1} == {'failed'}
    assert {state for n, state, binding in outputs if n == 2} == {'passed'}
    assert len({binding for n, state, binding in outputs}) == 2
    assert before == tuple((d.path, d.content) for d in supplied)


def test_many_origins_preserve_the_complete_conflict_set_in_gate_findings():
    values = [configuration(), requirement(10, applicability=condition('windows'))]
    values += [requirement(n, relations=[edge('depends_on', aid(number=10), number=n)]) for n in range(1, 10)]
    findings = stage(run(values))['diagnostics']
    assert len(findings) == 9
    assert [f['dependency']['source_id'] for f in findings] == [aid(number=n) for n in range(1, 10)]
    assert all(f['dependency']['target_id'] == aid(number=10) for f in findings)


def test_complete_transitive_path_is_not_replaced_by_only_the_excluded_endpoint():
    values = [configuration(), requirement(relations=[edge('depends_on', aid(number=2))]),
              requirement(2, relations=[edge('depends_on', aid(number=3), number=2)]),
              requirement(3, applicability=condition('windows'))]
    findings = stage(run(values))['diagnostics']
    assert [f['dependency']['distance'] for f in findings] == [2, 1]
    assert [a['id'] for a in findings[0]['dependency']['path']['artifacts']] == [aid(), aid(number=2), aid(number=3)]
    assert [r['relation_id'] for r in findings[0]['dependency']['path']['relations']] == [rid(), rid(2)]


def test_excluded_requirement_is_still_subject_to_existing_structural_validation():
    value = requirement(applicability=condition('windows')); del value['statement']
    report = run([configuration(), value])
    assert report.data['model_valid'] is False and not report.passed
    assert any(s['stage'] == 'schema_types_identity_fields' and s['status'] == 'failed' for s in report.data['stages'])


def test_production_profile_and_language_failures_survive_configuration_gate_success():
    data = inputs([configuration(), requirement(language='de')])
    report = validate_configured_model(data.documents, configuration_id=aid('configuration'),
                                      profile=data.profile, resources=data.resources)
    assert stage(report)['status'] == 'passed' and not report.passed
    assert any(d.get('code') == 'SRV179' for d in report.diagnostics)


def test_pure_gate_never_requests_random_identity_generation_or_filesystem_writes():
    supplied = documents([configuration(), domain_value('goal')]); p = profile()
    with no_write_attempts(), patch('os.urandom', side_effect=AssertionError('Unexpected identity generation')):
        report = validate_configured_model(supplied, configuration_id=aid('configuration'), profile=p)
    assert report.passed


def test_portable_python_api_uses_the_same_explicit_configuration_gate(tmp_path):
    _, package = build_distribution(tmp_path / 'distribution')
    values = [configuration(), domain_value('goal')]
    (tmp_path / 'documents.json').write_bytes(artifact_bytes(values))
    body = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from specroad.configurations import validate_configured_model
from specroad.validation import ModelDocument
values = json.loads(Path('documents.json').read_bytes())
documents = tuple(ModelDocument(v['id'] + '.json', json.dumps(v).encode()) for v in values)
result = validate_configured_model(documents, configuration_id=values[0]['id'])
print(json.dumps(result.data))
'''
    result = run_python(['-I', '-S', '-B', '-c', body, str(package)], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert next(s for s in report['stages'] if s['stage'] == 'configuration')['status'] == 'passed'
    assert report['approval_granted'] is False and report['write_authorized'] is False
