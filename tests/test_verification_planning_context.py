"""Appendix L.2.1 admission and exact fields, without rewriting old Evidence."""
from copy import deepcopy

import pytest

from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import (VerificationContext, verification_context_projection,
    assess_verification_context)
from support.domain import domain_value, waiver, relation
from support.records import ref
from support.read_only import no_write_attempts
from test_verification_context import configuration, evidence_for
from test_verification_aggregation import scenario, aggregate, subject
from test_verification_run_selection import observation


def value(kind, **changes):
    return domain_value(kind, language='en', text_direction='ltr',
        **({'outcome': 'An editable project.', 'priority': 'high'} if kind == 'capability' else {}),
        **changes)


def owned(data):
    return DomainArtifact(canonical_json_bytes(data))


@pytest.mark.parametrize('kind', ['capability', 'task'])
def test_exact_native_projection_uses_only_specified_present_fields(kind):
    data = value(kind, display_id='planning-subject',
        applicability={'op': 'literal', 'value': True},
        external_identities=[{'source': 'fixture', 'id': 'external:1'}],
        provenance=[{'locator': 'manual:source', 'captured_at': '2026-01-01T00:00:00Z',
                     'excerpt': 'Review source'}],
        extensions={'test.semantic': {'revision': 4, 'captured_at': 'semantic', 'ordered': [2, 1]}})
    expected = {name: data[name] for name in (
        'schema_version', 'id', 'id_scheme', 'artifact_type', 'title', 'language', 'text_direction',
        'owner', 'applicability', 'extensions', 'external_identities', 'display_id', 'description')}
    expected.update({name: data[name] for name in (
        ('outcome', 'priority') if kind == 'capability' else ('done_criteria',))})
    expected['provenance'] = [{'locator': 'manual:source', 'excerpt': 'Review source'}]
    original = deepcopy(data)
    with no_write_attempts():
        ctx = VerificationContext(owned(data), configuration=None)
    assert verification_context_projection(owned(data)) == expected
    assert ctx.context_sha256 == canonical_json_sha256(expected)
    assert data == original and ctx.data['hash_algorithm'] == 'verification_context_hash-v1'


SEMANTIC = [
    ('title', 'Changed title'), ('language', 'de-DE'), ('text_direction', 'rtl'),
    ('owner', 'another team'), ('description', 'Different behavior'),
    ('applicability', {'op': 'literal', 'value': False}),
    ('extensions', {'test.semantic': {'revision': 2, 'maturity': 'semantic', 'captured_at': 'business'}}),
    ('provenance', [{'locator': 'manual:other', 'captured_at': '2026-01-01T00:00:00Z', 'excerpt': 'Other source'}]),
    ('external_identities', [{'source': 'new', 'id': '123'}]), ('display_id', 'Changed-ID')]


@pytest.mark.parametrize('kind', ['capability', 'task'])
@pytest.mark.parametrize('field,changed', SEMANTIC)
def test_each_shared_business_field_invalidates_old_bound_evidence(kind, field, changed):
    original = value(kind); updated = deepcopy(original); updated[field] = changed
    old = VerificationContext(owned(original), configuration=configuration())
    current = VerificationContext(owned(updated), configuration=configuration())
    evidence = evidence_for(old); before = evidence.source_bytes
    with no_write_attempts(): result = assess_verification_context(current, evidence)
    assert result.data['freshness'] == 'stale' and current.context_sha256 != old.context_sha256
    assert evidence.source_bytes == before


@pytest.mark.parametrize('kind,field,changed', [
    ('capability', 'outcome', 'Different outcome'), ('capability', 'priority', 'low'),
    ('task', 'done_criteria', ['First', 'Second']), ('task', 'done_criteria', ['Different criterion'])])
def test_type_specific_business_fields_invalidate_old_evidence(kind, field, changed):
    original = value(kind); current = deepcopy(original); current[field] = changed
    old = VerificationContext(owned(original), configuration=None)
    new = VerificationContext(owned(current), configuration=None)
    assert old.context_sha256 != new.context_sha256


