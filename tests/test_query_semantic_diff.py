"""Declared semantic classes and bound observations, without interpreting prose."""
from copy import deepcopy
from unittest.mock import patch
import json

import pytest

from specroad.graph.comparison import ComparisonInputs
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_sha256
from specroad.model.configuration import ProjectConfiguration
from specroad.model.errors import ModelError
from specroad.query import compare_semantic
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.model import configuration_value
from support.processes import run_core
from support.read_only import no_write_attempts
from support.records import record_value, srx
from support.relations import aid, edge


def inputs(*values, project_id='sample'):
    return ComparisonInputs(project_id, [SourceRelations(artifact_bytes(value)) for value in values])


def requirement(**fields):
    return domain_value('requirement', **{'id': aid(), **fields})


def compare(old, new, **options):
    return compare_semantic(inputs(old), inputs(new), **options).data


def fields(result):
    return {field['pointer']: field for item in result['changes'] for field in item['fields']}


def test_structured_threshold_and_unstructured_statement_have_distinct_categories():
    old = requirement(thresholds=[{'property': 'latency', 'maximum': 10}], statement='Respond within 10 ms.')
    new = deepcopy(old); new['thresholds'][0]['maximum'] = 5; new['statement'] = 'Respond within 5 ms.'
    result = compare(old, new); rows = fields(result)
    assert set(rows) == {'/statement', '/thresholds'}
    assert rows['/statement']['category'] == 'text_changed'
    assert rows['/thresholds']['category'] == 'threshold_changed'
    assert rows['/thresholds']['before'] == [{'property': 'latency', 'maximum': 10}]
    assert rows['/thresholds']['after'] == [{'property': 'latency', 'maximum': 5}]
    assert result['categories'] == ['modified', 'text_changed', 'threshold_changed']
    assert result['changes'][0]['before_sha256'] == canonical_json_sha256(old)
    assert result['changes'][0]['after_sha256'] == canonical_json_sha256(new)


@pytest.mark.parametrize('bound,old,new,expected', [
    ('maximum', 'PT2S', 'PT1S', 'timing_tightened'),
    ('maximum', 'PT1S', 'PT2S', 'timing_relaxed'),
    ('minimum', 'PT1S', 'PT2S', 'timing_tightened'),
    ('minimum', 'PT2S', 'PT1S', 'timing_relaxed')])
def test_only_explicit_bound_direction_justifies_timing_order(bound, old, new, expected):
    result = compare(requirement(timing=old), requirement(timing=new), timing_bounds={aid(): bound})
    assert fields(result)['/timing']['category'] == expected
    assert result['timing'][0]['category'] == expected
    assert result['timing'][0]['interpretation'] == 'explicit_caller_bound'
    assert result['timing_bounds'] == {aid(): bound}
    assert result['categories'] == ['modified', expected]


def test_equivalent_units_are_explicit_without_erasing_the_actual_field_delta():
    result = compare(requirement(timing={'value': 1, 'unit': 's'}),
                     requirement(timing={'value': 1000, 'unit': 'ms'}), timing_bounds={aid(): 'maximum'})
    assert result['changed'] and result['timing'][0]['comparable']
    assert result['timing'][0]['order'] == 0 and result['timing'][0]['category'] == 'timing_equivalent'
    assert set(fields(result)) == {'/timing/unit', '/timing/value'}
    assert {f['category'] for f in fields(result).values()} == {'timing_equivalent'}


def test_calendar_duration_does_not_invent_a_fixed_seconds_order():
    result = compare(requirement(timing='P1M'), requirement(timing='P30D'), timing_bounds={aid(): 'maximum'})
    assert result['timing'][0]['category'] == 'timing_changed'
    assert result['timing'][0]['order'] is None and not result['timing'][0]['comparable']


def test_explicit_policy_is_bound_even_when_the_duration_is_unchanged():
    source = requirement(timing='PT1S')
    upper = compare(source, source, timing_bounds={aid(): 'maximum'})
    lower = compare(source, source, timing_bounds={aid(): 'minimum'})
    assert not upper['changed'] and not lower['changed']
    assert upper['timing'] == lower['timing'] == []
    assert upper['input_sha256'] != lower['input_sha256']


def test_missing_bound_does_not_interpret_free_text_or_invent_tightening():
    result = compare(requirement(timing='within ten seconds'), requirement(timing='within five seconds'))
    assert result['timing_bounds'] == {} and result['timing'] == []
    assert fields(result)['/timing']['category'] == 'text_changed'
    assert 'timing_tightened' not in result['categories']


@pytest.mark.parametrize('kind,field,old,new', [
    ('requirement', 'implementation_status', 'not_started', 'in_progress'),
    ('assumption', 'validation_status', 'pending', 'confirmed'),
    ('issue', 'issue_status', 'open', 'resolved')])
