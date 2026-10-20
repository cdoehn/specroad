"""Exact external observations become candidates, never executed or published."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from itertools import combinations
import json

import pytest

from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.storage.record_artifact import RecordArtifact
from specroad.verification import (JUnitDocument, JUnitMapping, JUnitCandidates,
    JUnitMappingError, VerificationContract, VerificationTest, map_junit_candidates,
    prepare_evidence_record)
from support.artifacts import artifact_bytes
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import record_value, ref
from test_evidence_construction import inputs as evidence_inputs


ATTRIBUTES = {'classname': 'suite.A', 'name': 'accepts', 'file': 'tests/a.py'}
REPORT = b'''<testsuites tests="2000"><testsuite name="outer">
  <testcase classname="suite.A" name="accepts" file="tests/a.py"/>
  <testsuite name="inner">
    <testcase classname="suite.A" name="rejects" file="tests/a.py"><failure>bad</failure></testcase>
    <testcase classname="suite.B" name="broken" file="tests/b.py"><error>trace</error></testcase>
    <testcase classname="suite.B" name="later" file="tests/b.py"><skipped/></testcase>
  </testsuite>
</testsuite></testsuites>'''


def target(kind='test', **changes):
    cls = VerificationTest if kind == 'test' else VerificationContract
    return cls(artifact_bytes(record_value(kind, **changes)))


def mapping_value(fields=('name',), rows=None):
    return {'format_version': 'junit-mapping-v1', 'identity_fields': list(fields),
            'bindings': rows if rows is not None else [
                {'identity': {name: ATTRIBUTES[name] for name in fields},
                 'target_id': ref('TEST')}]}


def mapping(fields=('name',), rows=None):
    return JUnitMapping(artifact_bytes(mapping_value(fields, rows)))


def document(attributes=ATTRIBUTES, body=''):
    attrs = ' '.join(name + '=' + json.dumps(value, ensure_ascii=False)
                     for name, value in attributes.items())
    return JUnitDocument(('<testsuite><testcase ' + attrs + '>' + body +
                          '</testcase></testsuite>').encode())


@pytest.mark.parametrize('kind', ['test', 'verification'])
@pytest.mark.parametrize('body,outcome,result', [
    ('', 'passed', 'passed'), ('<failure>assertion</failure>', 'failure', 'failed'),
    ('<error>exception</error>', 'error', 'failed'), ('<skipped/>', 'skipped', 'skipped')])
def test_valid_identity_yields_the_exact_bound_target_and_measured_outcome(kind, body, outcome, result):
    item = target(kind)
    doc = document(body=body)
    chosen = mapping(('classname', 'name', 'file'), [
        {'identity': ATTRIBUTES, 'target_id': item.data['id']}])
    with no_write_attempts():
        resolved = map_junit_candidates(doc, chosen, targets=[item])
    data = resolved.data
    assert data['candidates'] == [{
        'testcase_index': 0, 'testcase_pointer': '/root/children/0',
        'identity': ATTRIBUTES,
        'target': {'artifact_id': item.data['id'], 'artifact_type': kind,
                   'revision': 1, 'source_sha256': sha256(item.source_bytes).hexdigest(),
                   'record_sha256': canonical_json_sha256(item.data)},
        'junit_outcome': outcome, 'result': result, 'origin': 'imported_junit'}]
    assert data['format_version'] == 'junit-candidates-v1'
    assert data['source'] == {'size': len(doc.source_bytes), 'sha256': doc.sha256}
    assert data['parser_profile'] == 'junit-core-v1'
    assert data['mapping_sha256'] == canonical_json_sha256(chosen.data)
    assert data['mapping_source_sha256'] == sha256(chosen.source_bytes).hexdigest()
    assert data['identity_fields'] == ['classname', 'name', 'file'] and data['testcase_count'] == 1
    for flag in ('test_code_executed', 'evidence_created', 'run_context_bound',
                 'project_targets_verified', 'full_verification_evaluated',
                 'write_authorized', 'approval_granted'):
        assert data[flag] is False
    for invented in ('produced_at', 'producer', 'environment', 'run_context',
                     'configuration_hash', 'subjects', 'verification_result'):
        assert invented not in data and invented not in data['candidates'][0]


@pytest.mark.parametrize('fields', [keys for n in (1, 2, 3)
    for keys in combinations(('classname', 'name', 'file'), n)])
def test_each_explicit_attribute_combination_is_usable(fields):
    result = map_junit_candidates(document(), mapping(fields), targets=[target()]).data
    assert result['candidates'][0]['identity'] == {key: ATTRIBUTES[key] for key in fields}
    assert result['candidates'][0]['result'] == 'passed'


def test_suite_traversal_retains_occurrences_and_does_not_use_reported_totals():
    row_targets = [target(), target('verification')]
    rows = [{'identity': {'name': name}, 'target_id': row_targets[n % 2].data['id']}
            for n, name in enumerate(('accepts', 'rejects', 'broken', 'later'))]
    data = map_junit_candidates(JUnitDocument(REPORT), mapping(rows=rows), targets=row_targets).data
    assert data['testcase_count'] == 4
    assert [c['testcase_index'] for c in data['candidates']] == [0, 1, 2, 3]
    assert [c['testcase_pointer'] for c in data['candidates']] == [
        '/root/children/0/children/0', '/root/children/0/children/1/children/0',
        '/root/children/0/children/1/children/1', '/root/children/0/children/1/children/2']
    assert [c['result'] for c in data['candidates']] == ['passed', 'failed', 'failed', 'skipped']
    assert [c['target']['artifact_id'] for c in data['candidates']] == [
        row_targets[0].data['id'], row_targets[1].data['id'],
        row_targets[0].data['id'], row_targets[1].data['id']]


def test_distinct_keys_to_one_target_are_not_aggregated_or_changed_to_success():
    raw = b'<testsuite><testcase name="first"/><testcase name="second"><failure/></testcase></testsuite>'
    rows = [{'identity': {'name': name}, 'target_id': ref('TEST')} for name in ('first', 'second')]
    data = map_junit_candidates(JUnitDocument(raw), mapping(rows=rows), targets=[target()]).data
    assert [(c['identity'], c['result']) for c in data['candidates']] == [
        ({'name': 'first'}, 'passed'), ({'name': 'second'}, 'failed')]


def test_identity_tuples_cannot_collide_through_separator_concatenation():
    raw = b'<testsuite><testcase classname="a:b" name="c"/><testcase classname="a" name="b:c"/></testsuite>'
    items = [target(), target(id=ref('TEST', '1'))]
    rows = [{'identity': {'classname': a, 'name': b}, 'target_id': items[n].data['id']}
            for n, (a, b) in enumerate((('a:b', 'c'), ('a', 'b:c')))]
    data = map_junit_candidates(JUnitDocument(raw), mapping(('classname', 'name'), rows), targets=items).data
    assert [c['target']['artifact_id'] for c in data['candidates']] == [ref('TEST'), ref('TEST', '1')]


@pytest.mark.parametrize('field,changed', [
    ('name', 'Accepts'), ('name', ' accepts'), ('name', 'accepts '),
    ('classname', 'suite.a'), ('file', './tests/a.py'), ('file', 'tests\\a.py')])
def test_matching_is_literal_without_case_space_or_path_normalization(field, changed):
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(document({**ATTRIBUTES, field: changed}),
                             mapping(ATTRIBUTES), targets=[target()])
    assert caught.value.reason == 'junit_testcase_unmapped'


def test_unicode_and_xml_character_references_are_matched_as_decoded_values():
    raw = '<testsuite><testcase name="caf&#233; 🙂"/></testsuite>'.encode()
    rows = [{'identity': {'name': 'café 🙂'}, 'target_id': ref('TEST')}]
    candidate, = map_junit_candidates(JUnitDocument(raw), mapping(rows=rows), targets=[target()]).data['candidates']
    assert candidate['identity'] == {'name': 'café 🙂'}
    rows[0]['identity']['name'] = 'cafe\u0301 🙂'
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(JUnitDocument(raw), mapping(rows=rows), targets=[target()])
    assert caught.value.reason == 'junit_testcase_unmapped'


@pytest.mark.parametrize('raw', [b'<testsuites/>', b'<testsuite tests="4" failures="0"/>'])
def test_empty_reports_do_not_synthesize_a_successful_measurement(raw):
    data = map_junit_candidates(JUnitDocument(raw), mapping(rows=[]), targets=[]).data
    assert data['testcase_count'] == 0 and data['candidates'] == []
    assert data['full_verification_evaluated'] is False and data['evidence_created'] is False


def test_outputs_and_opaque_extensions_cannot_add_core_testcases_or_outcomes():
    raw = b'''<testsuite xmlns:e="urn:extension" failures="100">
      <e:testcase name="unknown"><failure/></e:testcase>
      <properties><testcase name="invisible"/></properties>
      <system-err>error failure skipped</system-err>
      <testcase name="accepts" errors="100" skipped="100" time="not numeric">
        <system-out>failed</system-out><system-err>error</system-err>
        <e:failure/><extension><failure/></extension>
      </testcase></testsuite>'''
    data = map_junit_candidates(JUnitDocument(raw), mapping(), targets=[target()]).data
    assert data['testcase_count'] == 1
    assert data['candidates'][0]['result'] == 'passed'


@pytest.mark.parametrize('tag', ['failure', 'error', 'skipped'])
def test_repeated_nodes_of_one_outcome_kind_are_one_observation(tag):
    doc = document(body=('<' + tag + '/>') * 3)
    candidate, = map_junit_candidates(doc, mapping(), targets=[target()]).data['candidates']
    assert candidate['junit_outcome'] == tag
    assert candidate['result'] == ('skipped' if tag == 'skipped' else 'failed')


@pytest.mark.parametrize('body', ['<failure/><error/>', '<error/><skipped/>',
    '<skipped/><failure/>', '<failure/><error/><skipped/>'])
def test_mixed_outcomes_are_rejected_without_selecting_the_first_or_last(body):
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(document(body=body), mapping(), targets=[target()])
    assert caught.value.reason == 'conflicting_junit_testcase_outcomes'
    assert caught.value.pointer == '/root/children/0'


@pytest.mark.parametrize('field', ['classname', 'name', 'file'])
@pytest.mark.parametrize('absent', [True, False])
def test_required_identity_components_are_not_inherited_or_defaulted(field, absent):
    attributes = dict(ATTRIBUTES)
    if absent:
        del attributes[field]
    else:
        attributes[field] = ''
    doc = document(attributes)
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(doc, mapping(ATTRIBUTES), targets=[target()])
    assert caught.value.reason == 'junit_testcase_identity_missing'
    assert caught.value.pointer == '/root/children/0/attributes'


def test_unmapped_late_testcase_rejects_the_entire_initial_resolution():
    raw = b'<testsuite><testcase name="accepts"/><testcase name="SECRET"/></testsuite>'
    with no_write_attempts(), pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(JUnitDocument(raw), mapping(), targets=[target()])
    assert caught.value.reason == 'junit_testcase_unmapped'
    assert caught.value.pointer == '/root/children/1'
    assert caught.value.diagnostic()['code'] == 'SRV090' and caught.value.exit_code == 3
    assert 'SECRET' not in json.dumps(caught.value.diagnostic()) and 'SECRET' not in str(caught.value)


def test_repeated_selected_key_does_not_silently_merge_occurrences():
    raw = b'<testsuite><testcase name="accepts"/><testsuite><testcase name="accepts"/></testsuite></testsuite>'
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(JUnitDocument(raw), mapping(), targets=[target()])
    assert caught.value.reason == 'duplicate_junit_testcase_identity'
    assert caught.value.pointer == '/root/children/1/children/0'


def test_mapping_targets_must_exist_even_for_a_row_not_used_by_this_document():
    rows = mapping_value()['bindings'] + [{'identity': {'name': 'unused'}, 'target_id': ref('TEST', '1')}]
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(document(), mapping(rows=rows), targets=[target()])
    assert caught.value.reason == 'junit_mapping_target_not_found'
    assert caught.value.pointer == '/bindings/1/target_id'


@pytest.mark.parametrize('target_id', ['accepts', 'suite/test-case', 'tests/a.py', 'SR-TEST-9999'])
def test_titles_external_ids_and_paths_do_not_replace_target_identity(target_id):
    item = target(title='accepts')
    rows = [{'identity': {'name': 'accepts'}, 'target_id': target_id}]
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(document(), mapping(rows=rows), targets=[item])
    assert caught.value.reason == 'junit_mapping_target_not_found'


@pytest.mark.parametrize('bad', [None, {}, 'test'])
def test_target_inventory_is_explicit(bad):
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(document(), mapping(), targets=bad)
    assert caught.value.reason == 'typed_junit_targets_required'


def test_target_is_a_native_owned_test_or_contract_and_not_a_loose_dictionary():
    item = target()
    for wrong in (item.data, item.source_bytes, RecordArtifact(item.source_bytes)):
        with pytest.raises(JUnitMappingError) as caught:
            map_junit_candidates(document(), mapping(), targets=[wrong])
        assert caught.value.reason == 'typed_junit_target_required'
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(document(), mapping(), targets=[item, item])
    assert caught.value.reason == 'duplicate_junit_target'


@pytest.mark.parametrize('field,value,reason', [
    ('document', b'<testsuite/>', 'typed_junit_document_required'),
    ('document', {}, 'typed_junit_document_required'),
    ('mapping', b'{}', 'typed_junit_mapping_required'),
    ('mapping', {}, 'typed_junit_mapping_required')])
def test_resolution_requires_typed_documents_and_mappings(field, value, reason):
    arguments = {'document': document(), 'mapping': mapping(), 'targets': [target()]}
    arguments[field] = value
    with pytest.raises(JUnitMappingError) as caught:
        map_junit_candidates(**arguments)
    assert caught.value.reason == reason


@pytest.mark.parametrize('fields', [[], None, 'name', ['name', 'name'], ['unknown'],
    ['external_id'], ['name', 'external_id'], ['name', 1], [{}], [True]])
def test_identity_field_configuration_is_closed_and_never_guessed(fields):
    value = {**mapping_value(), 'identity_fields': fields}
    with pytest.raises(JUnitMappingError) as caught:
        JUnitMapping(artifact_bytes(value))
    assert caught.value.reason == 'invalid_junit_identity_fields'


@pytest.mark.parametrize('change,reason', [
    ({'format_version': 'junit-mapping-v2'}, 'unsupported_junit_mapping_version'),
    ({'format_version': 1}, 'unsupported_junit_mapping_version'),
    ({'extra': True}, 'invalid_junit_mapping_fields'),
    ({'bindings': {}}, 'invalid_junit_mapping_bindings'),
    ({'bindings': None}, 'invalid_junit_mapping_bindings')])
def test_unknown_mapping_contracts_do_not_fall_back_to_a_default(change, reason):
    with pytest.raises(JUnitMappingError) as caught:
        JUnitMapping(artifact_bytes({**mapping_value(), **change}))
    assert caught.value.reason == reason


@pytest.mark.parametrize('binding,reason', [
    (None, 'invalid_junit_mapping_binding'),
    ({'identity': {'name': 'a'}}, 'invalid_junit_mapping_binding'),
    ({'identity': {'name': 'a'}, 'target_id': ref('TEST'), 'pattern': '*'}, 'invalid_junit_mapping_binding'),
    ({'identity': {}, 'target_id': ref('TEST')}, 'invalid_junit_mapping_identity'),
    ({'identity': {'name': ''}, 'target_id': ref('TEST')}, 'invalid_junit_mapping_identity'),
    ({'identity': {'name': None}, 'target_id': ref('TEST')}, 'invalid_junit_mapping_identity'),
    ({'identity': {'name': 1}, 'target_id': ref('TEST')}, 'invalid_junit_mapping_identity'),
    ({'identity': {'name': 'a', 'file': 'b'}, 'target_id': ref('TEST')}, 'invalid_junit_mapping_identity'),
    ({'identity': {'name': 'a'}, 'target_id': ''}, 'invalid_junit_mapping_target'),
    ({'identity': {'name': 'a'}, 'target_id': None}, 'invalid_junit_mapping_target')])
def test_incomplete_or_executable_mapping_rows_are_rejected(binding, reason):
    with pytest.raises(JUnitMappingError) as caught:
        mapping(rows=[binding])
    assert caught.value.reason == reason and caught.value.pointer.startswith('/bindings/0')


@pytest.mark.parametrize('second_id', [ref('TEST'), ref('TEST', '1')])
def test_two_rows_for_one_identity_are_rejected_including_same_target(second_id):
    rows = [{'identity': {'name': 'accepts'}, 'target_id': identity}
            for identity in (ref('TEST'), second_id)]
    with pytest.raises(JUnitMappingError) as caught:
        mapping(rows=rows)
    assert caught.value.reason == 'duplicate_junit_mapping_identity'


@pytest.mark.parametrize('raw', ['{}', bytearray(b'{}'), memoryview(b'{}'), None])
def test_mapping_input_requires_immutable_bytes(raw):
    with pytest.raises(JUnitMappingError) as caught:
        JUnitMapping(raw)
    assert caught.value.reason == 'junit_mapping_bytes_required'


@pytest.mark.parametrize('raw,reason', [
    (b'{"bindings":[],"bindings":[]}', 'duplicate_key'),
    (b'{"value":NaN}', 'nonfinite_number'), (b'{} trailing', 'invalid_json'),
    (b'[]', 'object_required'), (b'{}' + bytes([255]), 'invalid_utf8')])
def test_mapping_uses_strict_native_json_syntax(raw, reason):
    with pytest.raises(ModelError) as caught:
        JUnitMapping(raw)
    assert caught.value.reason == reason


def test_mapping_byte_and_entry_limits_accept_the_boundary_and_reject_overflow():
    raw = mapping().source_bytes
    exact = raw + b' ' * (4 * 1024 * 1024 - len(raw))
    assert JUnitMapping(exact).data == mapping().data
    with pytest.raises(JUnitMappingError) as caught:
        JUnitMapping(exact + b' ')
    assert caught.value.reason == 'junit_mapping_byte_limit'
    rows = [{'identity': {'name': str(n)}, 'target_id': ref('TEST')} for n in range(10000)]
    assert len(mapping(rows=rows).data['bindings']) == 10000
    with pytest.raises(JUnitMappingError) as caught:
        mapping(rows=rows + [{'identity': {'name': 'overflow'}, 'target_id': ref('TEST')}])
    assert caught.value.reason == 'invalid_junit_mapping_bindings'


def test_mapping_and_result_ownership_cannot_change_the_original_inputs():
    row = mapping_value()
    chosen = JUnitMapping(artifact_bytes(row))
    item, doc = target(), document()
    result = map_junit_candidates(doc, chosen, targets=[item])
    original = result.data
    row['bindings'].clear(); chosen.data.clear(); item.data.clear(); doc.data.clear()
    result.data['candidates'][0]['target'].clear()
    result.data.clear()
    assert result.data == original
    assert result.sha256 == canonical_json_sha256(original)
    for obj in (chosen, result):
        with pytest.raises(FrozenInstanceError):
            obj._encoded = b'{}'
        with pytest.raises(TypeError):
            bool(obj)
    with pytest.raises(TypeError):
        JUnitCandidates(original)
    with pytest.raises(ModelError):
        RecordArtifact(canonical_json_bytes(original), expected_type='evidence')


def test_semantic_mapping_hash_is_distinct_from_original_byte_provenance():
    a = mapping()
    b = JUnitMapping(json.dumps(a.data, indent=1, sort_keys=True).encode())
    assert a.source_bytes != b.source_bytes and a.sha256 == b.sha256
    first = map_junit_candidates(document(), a, targets=[target()]).data
    second = map_junit_candidates(document(), b, targets=[target()]).data
    assert first['candidates'] == second['candidates']
    assert first['mapping_sha256'] == second['mapping_sha256']
    assert first['mapping_source_sha256'] != second['mapping_source_sha256']


def test_target_revision_and_content_are_bound_without_local_path_metadata():
    a, b = target(), target(revision=2, title='Updated target')
    chosen, doc = mapping(), document()
    first = map_junit_candidates(doc, chosen, targets=[a]).data['candidates'][0]['target']
    second = map_junit_candidates(doc, chosen, targets=[b]).data['candidates'][0]['target']
    assert first['artifact_id'] == second['artifact_id']
    assert second['revision'] == 2 and first['record_sha256'] != second['record_sha256']
    assert first['source_sha256'] != second['source_sha256']
    assert 'path' not in first and 'record' not in first


def test_cached_values_are_not_a_substitute_for_owned_source_bytes():
    chosen, doc = mapping(), document(body='<failure/>')
    expected = map_junit_candidates(doc, chosen, targets=[target()]).data
    object.__setattr__(chosen, '_encoded', b'{}')
    object.__setattr__(doc, '_encoded', b'{}')
    assert map_junit_candidates(doc, chosen, targets=[target()]).data == expected
    forged = target()
    object.__setattr__(forged, 'source_bytes', b'{}')
    with pytest.raises(ModelError):
        map_junit_candidates(doc, chosen, targets=[forged])


def test_inputs_remain_passive_even_when_they_contain_paths_and_code(monkeypatch):
    attrs = {**ATTRIBUTES, 'file': '/unavailable/do-not-read.py'}
    body = '<failure>__import__("os").system("do not run")</failure>'
    rows = [{'identity': attrs, 'target_id': ref('TEST')}]
    item = target()
    def forbidden(*args, **kwargs):
        raise AssertionError('Unexpected external input or execution')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('builtins.open', 'io.open', 'os.open', 'time.time',
                     'secrets.token_bytes', 'socket.getaddrinfo'):
            patch.setattr(name, forbidden)
        result = map_junit_candidates(document(attrs, body), mapping(ATTRIBUTES, rows),
                                      targets=[item])
    assert result.data['candidates'][0]['result'] == 'failed'


@pytest.mark.parametrize('with_test', [False, True])
def test_candidate_result_can_feed_existing_construction_only_with_explicit_run_inputs(with_test):
    subjects, contract, arguments = evidence_inputs(with_test=with_test)
    item = arguments['test'] if with_test else contract
    chosen = mapping(rows=[{'identity': {'name': 'accepts'}, 'target_id': item.data['id']}])
    value = map_junit_candidates(document(body='<error/>'), chosen, targets=[item]).data
    candidate, = value['candidates']
    with no_write_attempts():
        evidence = prepare_evidence_record(subjects, contract, **{
            **arguments, 'result': candidate['result'], 'origin': candidate['origin']})
    assert evidence.data['result'] == 'failed' and evidence.data['origin'] == 'imported_junit'
    assert evidence.data['run_context'] == arguments['run_context']
    assert candidate['target']['artifact_id'] in {s['artifact_id'] for s in evidence.data['subjects']}
    assert value['evidence_created'] is False and value['run_context_bound'] is False


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_mapping_and_error_contracts_work_in_isolated_distributions(tmp_path, mode):
    source = target().source_bytes
    chosen = mapping().source_bytes
    raw = document(body='<failure/>').source_bytes
    body = ('import json\nfrom specroad.verification import (JUnitDocument, JUnitMapping, '
            'VerificationTest, JUnitMappingError, map_junit_candidates)\n'
            't=VerificationTest(' + repr(source) + ')\n'
            'm=JUnitMapping(' + repr(chosen) + ')\n'
            'd=JUnitDocument(' + repr(raw) + ')\n'
            'value=map_junit_candidates(d,m,targets=[t]).data\n'
            'try: map_junit_candidates(d,m,targets=[])\n'
            'except JUnitMappingError as error: failure=error.diagnostic()\n'
            'else: raise AssertionError("Missing target accepted")\n'
            'print(json.dumps({"value":value,"failure":failure},sort_keys=True))\n')
    if mode == 'core':
        process = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'dist')
        prefix = 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n'
        process = run_python(['-I', '-S', '-B', '-c', prefix + body], tmp_path, capture=True)
    assert process.returncode == 0, process.stderr.decode()
    data = json.loads(process.stdout)
    assert data['value'] == map_junit_candidates(JUnitDocument(raw), JUnitMapping(chosen), targets=[target()]).data
    assert data['failure']['reason'] == 'junit_mapping_target_not_found'
    assert data['failure']['code'] == 'SRV090' and data['failure']['exit_code'] == 3
