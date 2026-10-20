"""Complete mapping observations with exact contexts and explicit external IDs."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from itertools import combinations
import json
from xml.sax.saxutils import quoteattr

import pytest

from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.verification import (JUnitDocument, JUnitMapping, JUnitMappingError,
    JUnitMappingRules, JUnitExternalIdentifiers, JUnitMappingAnalysis,
    analyze_junit_candidates, map_junit_candidates)
from support.artifacts import artifact_bytes
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import ref
from test_junit_mapping import ATTRIBUTES, REPORT, mapping, mapping_value, target


def report(*cases):
    parts = []
    for attrs, body in cases:
        attributes = ' '.join(key + '=' + quoteattr(value) for key, value in attrs.items())
        parts.append('<testcase ' + attributes + '>' + body + '</testcase>')
    return JUnitDocument(('<testsuite>' + ''.join(parts) + '</testsuite>').encode())


def rules(fields=('name',), rows=None):
    data = mapping_value(fields, rows)
    data['format_version'] = 'junit-mapping-rules-v1'
    return JUnitMappingRules(artifact_bytes(data))


def external(document, entries):
    return JUnitExternalIdentifiers(artifact_bytes({
        'format_version': 'junit-external-identifiers-v1', 'source_sha256': document.sha256,
        'entries': [{'testcase_index': index, 'external_id': identity} for index, identity in entries]}))


def row(identity, target_id=None):
    return {'identity': identity, 'target_id': ref('TEST') if target_id is None else target_id}


def accounting(value):
    count = value['testcase_count']
    resolved = {c['testcase_index'] for c in value['candidates']}
    rejected = set(value['rejected_testcase_indexes'])
    diagnosed = {n for d in value['diagnostics'] for n in d['testcase_indexes']}
    assert resolved.isdisjoint(rejected) and resolved | rejected == set(range(count))
    assert rejected == diagnosed
    assert [c['testcase_index'] for c in value['observations']] == list(range(count))
    assert value['mapping_complete'] == (not value['diagnostics'])
    for flag in ('import_policy_applied', 'test_code_executed', 'evidence_created',
                 'run_context_bound', 'project_targets_verified', 'full_verification_evaluated',
                 'write_authorized', 'approval_granted'):
        assert value[flag] is False


@pytest.mark.parametrize('kind', ['test', 'verification'])
@pytest.mark.parametrize('field', ['classname', 'file'])
def test_equal_test_names_with_different_selected_context_stay_separate(kind, field):
    items = [target(kind), target(kind, id=ref('TEST' if kind == 'test' else 'VER', '1'))]
    first, second = dict(ATTRIBUTES), {**ATTRIBUTES, field: 'different'}
    document = report((first, ''), (second, '<failure/>'))
    selected = ['name', field]
    rows = [row({key: attrs[key] for key in selected}, item.data['id'])
            for attrs, item in zip((first, second), items)]
    data = analyze_junit_candidates(document, rules(selected, rows), targets=items).data
    accounting(data)
    assert data['mapping_complete'] and len(data['candidates']) == 2
    assert [c['result'] for c in data['candidates']] == ['passed', 'failed']
    assert [c['target']['artifact_id'] for c in data['candidates']] == [item.data['id'] for item in items]
    assert [c['context'][field] for c in data['observations']] == [first[field], second[field]]


@pytest.mark.parametrize('field', ['classname', 'file'])
def test_omitted_context_does_not_collapse_distinct_cases_or_invent_a_contradiction(field):
    document = report((ATTRIBUTES, ''), ({**ATTRIBUTES, field: 'different'}, '<failure/>'))
    data = analyze_junit_candidates(document, rules(), targets=[target()]).data
    accounting(data)
    assert data['candidates'] == [] and data['rejected_testcase_indexes'] == [0, 1]
    assert [(d['category'], d['reason'], d['testcase_indexes']) for d in data['diagnostics']] == [
        ('ambiguous', 'duplicate_junit_testcase_identity', [0, 1])]
    assert data['observations'][0]['context'] != data['observations'][1]['context']


def test_separate_diagnoses_account_for_every_invalid_case_and_keep_independent_observation():
    document = report(
        ({'name': 'valid'}, ''),
        ({'name': 'unmapped'}, ''),
        ({'name': 'ambiguous'}, ''),
        ({'name': 'mixed'}, '<failure/><skipped/>'),
        ({'name': 'repeated'}, ''),
        ({'name': 'repeated'}, '<failure/>'))
    rows = [row({'name': name}) for name in ('valid', 'ambiguous', 'mixed', 'repeated')]
    rows.append(row({'name': 'ambiguous'}, ref('VER')))
    data = analyze_junit_candidates(document, rules(rows=rows), targets=[target(), target('verification')]).data
    accounting(data)
    assert [(c['testcase_index'], c['result']) for c in data['candidates']] == [(0, 'passed')]
    assert [(d['category'], d['reason'], d['testcase_indexes']) for d in data['diagnostics']] == [
        ('unmapped', 'junit_testcase_unmapped', [1]),
        ('ambiguous', 'junit_mapping_ambiguous', [2]),
        ('contradictory', 'conflicting_junit_testcase_outcomes', [3]),
        ('ambiguous', 'duplicate_junit_testcase_identity', [4, 5]),
        ('contradictory', 'conflicting_junit_testcase_results', [4, 5])]
    assert data['diagnostics'][1]['mapping_indexes'] == [1, 4]
    assert [d['code'] for d in data['diagnostics']] == ['SRV043', 'SRV043', 'SRV090', 'SRV043', 'SRV090']


@pytest.mark.parametrize('outcomes', [
    ('', '<failure/>'), ('<error/>', '<skipped/>'), ('<error/>', '<failure/>')])
def test_conflicting_repeated_observations_never_choose_a_favorable_result(outcomes):
    chosen = rules()
    for bodies in (outcomes, outcomes[::-1]):
        data = analyze_junit_candidates(report(*[(ATTRIBUTES, body) for body in bodies]),
                                         chosen, targets=[target()]).data
        accounting(data)
        assert data['candidates'] == []
        assert {d['reason'] for d in data['diagnostics']} == {
            'duplicate_junit_testcase_identity', 'conflicting_junit_testcase_results'}
        assert all(d['testcase_indexes'] == [0, 1] for d in data['diagnostics'])


def test_identical_repeated_results_are_ambiguous_without_being_called_contradictory():
    data = analyze_junit_candidates(report((ATTRIBUTES, '<failure/>'), (ATTRIBUTES, '<failure/>')),
                                     rules(), targets=[target()]).data
    accounting(data)
    assert data['candidates'] == [] and len(data['diagnostics']) == 1
    assert data['diagnostics'][0]['category'] == 'ambiguous'


def test_missing_identity_and_mixed_outcomes_are_both_reported():
    data = analyze_junit_candidates(report(({'classname': 'class'}, '<failure/><error/>')),
                                     rules(), targets=[target()]).data
    accounting(data)
    assert {d['reason'] for d in data['diagnostics']} == {
        'junit_testcase_identity_missing', 'conflicting_junit_testcase_outcomes'}
    missing, = [d for d in data['diagnostics'] if d['category'] == 'unmapped']
    assert missing['missing_fields'] == ['name']


def test_missing_and_empty_attributes_keep_distinct_observations_and_never_use_suite_defaults():
    document = JUnitDocument(b'<testsuite name="accepts"><testcase/><testcase name=""/></testsuite>')
    data = analyze_junit_candidates(document, rules(), targets=[target()]).data
    accounting(data)
    assert [c['identity'] for c in data['observations']] == [{'name': None}, {'name': ''}]
    assert [d['testcase_indexes'] for d in data['diagnostics']] == [[0], [1]]
    assert all(d['reason'] == 'junit_testcase_identity_missing' for d in data['diagnostics'])


@pytest.mark.parametrize('same_target', [False, True])
def test_ambiguous_mapping_rows_are_never_resolved_by_first_last_or_equal_target(same_target):
    rows = [row({'name': 'accepts'}), row({'name': 'accepts'}, ref('TEST') if same_target else ref('VER'))]
    data = analyze_junit_candidates(report((ATTRIBUTES, '')), rules(rows=rows),
                                     targets=[target(), target('verification')]).data
    accounting(data)
    assert data['candidates'] == []
    assert data['diagnostics'][0]['reason'] == 'junit_mapping_ambiguous'
    assert data['diagnostics'][0]['mapping_indexes'] == [0, 1]


def test_bad_unused_rows_remain_visible_in_an_empty_report():
    rows = [row({'name': 'unknown'}, ref('TEST', '1')),
            row({'name': 'duplicate'}), row({'name': 'duplicate'})]
    data = analyze_junit_candidates(JUnitDocument(b'<testsuite/>'), rules(rows=rows), targets=[target()]).data
    accounting(data)
    assert not data['mapping_complete'] and data['testcase_count'] == 0
    assert {(d['category'], d['reason']) for d in data['diagnostics']} == {
        ('unmapped', 'junit_mapping_target_not_found'), ('ambiguous', 'junit_mapping_ambiguous')}
    assert all(d['testcase_indexes'] == [] for d in data['diagnostics'])


def test_missing_target_rejects_only_affected_observation_and_does_not_invent_artifact():
    document = report(({'name': 'good'}, '<failure/>'), ({'name': 'missing'}, ''))
    chosen = rules(rows=[row({'name': 'good'}), row({'name': 'missing'}, 'SECRET_TARGET')])
    data = analyze_junit_candidates(document, chosen, targets=[target()]).data
    accounting(data)
    assert [(c['testcase_index'], c['result']) for c in data['candidates']] == [(0, 'failed')]
    assert data['rejected_testcase_indexes'] == [1]
    assert all(d['reason'] == 'junit_mapping_target_not_found' for d in data['diagnostics'])
    assert 'SECRET_TARGET' not in json.dumps(data['diagnostics'])
    assert len(data['targets']) == 1


@pytest.mark.parametrize('fields', [keys for n in (1, 2, 3, 4)
    for keys in combinations(('classname', 'name', 'file', 'external_id'), n)
    if 'external_id' in keys])
def test_external_identifier_combinations_use_explicit_source_bound_values(fields):
    document = report((ATTRIBUTES, '<error/>'))
    supplied = {**ATTRIBUTES, 'external_id': 'producer:case-7'}
    chosen = rules(fields, [row({key: supplied[key] for key in fields}, ref('VER'))])
    sidecar = external(document, [(0, supplied['external_id'])])
    data = analyze_junit_candidates(document, chosen, targets=[target('verification')],
                                     external_identifiers=sidecar).data
    accounting(data)
    candidate, = data['candidates']
    assert candidate['identity'] == {key: supplied[key] for key in fields}
    assert (candidate['result'], candidate['junit_outcome']) == ('failed', 'error')
    assert candidate['target']['artifact_id'] == ref('VER')
    assert data['external_identifiers'] == {
        'sha256': canonical_json_sha256(sidecar.data), 'size': len(sidecar.source_bytes),
        'source_sha256': sha256(sidecar.source_bytes).hexdigest()}


def test_nested_core_ordinals_bind_external_ids_without_counting_opaque_testcases():
    document = JUnitDocument(b'''<testsuites><testsuite><extension><testcase name="ignored"/></extension>
      <testcase name="same"/><testsuite><testcase name="same"><failure/></testcase></testsuite>
    </testsuite></testsuites>''')
    chosen = rules(['external_id'], [row({'external_id': 'a'}), row({'external_id': 'b'}, ref('VER'))])
    data = analyze_junit_candidates(document, chosen, targets=[target(), target('verification')],
                                     external_identifiers=external(document, [(1, 'b'), (0, 'a')])).data
    accounting(data)
    assert [c['identity'] for c in data['candidates']] == [{'external_id': 'a'}, {'external_id': 'b'}]
    assert [c['testcase_pointer'] for c in data['candidates']] == [
        '/root/children/0/children/0', '/root/children/0/children/1/children/0']
    assert [c['result'] for c in data['candidates']] == ['passed', 'failed']


def test_external_identifier_is_not_guessed_from_xml_extensions_or_target_metadata():
    document = JUnitDocument(b'''<testsuite><testcase name="accepts" external_id="suite/test-case">
      <properties><property name="external_id" value="suite/test-case"/></properties>
    </testcase></testsuite>''')
    chosen = rules(['external_id'], [row({'external_id': 'suite/test-case'})])
    data = analyze_junit_candidates(document, chosen, targets=[target()],
                                     external_identifiers=external(document, [])).data
    accounting(data)
    assert data['candidates'] == [] and data['observations'][0]['identity'] == {'external_id': None}
    assert data['diagnostics'][0]['reason'] == 'junit_testcase_identity_missing'
    assert data['diagnostics'][0]['missing_fields'] == ['external_id']


def test_partial_sidecar_keeps_missing_occurrences_explicit():
    document = report(({'name': 'one'}, ''), ({'name': 'two'}, '<skipped/>'))
    chosen = rules(['external_id'], [row({'external_id': 'explicit'})])
    data = analyze_junit_candidates(document, chosen, targets=[target()],
                                     external_identifiers=external(document, [(1, 'explicit')])).data
    accounting(data)
    assert data['rejected_testcase_indexes'] == [0]
    assert [(c['testcase_index'], c['result']) for c in data['candidates']] == [(1, 'skipped')]


def test_external_id_is_exact_and_never_normalized_or_treated_as_a_path():
    document = report((ATTRIBUTES, ''))
    identifier = '../literal/ Cäsé '
    chosen = rules(['external_id'], [row({'external_id': identifier})])
    for given, resolved in ((identifier, True), (identifier.strip(), False),
                            (identifier.lower(), False), ('../literal/ Ca\u0308se\u0301 ', False)):
        data = analyze_junit_candidates(document, chosen, targets=[target()],
                                         external_identifiers=external(document, [(0, given)])).data
        accounting(data)
        assert data['mapping_complete'] == resolved
        assert len(data['candidates']) == int(resolved)


def test_same_external_id_can_be_disambiguated_only_by_explicit_context_fields():
    document = report((ATTRIBUTES, ''), ({**ATTRIBUTES, 'classname': 'other'}, '<error/>'))
    sidecar = external(document, [(0, 'id'), (1, 'id')])
    ambiguous = analyze_junit_candidates(document, rules(['external_id'], [row({'external_id': 'id'})]),
                                          targets=[target()], external_identifiers=sidecar).data
    accounting(ambiguous)
    assert ambiguous['candidates'] == [] and ambiguous['diagnostics'][0]['category'] == 'ambiguous'
    chosen = rules(['classname', 'external_id'], [
        row({'classname': 'suite.A', 'external_id': 'id'}),
        row({'classname': 'other', 'external_id': 'id'}, ref('VER'))])
    data = analyze_junit_candidates(document, chosen, targets=[target(), target('verification')],
                                     external_identifiers=sidecar).data
    accounting(data)
    assert data['mapping_complete'] and [c['result'] for c in data['candidates']] == ['passed', 'failed']


@pytest.mark.parametrize('raw', [
    b'<testsuite><testcase name="accepts"/></testsuite> ',
    '<testsuite><testcase name="accepts"/></testsuite>'.encode('utf-16')])
def test_equivalent_parse_values_cannot_reuse_another_reports_sidecar(raw):
    original = JUnitDocument(b'<testsuite><testcase name="accepts"/></testsuite>')
    changed = JUnitDocument(raw)
    assert original.data['root'] == changed.data['root']
    with pytest.raises(JUnitMappingError) as caught:
        analyze_junit_candidates(changed, rules(['external_id'], [row({'external_id': 'id'})]),
                                  targets=[target()], external_identifiers=external(original, [(0, 'id')]))
    assert caught.value.reason == 'junit_external_source_mismatch'
    assert caught.value.pointer == '/source_sha256'


@pytest.mark.parametrize('index', [1, 9999])
def test_a_sidecar_may_not_refer_to_an_absent_core_ordinal(index):
    document = report((ATTRIBUTES, ''))
    with pytest.raises(JUnitMappingError) as caught:
        analyze_junit_candidates(document, rules(['external_id'], [row({'external_id': 'id'})]),
                                  targets=[target()], external_identifiers=external(document, [(index, 'id')]))
    assert caught.value.reason == 'junit_external_index_out_of_range'


@pytest.mark.parametrize('bad', [None, {}, b'{}'])
def test_selected_external_identity_requires_a_typed_sidecar(bad):
    with pytest.raises(JUnitMappingError) as caught:
        analyze_junit_candidates(report((ATTRIBUTES, '')), rules(['external_id'], [row({'external_id': 'id'})]),
                                  targets=[target()], external_identifiers=bad)
    assert caught.value.reason == 'typed_junit_external_identifiers_required'


def test_unselected_external_data_is_rejected_instead_of_silently_ignored():
    document = report((ATTRIBUTES, ''))
    with pytest.raises(JUnitMappingError) as caught:
        analyze_junit_candidates(document, rules(), targets=[target()],
                                  external_identifiers=external(document, [(0, 'id')]))
    assert caught.value.reason == 'unused_junit_external_identifiers'


@pytest.mark.parametrize('change,reason', [
    ({'format_version': 'unknown'}, 'unsupported_junit_external_identifiers_version'),
    ({'extra': True}, 'invalid_junit_external_identifiers_fields'),
    ({'source_sha256': 'A' * 64}, 'invalid_junit_external_source_hash'),
    ({'source_sha256': 'g' * 64}, 'invalid_junit_external_source_hash'),
    ({'source_sha256': 'a' * 63}, 'invalid_junit_external_source_hash'),
    ({'source_sha256': 1}, 'invalid_junit_external_source_hash'),
    ({'entries': {}}, 'invalid_junit_external_entries'),
    ({'entries': None}, 'invalid_junit_external_entries')])
def test_external_document_has_a_closed_versioned_contract(change, reason):
    value = {'format_version': 'junit-external-identifiers-v1', 'source_sha256': 'a' * 64, 'entries': []}
    with pytest.raises(JUnitMappingError) as caught:
        JUnitExternalIdentifiers(artifact_bytes({**value, **change}))
    assert caught.value.reason == reason


@pytest.mark.parametrize('entry,reason', [
    (None, 'invalid_junit_external_entry'), ({}, 'invalid_junit_external_entry'),
    ({'testcase_index': 0, 'external_id': 'id', 'path': 'x'}, 'invalid_junit_external_entry'),
    ({'testcase_index': True, 'external_id': 'id'}, 'invalid_junit_external_index'),
    ({'testcase_index': -1, 'external_id': 'id'}, 'invalid_junit_external_index'),
    ({'testcase_index': 10000, 'external_id': 'id'}, 'invalid_junit_external_index'),
    ({'testcase_index': 0.0, 'external_id': 'id'}, 'invalid_junit_external_index'),
    ({'testcase_index': '0', 'external_id': 'id'}, 'invalid_junit_external_index'),
    ({'testcase_index': 0, 'external_id': ''}, 'invalid_junit_external_id'),
    ({'testcase_index': 0, 'external_id': None}, 'invalid_junit_external_id'),
    ({'testcase_index': 0, 'external_id': 1}, 'invalid_junit_external_id')])
def test_external_entries_are_exact_nonempty_identifiers_on_nonnegative_integer_ordinals(entry, reason):
    value = {'format_version': 'junit-external-identifiers-v1', 'source_sha256': 'a' * 64, 'entries': [entry]}
    with pytest.raises(JUnitMappingError) as caught:
        JUnitExternalIdentifiers(artifact_bytes(value))
    assert caught.value.reason == reason and caught.value.pointer.startswith('/entries/0')


@pytest.mark.parametrize('other', ['a', 'b'])
def test_duplicate_external_ordinals_are_invalid_even_when_ids_agree(other):
    with pytest.raises(JUnitMappingError) as caught:
        external(report((ATTRIBUTES, '')), [(0, 'a'), (0, other)])
    assert caught.value.reason == 'duplicate_junit_external_index'


@pytest.mark.parametrize('cls', [JUnitMappingRules, JUnitExternalIdentifiers], ids=['rules', 'external'])
@pytest.mark.parametrize('raw', ['{}', bytearray(b'{}'), memoryview(b'{}'), None])
def test_extended_inputs_require_owned_bytes(cls, raw):
    with pytest.raises(JUnitMappingError) as caught:
        cls(raw)
    assert caught.value.reason.endswith('_bytes_required')


@pytest.mark.parametrize('cls', [JUnitMappingRules, JUnitExternalIdentifiers], ids=['rules', 'external'])
@pytest.mark.parametrize('raw,reason', [
    (b'{"entries":[],"entries":[]}', 'duplicate_key'), (b'{} trailing', 'invalid_json'),
    (b'[]', 'object_required'), (b'{}' + bytes([255]), 'invalid_utf8')])
def test_extended_inputs_preserve_strict_native_json_failures(cls, raw, reason):
    with pytest.raises(ModelError) as caught:
        cls(raw)
    assert caught.value.reason == reason


def test_extended_input_byte_and_count_boundaries_are_hard_and_usable():
    document = report((ATTRIBUTES, ''))
    for cls, raw in ((JUnitMappingRules, rules().source_bytes),
                     (JUnitExternalIdentifiers, external(document, []).source_bytes)):
        padded = raw + b' ' * (4 * 1024 * 1024 - len(raw))
        assert cls(padded).data == cls(raw).data
        with pytest.raises(JUnitMappingError) as caught:
            cls(padded + b' ')
        assert caught.value.reason.endswith('_byte_limit')
    entries = [(n, 'id') for n in range(10000)]
    assert len(external(document, entries).data['entries']) == 10000
    with pytest.raises(JUnitMappingError) as caught:
        external(document, entries + [(0, 'overflow')])
    assert caught.value.reason == 'invalid_junit_external_entries'
    assert len(rules(rows=[row({'name': 'same'})] * 10000).data['bindings']) == 10000
    with pytest.raises(JUnitMappingError) as caught:
        rules(rows=[row({'name': 'same'})] * 10001)
    assert caught.value.reason == 'invalid_junit_mapping_bindings'


@pytest.mark.parametrize('change,reason', [
    ({'format_version': 'junit-mapping-v1'}, 'unsupported_junit_mapping_version'),
    ({'identity_fields': []}, 'invalid_junit_identity_fields'),
    ({'identity_fields': ['name', 'name']}, 'invalid_junit_identity_fields'),
    ({'identity_fields': ['name', 'path']}, 'invalid_junit_identity_fields'),
    ({'extra': True}, 'invalid_junit_mapping_fields'),
    ({'bindings': [row({'name': ''})]}, 'invalid_junit_mapping_identity'),
    ({'bindings': [{'identity': {'name': 'accepts'}, 'target_id': None}]}, 'invalid_junit_mapping_target')])
def test_analysis_rules_keep_mapping_schema_guards(change, reason):
    value = rules().data
    with pytest.raises(JUnitMappingError) as caught:
        JUnitMappingRules(artifact_bytes({**value, **change}))
    assert caught.value.reason == reason


@pytest.mark.parametrize('field,value,reason', [
    ('document', {}, 'typed_junit_document_required'),
    ('mapping', b'{}', 'typed_junit_mapping_required'),
    ('targets', None, 'typed_junit_targets_required'),
    ('targets', [{}], 'typed_junit_target_required')])
def test_analysis_boundary_requires_native_input_types(field, value, reason):
    args = {'document': report((ATTRIBUTES, '')), 'mapping': rules(), 'targets': [target()]}
    args[field] = value
    with pytest.raises(JUnitMappingError) as caught:
        analyze_junit_candidates(**args)
    assert caught.value.reason == reason


def test_duplicate_or_forged_native_targets_are_not_accepted():
    item = target()
    with pytest.raises(JUnitMappingError) as caught:
        analyze_junit_candidates(report((ATTRIBUTES, '')), rules(), targets=[item, item])
    assert caught.value.reason == 'duplicate_junit_target'
    object.__setattr__(item, 'source_bytes', b'{}')
    with pytest.raises(ModelError):
        analyze_junit_candidates(report((ATTRIBUTES, '')), rules(), targets=[item])


def test_analysis_and_sidecar_own_values_and_revalidate_original_bytes_not_caches():
    document = report((ATTRIBUTES, '<error/>'))
    chosen = rules(['external_id'], [row({'external_id': 'id'})])
    sidecar = external(document, [(0, 'id')])
    value = analyze_junit_candidates(document, chosen, targets=[target()], external_identifiers=sidecar)
    expected = value.data
    for obj in (chosen, sidecar, document):
        obj.data.clear()
        object.__setattr__(obj, '_encoded', b'{}')
    value.data['observations'].clear(); value.data['targets'].clear()
    assert value.data == expected and value.sha256 == canonical_json_sha256(expected)
    assert analyze_junit_candidates(document, chosen, targets=[target()],
                                    external_identifiers=sidecar).data == expected
    for obj in (chosen, sidecar, value):
        with pytest.raises(FrozenInstanceError):
            obj._encoded = b'{}'
        with pytest.raises(TypeError):
            bool(obj)
    with pytest.raises(TypeError):
        JUnitMappingAnalysis(expected)


def test_input_order_and_whitespace_do_not_change_candidate_meaning_but_keep_provenance():
    document = report(({'name': 'a'}, ''), ({'name': 'b'}, '<failure/>'))
    rows = [row({'name': 'a'}), row({'name': 'b'}, ref('VER'))]
    a = analyze_junit_candidates(document, rules(rows=rows), targets=[target(), target('verification')])
    reordered = analyze_junit_candidates(document, rules(rows=rows),
                                         targets=[target('verification'), target()])
    assert a.data == reordered.data and a.sha256 == reordered.sha256
    formatted = JUnitMappingRules(json.dumps(rules(rows=rows).data, indent=1).encode())
    b = analyze_junit_candidates(document, formatted, targets=[target(), target('verification')])
    assert a.data['candidates'] == b.data['candidates']
    assert a.data['mapping_sha256'] == b.data['mapping_sha256']
    assert a.data['mapping_source_sha256'] != b.data['mapping_source_sha256']
    changed = analyze_junit_candidates(document, rules(rows=rows),
                                       targets=[target(title='changed'), target('verification')])
    assert changed.data['candidates'][0]['target']['record_sha256'] != a.data['candidates'][0]['target']['record_sha256']


def test_strict_w_api_is_unchanged_and_legacy_mapping_is_usable_for_analysis():
    document = report((ATTRIBUTES, '<failure/>'))
    strict = map_junit_candidates(document, mapping(), targets=[target()]).data
    analyzed = analyze_junit_candidates(document, mapping(), targets=[target()]).data
    accounting(analyzed)
    assert analyzed['candidates'] == strict['candidates']
    assert analyzed['source'] == strict['source'] and analyzed['mapping_sha256'] == strict['mapping_sha256']
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(document, rules(), targets=[target()])
    assert caught.value.reason == 'typed_junit_mapping_required'


def test_diagnostics_stay_linear_for_large_duplicate_report_and_mapping():
    document = JUnitDocument(b'<testsuite>' + b'<testcase name="same"/>' * 9999 + b'</testsuite>')
    chosen = rules(rows=[row({'name': 'same'})] * 10000)
    data = analyze_junit_candidates(document, chosen, targets=[target()]).data
    accounting(data)
    assert data['candidates'] == [] and data['rejected_testcase_indexes'] == list(range(9999))
    assert {d['reason'] for d in data['diagnostics']} == {
        'junit_mapping_ambiguous', 'duplicate_junit_testcase_identity'}
    assert sum(len(d['testcase_indexes']) for d in data['diagnostics']) == 19998
    assert sum(len(d['mapping_indexes']) for d in data['diagnostics']) == 10000


def test_analysis_never_opens_paths_resolves_identifiers_or_executes_output(monkeypatch):
    attrs = {**ATTRIBUTES, 'file': '/unavailable/test.py'}
    document = report((attrs, '<error>__import__("os").system("do not execute")</error>'))
    chosen = rules(['file', 'external_id'], [row({'file': attrs['file'], 'external_id': 'file:///unavailable'})])
    sidecar = external(document, [(0, 'file:///unavailable')])
    item = target()
    def forbidden(*args, **kwargs):
        raise AssertionError('Unexpected external access')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('builtins.open', 'io.open', 'os.open', 'time.time',
                     'secrets.token_bytes', 'socket.getaddrinfo'):
            patch.setattr(name, forbidden)
        data = analyze_junit_candidates(document, chosen, targets=[item], external_identifiers=sidecar).data
    accounting(data)
    assert data['candidates'][0]['result'] == 'failed'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_extended_mapping_diagnostics_and_external_binding_work_in_isolated_distributions(tmp_path, mode):
    document = report(({'name': 'valid'}, ''), ({'name': 'mixed'}, '<failure/><error/>'))
    chosen = rules(['external_id'], [row({'external_id': 'a'}), row({'external_id': 'b'})])
    sidecar = external(document, [(0, 'a'), (1, 'b')])
    item = target()
    body = ('import json\nfrom specroad.verification import (JUnitDocument, JUnitMappingRules, '
            'JUnitExternalIdentifiers, VerificationTest, JUnitMappingError, analyze_junit_candidates)\n'
            'd=JUnitDocument(' + repr(document.source_bytes) + ')\n'
            'm=JUnitMappingRules(' + repr(chosen.source_bytes) + ')\n'
            's=JUnitExternalIdentifiers(' + repr(sidecar.source_bytes) + ')\n'
            't=VerificationTest(' + repr(item.source_bytes) + ')\n'
            'value=analyze_junit_candidates(d,m,targets=[t],external_identifiers=s).data\n'
            'try: analyze_junit_candidates(JUnitDocument(b"<testsuite/>"),m,targets=[t],external_identifiers=s)\n'
            'except JUnitMappingError as error: reason=error.reason\n'
            'else: raise AssertionError("Foreign sidecar accepted")\n'
            'print(json.dumps({"value":value,"reason":reason},sort_keys=True))\n')
    if mode == 'core':
        process = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'dist')
        prefix = 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n'
        process = run_python(['-I', '-S', '-B', '-c', prefix + body], tmp_path, capture=True)
    assert process.returncode == 0, process.stderr.decode()
    data = json.loads(process.stdout)
    assert data == {'value': analyze_junit_candidates(document, chosen, targets=[item],
                                                     external_identifiers=sidecar).data,
                    'reason': 'junit_external_source_mismatch'}