def test_stored_status_changes_are_separate_from_text(kind, field, old, new):
    factory = record_value if kind == 'issue' else domain_value
    before = factory(kind, **{field: old}); after = deepcopy(before); after[field] = new
    result = compare(before, after)
    assert fields(result)['/' + field]['category'] == 'status_changed'
    assert result['categories'] == ['modified', 'status_changed']


@pytest.mark.parametrize('field,old,new,expected', [
    ('scope', {'mode': 'normal'}, {'mode': 'emergency'}, 'scope_changed'),
    ('exceptions', ['Case A'], ['Case B'], 'exception_changed'),
    ('verification_plan_status', 'not_planned', 'planned', 'verification_changed'),
    ('priority', 'mandatory', 'high', 'field_changed')])
def test_existing_structural_classes_survive_semantic_aggregation(field, old, new, expected):
    result = compare(requirement(**{field: old}), requirement(**{field: new}))
    assert {f['category'] for f in fields(result).values()} == {expected}
    assert result['categories'] == sorted(['modified', expected])


def test_code_reference_changes_retain_the_whole_artifact_class():
    result = compare(record_value('code_ref', path='src/old.py'), record_value('code_ref', path='src/new.py'))
    assert result['categories'] == ['code_reference_changed', 'field_changed', 'modified']
    assert fields(result)['/path']['before'] == 'src/old.py'
    assert fields(result)['/path']['after'] == 'src/new.py'


def test_applicability_and_product_configuration_are_distinct_classes():
    old_req = requirement(applicability=srx()); new_req = deepcopy(old_req)
    new_req['applicability']['expression']['value'] = False
    old_cfg = record_value('configuration'); new_cfg = deepcopy(old_cfg); new_cfg['selection']['platform'] = 'windows'
    result = compare_semantic(inputs(old_req, old_cfg), inputs(new_cfg, new_req)).data
    rows = fields(result)
    assert rows['/applicability/expression/value']['category'] == 'applicability_changed'
    assert rows['/selection/platform']['category'] == 'configuration_changed'
    assert result['categories'] == ['applicability_changed', 'configuration_changed', 'modified']
    assert result['configuration_scope'] == {'state': 'not_evaluated'}
    assert result['inventory_delta'] == {'scope': 'supplied_artifact_sets', 'added_ids': [], 'removed_ids': []}


def test_project_semantic_configuration_changes_are_bound_even_without_artifact_changes():
    old = ProjectConfiguration(configuration_value(validation_policy={'fail_on': 'error'}))
    new = ProjectConfiguration(configuration_value(validation_policy={'fail_on': 'warning'}))
    result = compare_semantic(inputs(), inputs(), before_configuration=old, after_configuration=new).data
    assert result['changed'] and not result['changes']
    assert result['categories'] == ['configuration_changed']
    config = result['project_configuration']
    assert config['state'] == 'compared' and config['changed']
    assert config['fields'] == [{'pointer': '/validation_policy/fail_on', 'operation': 'replace',
        'before_present': True, 'after_present': True, 'before': 'error', 'after': 'warning',
        'category': 'configuration_changed'}]
    assert result['configuration_inputs'] == {'before_sha256': canonical_json_sha256(old.data),
                                              'after_sha256': canonical_json_sha256(new.data)}


def test_presentation_configuration_is_bound_but_does_not_claim_semantic_change():
    old = ProjectConfiguration(configuration_value(default_locale='de-DE'))
    new = ProjectConfiguration(configuration_value(default_locale='en-US'))
    result = compare_semantic(inputs(), inputs(), before_configuration=old, after_configuration=new).data
    assert not result['changed'] and result['categories'] == []
    assert result['project_configuration']['before_sha256'] == result['project_configuration']['after_sha256']
    assert result['configuration_inputs']['before_sha256'] != result['configuration_inputs']['after_sha256']


@pytest.mark.parametrize('field,value,expected', [
    ('result', 'passed', 'evidence_result_changed'),
    ('subjects', [{'artifact_id': aid(), 'revision': 2, 'artifact_sha256': 'd' * 64,
                   'verification_context_sha256': 'e' * 64}], 'evidence_binding_changed'),
    ('configuration_hash', 'f' * 64, 'evidence_binding_changed'),
    ('attachments', [{'path': 'attachments/report.json', 'media_type': 'application/json',
                      'size': 2, 'sha256': 'c' * 64}], 'evidence_changed')])
def test_evidence_record_deltas_never_claim_subject_verification_or_currency(field, value, expected):
    old = record_value('evidence'); new = deepcopy(old); new[field] = value
    result = compare(old, new)
    assert {f['category'] for f in fields(result).values()} == {expected}
    assert result['categories'] == sorted([expected, 'modified'])
    assert result['evidence_currency'] == {'state': 'not_evaluated'}
    assert not result['approval_granted'] and not result['full_semantic_validation']