@pytest.mark.parametrize('kind', ['capability', 'task'])
@pytest.mark.parametrize('changes', [
    {'revision': 3}, {'created_at': '2026-10-01T00:00:00Z'}, {'updated_at': '2026-10-02T00:00:00Z'},
    {'created_by': {'actor_type': 'tool', 'actor_id': 'importer'}},
    {'updated_by': {'actor_type': 'human', 'actor_id': 'editor'}},
    {'maturity': 'in_review'}, {'implementation_status': 'implemented'},
    {'verification_plan_status': 'running'}, {'verification_waiver': waiver()},
    {'relations': [relation('references', ref('SRC'))]}, {'tags': ['reviewed']},
])
def test_excluded_workflow_audit_and_relation_fields_keep_context_hash(kind, changes):
    old = VerificationContext(owned(value(kind)), configuration=configuration())
    changed = value(kind); changed.update(changes)
    current = VerificationContext(owned(changed), configuration=configuration())
    assert current.context_sha256 == old.context_sha256
    assert current.subject_binding['artifact_sha256'] != old.subject_binding['artifact_sha256']
    assert assess_verification_context(current, evidence_for(old)).data['freshness'] == 'current'


@pytest.mark.parametrize('kind', ['capability', 'task'])
def test_optional_presence_arrays_and_nested_audit_named_data_remain_semantic(kind):
    original = value(kind); without = deepcopy(original); without.pop('language')
    assert VerificationContext(owned(without), configuration=None).context_sha256 != \
           VerificationContext(owned(original), configuration=None).context_sha256
    a = {'locator': 'a', 'captured_at': '2026-01-01T00:00:00Z', 'excerpt': 'Source A'}
    b = {**a, 'locator': 'b', 'excerpt': 'Source B'}
    for key, a, b in [('extensions', {'sample.data': {'revision': 1}}, {'sample.data': {'revision': 2}}),
                     ('provenance', [a, b], [b, a])]:
        first = {**original, key: a}; second = {**original, key: b}
        assert VerificationContext(owned(first), configuration=None).context_sha256 != \
               VerificationContext(owned(second), configuration=None).context_sha256
    source = {'locator': 'manual:source', 'captured_at': '2026-01-01T00:00:00Z', 'excerpt': 'Source'}
    first = {**original, 'provenance': [source]}
    second = {**original, 'provenance': [{**source, 'captured_at': '2026-10-22T00:00:00Z'}]}
    assert VerificationContext(owned(first), configuration=None).context_sha256 == \
           VerificationContext(owned(second), configuration=None).context_sha256


@pytest.mark.parametrize('kind', ['capability', 'task'])
@pytest.mark.parametrize('direct', [False, True])
@pytest.mark.parametrize('mutation,expected', [('none', 'passed'), ('failure', 'failed'),
    ('subject_hash', 'stale'), ('configuration', 'incomplete'), ('missing_subject', 'incomplete')])
def test_existing_evidence_is_evaluated_natively_and_never_rebound(kind, direct, mutation, expected):
    records, evaluation, cfg, key = scenario(subject_kind=kind, direct=direct)
    item = observation(records, evaluation, key, run='ci:expected', result='passed')
    if mutation == 'failure': item['result'] = 'failed'
    elif mutation == 'subject_hash': item['subjects'][0]['verification_context_sha256'] = 'f' * 64
    elif mutation == 'configuration': item['configuration_hash'] = 'f' * 64
    elif mutation == 'missing_subject': item['subjects'] = item['subjects'][1:]
    before = canonical_json_bytes(item)
    with no_write_attempts(): report = aggregate(records + [item], evaluation, cfg)
    assert subject(report)['verification_result'] == expected
    assert canonical_json_bytes(item) == before


@pytest.mark.parametrize('kind', ['capability', 'task'])
def test_untyped_or_unknown_schema_data_cannot_bypass_native_admission(kind):
    data = value(kind)
    with pytest.raises(ModelError): VerificationContext(data, configuration=None)
    data['schema_version'] = '9.0.0'
    with pytest.raises(ModelError): VerificationContext(owned(data), configuration=None)
