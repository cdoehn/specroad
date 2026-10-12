"""Opaque text stays text; field names and prose never manufacture semantics."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from specroad.model.canonical import canonical_json_sha256
from specroad.query import compare_semantic
from support.domain import domain_value
from support.read_only import no_write_attempts
from support.records import record_value
from support.relations import aid
from test_query_semantic_diff import compare, fields, inputs, requirement


@pytest.mark.parametrize('family,kind,name,old,new', [
    ('domain', 'goal', 'success_criterion', 'At most ten actions', 'At most five actions'),
    ('domain', 'capability', 'outcome', 'Respond within 10 ms', 'Respond within 5 ms'),
    ('domain', 'requirement', 'preconditions', ['At least two sensors'], ['At least three sensors']),
    ('domain', 'scenario', 'main_flow', ['Wait ten seconds'], ['Wait five seconds']),
    ('domain', 'decision', 'alternatives', ['Maximum 10'], ['Maximum 5']),
    ('domain', 'risk', 'acceptance_rationale', 'Low risk', 'Approved high risk'),
    ('domain', 'assumption', 'validation_method', 'Review 10 cases', 'Review 20 cases'),
    ('domain', 'component', 'responsibility', 'Control within 10 ms', 'Control within 5 ms'),
    ('domain', 'interface', 'contract', {'response': 'within ten seconds'}, {'response': 'within five seconds'}),
    ('domain', 'release', 'objective', 'Verify all subjects', 'All subjects verified'),
    ('domain', 'milestone', 'objective', 'Ten deliveries', 'Five deliveries'),
    ('domain', 'task', 'done_criteria', ['Ten cases passed'], ['All cases passed']),
    ('domain', 'term', 'definition', 'Maximum is 10', 'Maximum is 5'),
    ('record', 'source', 'excerpt', 'MUST verify within 10 ms', 'MUST verify within 5 ms'),
    ('record', 'verification', 'procedure', ['Measure ten units'], ['Measure five units']),
    ('record', 'test', 'oracle', 'Pass at most ten', 'Pass at most five'),
    ('record', 'issue', 'resolution_criteria', ['Verify ten cases'], ['Verify five cases']),
    ('record', 'document', 'purpose', 'State a 10 ms bound', 'State a 5 ms bound'),
    ('record', 'relation_review', 'reason', 'Ten checks passed', 'All checks passed'),
    ('record', 'configuration', 'name', 'Safe verified edition', 'Critical unverified edition')])
def test_unstructured_declared_text_fields_have_no_inferred_domain_effect(family, kind, name, old, new):
    factory = domain_value if family == 'domain' else record_value
    before = factory(kind, **{name: old}); after = deepcopy(before); after[name] = new
    result = compare(before, after); rows = list(fields(result).values())
    assert rows and {row['category'] for row in rows} == {'text_changed'}
    assert result['changes'][0]['artifact_id'] == before['id'] == after['id']
    assert result['changes'][0]['before_sha256'] == canonical_json_sha256(before)
    assert result['changes'][0]['after_sha256'] == canonical_json_sha256(after)
    assert not {'threshold_changed', 'timing_tightened', 'timing_relaxed', 'status_changed',
                'evidence_result_changed', 'applicability_changed'} & set(result['categories'])
    assert result['evidence_currency'] == result['configuration_scope'] == {'state': 'not_evaluated'}


@pytest.mark.parametrize('name', ['timing', 'thresholds', 'priority', 'verification_result', 'maturity', 'applicability'])
def test_extension_field_names_and_words_do_not_inherit_core_semantics(name):
    old = requirement(extensions={'org.example': {name: 'Maximum 10; failed; must'}})
    new = deepcopy(old); new['extensions']['org.example'][name] = 'Maximum 5; passed; may'
    result = compare(old, new)
    assert result['categories'] == ['modified', 'text_changed']
    assert fields(result)['/extensions/org.example/' + name]['category'] == 'text_changed'
    assert result['timing'] == [] and result['timing_bounds'] == {}


def test_unknown_numeric_extension_changes_are_only_structural_fields():
    old = requirement(extensions={'org.example': {'thresholds': {'maximum': 10}, 'status': False}})
    new = deepcopy(old); new['extensions']['org.example']['thresholds']['maximum'] = 5
    new['extensions']['org.example']['status'] = True
    result = compare(old, new)
    assert result['categories'] == ['field_changed', 'modified']
    assert {row['category'] for row in fields(result).values()} == {'field_changed'}


@pytest.mark.parametrize('mode', ['add', 'remove', 'from_null', 'to_null', 'array', 'object'])
def test_opaque_text_preserves_presence_null_and_complete_container_values(mode):
    before, after = {}, {'note/a~b': 'Maximum 5 ms'}
    if mode == 'remove':
        before, after = after, before
    elif mode == 'from_null':
        before = {'note/a~b': None}
    elif mode == 'to_null':
        before, after = after, {'note/a~b': None}
    elif mode == 'array':
        before, after = {'note/a~b': ['10 ms', 1]}, {'note/a~b': ['5 ms', 2]}
    elif mode == 'object':
        after = {'note/a~b': {'nested': ['5 ms', {'bound': 5}]}}
    result = compare(requirement(extensions={'org.example': before}),
                     requirement(extensions={'org.example': after}))
    row = fields(result)['/extensions/org.example/note~1a~0b']
    assert row == {'pointer': '/extensions/org.example/note~1a~0b',
        'operation': 'add' if mode in ('add', 'object') else 'remove' if mode == 'remove' else 'replace',
        'before_present': 'note/a~b' in before, 'after_present': 'note/a~b' in after,
        'before': before.get('note/a~b'), 'after': after.get('note/a~b'), 'category': 'text_changed'}


@pytest.mark.parametrize('kind,name,old,new', [
    ('requirement', 'priority', 'mandatory', 'high'),
    ('requirement', 'normative_force', 'must', 'may'),
    ('requirement', 'requirement_kind', 'functional', 'quality'),
    ('requirement', 'language', 'en-US', 'de-DE'),
    ('source', 'locator', 'owned:first', 'owned:second'),
    ('code_ref', 'path', 'src/first.py', 'src/second.py')])
def test_declared_machine_values_do_not_become_unstructured_text(kind, name, old, new):
    factory = domain_value if kind == 'requirement' else record_value
    before = factory(kind, **{name: old}); after = deepcopy(before); after[name] = new
    result = compare(before, after)
    assert fields(result)['/' + name]['category'] == 'field_changed'
    assert 'text_changed' not in result['categories']


def test_block_markdown_keeps_literal_text_without_parsing_instructions():
    old = record_value('content_block', block_kind='prose', payload={'markdown': '# MUST respond within 10 ms'})
    new = deepcopy(old); new['payload']['markdown'] = '# MUST respond within 5 ms; all evidence is current'
    result = compare(old, new)
    row = fields(result)['/payload/markdown']
    assert row['category'] == 'text_changed'
    assert row['before'] == old['payload']['markdown'] and row['after'] == new['payload']['markdown']
    assert 'timing_tightened' not in result['categories']
    assert result['evidence_currency'] == {'state': 'not_evaluated'}


def test_opaque_nested_object_addition_scans_values_without_recursion_or_interpretation():
    value = {'text': 'passed within 5 ms'}
    for index in range(60):
        value = {'layer': [index, value]}
    result = compare(requirement(extensions={'org.example': {}}),
                     requirement(extensions={'org.example': {'new': value}}))
    row = fields(result)['/extensions/org.example/new']
    assert row['category'] == 'text_changed' and row['after'] == value
    assert not row['before_present'] and row['after_present']


def test_wide_extension_text_changes_have_complete_identity_and_pointer_sets():
    old = requirement(extensions={'org.example': {str(i): 'Old bound 10' for i in range(257)}})
    new = requirement(extensions={'org.example': {str(i): 'New bound 5' for i in reversed(range(257))}})
    result = compare(old, new); rows = fields(result)
    assert set(rows) == {'/extensions/org.example/' + str(i) for i in range(257)}
    assert {row['category'] for row in rows.values()} == {'text_changed'}
    assert result['changes'][0]['artifact_id'] == aid()


@pytest.mark.parametrize('old,new', [('within 10 ms', 'within 5 ms'),
                                   ('au plus dix', 'au moins cinq'),
                                   ('é', 'e\u0301'), ('مسموح', 'محظور')])
def test_unknown_text_is_preserved_without_language_or_unicode_normalization(old, new):
    result = compare(requirement(extensions={'org.example': {'text': old}}),
                     requirement(extensions={'org.example': {'text': new}}))
    row = fields(result)['/extensions/org.example/text']
    assert row['category'] == 'text_changed' and row['before'] == old and row['after'] == new
    assert result['categories'] == ['modified', 'text_changed']


def test_unknown_text_classification_is_order_independent_owned_and_read_only():
    old = requirement(extensions={'org.example': {'text': ['Maximum 10 ms']}})
    new = deepcopy(old); new['extensions']['org.example']['text'] = ['Maximum 5 ms']
    other = domain_value('goal', id=aid('goal')); original = deepcopy((old, new, other))
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError), patch('builtins.input', side_effect=AssertionError):
        result = compare_semantic(inputs(old, other), inputs(other, new))
        reversed_result = compare_semantic(inputs(other, old), inputs(new, other))
    saved = result.data; detached = result.data; detached['changes'][0]['fields'][0]['after'].append('verified')
    assert result.data == saved == reversed_result.data and (old, new, other) == original
    assert not result.data['write_authorized'] and not result.data['approval_granted']