def test_relation_identity_and_document_position_changes_remain_visible():
    old = record_value('document', relations=[edge('contains', aid('section'), position=0)])
    new = deepcopy(old); new['relations'][0]['position'] = 1
    result = compare(old, new); row = fields(result)['/relations']
    assert row['category'] == 'relation_changed'
    assert row['before'][0]['relation_id'] == row['after'][0]['relation_id']
    assert row['before'][0]['position'] == 0 and row['after'][0]['position'] == 1
    assert result['categories'] == ['document_structure_changed', 'modified', 'relation_changed']


def test_addition_removal_and_retirement_preserve_identity_and_do_not_guess_scope_exclusion():
    old = requirement(); retired = deepcopy(old); retired['maturity'] = 'retired'
    removed = requirement(id=aid(number=2)); added = requirement(id=aid(number=3))
    result = compare_semantic(inputs(old, removed), inputs(added, retired)).data
    assert {v['artifact_id']: v['change_kind'] for v in result['changes']} == {
        aid(): 'retired', aid(number=2): 'removed', aid(number=3): 'added'}
    assert result['inventory_delta'] == {'scope': 'supplied_artifact_sets',
        'added_ids': [aid(number=3)], 'removed_ids': [aid(number=2)]}
    assert result['configuration_scope'] == {'state': 'not_evaluated'}


@pytest.mark.parametrize('case', ['one_config', 'wrong_project', 'wrong_prefix', 'bad_bound',
                                'unknown_timing_subject', 'missing_timing', 'unparseable_timing'])
def test_unsupported_or_unbound_semantics_fail_instead_of_becoming_success(case):
    old = requirement(); new = deepcopy(old); options = {}
    if case == 'one_config':
        options['before_configuration'] = ProjectConfiguration(configuration_value())
    elif case in ('wrong_project', 'wrong_prefix'):
        config = configuration_value(**({'project_id': 'foreign'} if case == 'wrong_project' else {'id_prefix': 'AB'}))
        options.update(before_configuration=ProjectConfiguration(config), after_configuration=ProjectConfiguration(config))
    else:
        identity = aid(number=99) if case == 'unknown_timing_subject' else aid()
        options['timing_bounds'] = {identity: 'guess' if case == 'bad_bound' else 'maximum'}
        if case == 'unparseable_timing':
            old['timing'] = new['timing'] = 'within ten seconds'
    with pytest.raises(ModelError):
        compare(old, new, **options)


def test_unchanged_invalid_artifact_fields_are_not_hidden_by_empty_diff():
    bad = requirement(priority='urgent')
    with pytest.raises(ModelError):
        compare(bad, bad)


def test_data_only_comparison_owns_results_and_preserves_input_order_independence():
    old = requirement(thresholds=[{'maximum': 10}]); new = deepcopy(old); new['thresholds'][0]['maximum'] = 5
    other = domain_value('goal', id=aid('goal')); saved = deepcopy((old, new, other))
    before, after = inputs(old, other), inputs(other, new)
    with no_write_attempts(), patch('builtins.input', side_effect=AssertionError), patch('secrets.token_bytes', side_effect=AssertionError):
        result = compare_semantic(before, after)
        reversed_result = compare_semantic(inputs(other, old), inputs(new, other))
    expected = result.data
    assert expected == reversed_result.data and (old, new, other) == saved
    detached = result.data; detached['changes'][0]['fields'][0]['after'][0]['maximum'] = 999
    assert result.data == expected and result.sha256 == canonical_json_sha256(expected)
    assert expected['project_configuration']['state'] == 'not_supplied'
    assert expected['evidence_currency']['state'] == expected['configuration_scope']['state'] == 'not_evaluated'
    assert not expected['write_authorized'] and not expected['approval_granted']


def test_public_comparison_has_the_same_data_contract_in_a_fresh_isolated_process(tmp_path):
    old = requirement(timing='PT2S'); new = requirement(timing='PT1S')
    expected = compare(old, new, timing_bounds={aid(): 'maximum'})
    body = ("import json\nfrom specroad.query import compare_semantic\n"
            "from specroad.graph.comparison import ComparisonInputs\n"
            "from specroad.graph.relations import SourceRelations\n"
            "left=ComparisonInputs('sample',[SourceRelations(" + repr(artifact_bytes(old)) + ")])\n"
            "right=ComparisonInputs('sample',[SourceRelations(" + repr(artifact_bytes(new)) + ")])\n"
            "print(json.dumps(compare_semantic(left,right,timing_bounds=" + repr({aid(): 'maximum'}) + ").data))\n")
    completed = run_core(body, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == expected
