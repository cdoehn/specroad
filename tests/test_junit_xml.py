"""JUnit is bounded passive input, never a test runner or write authority."""
from dataclasses import FrozenInstanceError, fields
from hashlib import sha256
import json

import pytest

from specroad.verification import JUnitDocument, JUnitLimits, XmlImportError
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts


REPORT = b'''<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="all" tests="999">
  <testsuite name="suite" timestamp="2026-10-20T06:30:00Z" tests="4"
             failures="1" errors="1" skipped="1" time="001.250">
    <testcase classname="pkg.A" name="ok" file="../passive.py" line="007" time="0.1"/>
    <testcase classname="pkg.A" name="bad"><failure>assert x &lt; 2</failure></testcase>
    <testcase name="broken"><error><![CDATA[trace <not-code>]]></error></testcase>
    <testcase name="later"><skipped>not available</skipped></testcase>
    <system-out>ordinary &amp; literal &#x1F642;</system-out>
    <system-err>stderr</system-err>
  </testsuite>
</testsuites>'''


def test_document_reads_the_complete_profile_without_inventing_results():
    with no_write_attempts():
        document = JUnitDocument(REPORT)
    value = document.data
    assert document.source_bytes == REPORT and document.sha256 == sha256(REPORT).hexdigest()
    assert value['source'] == {'size': len(REPORT), 'sha256': document.sha256}
    assert value['format_version'] == 'junit-core-v1'
    assert value['test_code_executed'] is False and value['evidence_created'] is False
    assert value['ignored_elements'] == value['ignored_attributes'] == 0
    root = value['root']
    assert root['tag'] == 'testsuites' and root['attributes'] == {'name': 'all', 'tests': '999'}
    suite, = root['children']
    assert suite['attributes'] == {'name': 'suite', 'timestamp': '2026-10-20T06:30:00Z',
        'tests': '4', 'failures': '1', 'errors': '1', 'skipped': '1', 'time': '001.250'}
    cases = suite['children'][:4]
    assert cases[0] == {'tag': 'testcase', 'attributes': {'classname': 'pkg.A', 'name': 'ok',
        'file': '../passive.py', 'line': '007', 'time': '0.1'}, 'text': '', 'children': []}
    for case, tag, text in zip(cases[1:], ('failure', 'error', 'skipped'),
                              ('assert x < 2', 'trace <not-code>', 'not available')):
        assert case['children'] == [{'tag': tag, 'attributes': {}, 'text': text, 'children': []}]
    assert [(n['tag'], n['text']) for n in suite['children'][4:]] == [
        ('system-out', 'ordinary & literal 🙂'), ('system-err', 'stderr')]


@pytest.mark.parametrize('raw', [b'<testsuites/>', b'<testsuite/>',
    b'<testsuites><testsuite><testsuite><testcase/></testsuite></testsuite></testsuites>'])
def test_empty_and_nested_suites_are_values_not_success(raw):
    doc = JUnitDocument(raw)
    assert doc.data['source']['size'] == len(raw)
    with pytest.raises(TypeError):
        bool(doc)


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-16', 'iso-8859-1', 'ascii'])
def test_xml_encodings_are_decoded_by_the_parser_and_original_bytes_are_retained(encoding):
    raw = ('<?xml version="1.0" encoding="' + encoding + '"?>'
           '<testsuite><testcase name="caf&#233;"/></testsuite>').encode(encoding)
    doc = JUnitDocument(raw)
    assert doc.data['root']['children'][0]['attributes']['name'] == 'café'
    assert doc.source_bytes == raw


def test_unknown_extensions_cannot_smuggle_normative_testcases():
    raw = b'''<testsuite custom="retained only in source" xmlns:e="urn:extension">
      <properties><testcase name="not-a-case"/></properties>
      <e:testcase name="also-not-a-case"/>
      <testcase name="actual" custom="ignored"><e:failure>not a failure</e:failure></testcase>
    </testsuite>'''
    doc = JUnitDocument(raw)
    assert doc.data['ignored_elements'] == 4
    assert doc.data['ignored_attributes'] == 2
    assert doc.data['root']['children'] == [
        {'tag': 'testcase', 'attributes': {'name': 'actual'}, 'text': '', 'children': []}]
    assert doc.source_bytes == raw


def test_each_read_returns_owned_data_and_the_document_is_immutable():
    doc = JUnitDocument(REPORT)
    changed = doc.data
    changed['root']['children'].clear()
    changed['source']['sha256'] = '0' * 64
    assert len(doc.data['root']['children']) == 1
    assert doc.sha256 == sha256(REPORT).hexdigest()
    with pytest.raises(FrozenInstanceError):
        doc.source_bytes = b'<testsuite/>'


def test_all_reported_counts_outcomes_and_source_paths_remain_passive(monkeypatch):
    raw = b'''<testsuite tests="not a number"><testcase name="run-me" file="/private/test.py">
      <failure>exit(0)</failure><error>still failed</error><skipped/>
      <system-out>__import__('os').system('not-executed')</system-out>
    </testcase></testsuite>'''
    def forbidden(*args, **kwargs):
        raise AssertionError('No reader, process, network or clock may be consulted')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('builtins.open', 'io.open', 'os.open', 'time.time'):
            patch.setattr(name, forbidden)
        result = JUnitDocument(raw).data
    assert result['root']['attributes']['tests'] == 'not a number'
    case, = result['root']['children']
    assert case['attributes']['file'] == '/private/test.py'
    assert [n['tag'] for n in case['children']] == ['failure', 'error', 'skipped', 'system-out']
    assert 'result' not in case and result['evidence_created'] is False


@pytest.mark.parametrize('raw', [b'', b'<testsuite>', b'<testsuite/><testsuite/>',
    b'<testsuite name="a" name="b"/>', b'<testsuite>&undefined;</testsuite>',
    b'<testsuite>\x00</testsuite>', b'<testsuite>\xff</testsuite>'])
def test_malformed_xml_has_a_machine_readable_error_and_no_partial_result(raw):
    with no_write_attempts(), pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw)
    error = caught.value
    assert error.reason == 'invalid_xml' and error.exit_code == 3
    assert error.diagnostic()['code'] == 'SRV083'
    assert type(error.line) is int and type(error.column) is int
    assert type(error.position) is int


@pytest.mark.parametrize('raw,reason', [
    (b'<testcase/>', 'junit_root_required'),
    (b'<testsuite xmlns="urn:other"/>', 'junit_root_required'),
    (b'<testsuites><testcase/></testsuites>', 'junit_element_placement'),
    (b'<testsuite><failure/></testsuite>', 'junit_element_placement'),
    (b'<testsuite><testcase><testsuite/></testcase></testsuite>', 'junit_element_placement'),
    (b'<?xml version="1.1"?><testsuite/>', 'xml_version_not_supported'),
])
def test_unsupported_profile_structure_is_not_reinterpreted(raw, reason):
    with pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw)
    assert (caught.value.reason, caught.value.exit_code) == (reason, 3)


@pytest.mark.parametrize('raw', [
    b'<!DOCTYPE testsuite><testsuite/>',
    b'<!DOCTYPE testsuite SYSTEM "file:///private/input"><testsuite/>',
    b'<!DOCTYPE testsuite SYSTEM "https://example.invalid/external.dtd"><testsuite/>',
    b'<!DOCTYPE testsuite [<!ENTITY x "secret">]><testsuite>&x;</testsuite>',
    b'<!DOCTYPE testsuite [<!ENTITY % x SYSTEM "file:///private/input">%x;]><testsuite/>',
    b'<!DOCTYPE testsuite [<!ENTITY a "xx"><!ENTITY b "&a;&a;&a;">]><testsuite>&b;</testsuite>',
])
@pytest.mark.parametrize('encoding', ['utf-8', 'utf-16'])
def test_dtd_and_entities_are_rejected_before_resolution(raw, encoding, monkeypatch):
    payload = raw.decode().encode(encoding)
    def forbidden(*args, **kwargs):
        raise AssertionError('An XML reference attempted external I/O')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('builtins.open', 'io.open', 'os.open'):
            patch.setattr(name, forbidden)
        with pytest.raises(XmlImportError) as caught:
            JUnitDocument(payload)
    assert caught.value.reason == 'xml_dtd_or_entity_forbidden'
    assert caught.value.exit_code == 7
    assert 'private' not in str(caught.value) and 'secret' not in str(caught.value)


@pytest.mark.parametrize('raw', [
    b'<testsuite xmlns:x="http://www.w3.org/2001/XMLSchema-instance" x:schemaLocation="urn:a https://example.invalid/a.xsd"/>',
    b'<testsuite xmlns:x="http://www.w3.org/2001/XMLSchema-instance" x:noNamespaceSchemaLocation="file:///private/schema"/>',
    b'<testsuite xmlns:x="http://www.w3.org/2001/XInclude"><x:include href="file:///private/input"/></testsuite>',
    b'<testsuite xmlns:x="http://www.w3.org/2001/XMLSchema"><x:import schemaLocation="https://example.invalid"/></testsuite>',
])
def test_external_schema_and_inclusion_requests_are_forbidden_even_under_extensions(raw):
    with no_write_attempts(), pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw)
    assert caught.value.reason == 'xml_external_reference_forbidden' and caught.value.exit_code == 7


def test_processing_instructions_cannot_enable_a_stylesheet_or_other_processor():
    with no_write_attempts(), pytest.raises(XmlImportError) as caught:
        JUnitDocument(b'<?xml-stylesheet href="https://example.invalid/code"?><testsuite/>')
    assert (caught.value.reason, caught.value.exit_code) == ('xml_processing_instruction_forbidden', 7)


@pytest.mark.parametrize('field,boundary,too_large,limit,reason', [
    ('max_bytes', b'<testsuite/>', b'<testsuite/> ', 12, 'xml_byte_limit'),
    ('max_depth', b'<testsuite><testcase/></testsuite>',
     b'<testsuite><testcase><failure/></testcase></testsuite>', 2, 'xml_depth_limit'),
    ('max_elements', b'<testsuite><testcase/></testsuite>',
     b'<testsuite><testcase/><testcase/></testsuite>', 2, 'xml_element_limit'),
    ('max_text_chars', b'<testsuite><system-out>four</system-out></testsuite>',
     b'<testsuite><system-out>five!</system-out></testsuite>', 4, 'xml_text_limit'),
    ('max_attributes_per_element', b'<testsuite name="a"/>',
     b'<testsuite name="a" tests="1"/>', 1, 'xml_attribute_limit'),
    ('max_name_chars', b'<testsuite/>', b'<testsuite><extensionlong/></testsuite>', 9, 'xml_name_limit'),
])
def test_each_document_limit_accepts_the_boundary_and_rejects_the_next_input(field, boundary, too_large, limit, reason):
    limits = JUnitLimits(**{field: limit})
    assert JUnitDocument(boundary, limits=limits).source_bytes == boundary
    with no_write_attempts(), pytest.raises(XmlImportError) as caught:
        JUnitDocument(too_large, limits=limits)
    assert (caught.value.reason, caught.value.exit_code) == (reason, 7)


@pytest.mark.parametrize('body', ['<extension>abcde</extension>', '<extension long="abcde"/>',
                                '<!--abcde-->', '<extension xmlns:x="abcde"/>'])
def test_ignored_content_also_consumes_the_text_limit(body):
    with pytest.raises(XmlImportError) as caught:
        JUnitDocument(('<testsuite>' + body + '</testsuite>').encode(),
                      limits=JUnitLimits(max_text_chars=4))
    assert caught.value.reason == 'xml_text_limit' and caught.value.exit_code == 7


def test_depth_and_element_limits_cover_ignored_subtrees_too():
    raw = b'<testsuite><unknown><testcase/></unknown></testsuite>'
    for limits, reason in ((JUnitLimits(max_depth=2), 'xml_depth_limit'),
                           (JUnitLimits(max_elements=2), 'xml_element_limit')):
        with pytest.raises(XmlImportError) as caught:
            JUnitDocument(raw, limits=limits)
        assert caught.value.reason == reason and caught.value.exit_code == 7


@pytest.mark.parametrize('field', [field.name for field in fields(JUnitLimits)])
@pytest.mark.parametrize('value', [0, -1, True, '2', 1.5, None])
def test_limits_must_be_positive_integers(field, value):
    with pytest.raises(XmlImportError) as caught:
        JUnitLimits(**{field: value})
    assert (caught.value.reason, caught.value.exit_code) == ('invalid_xml_limits', 2)


@pytest.mark.parametrize('field', list(fields(JUnitLimits)), ids=lambda field: field.name)
def test_hard_ceilings_cannot_be_disabled_or_raised(field):
    with pytest.raises(XmlImportError) as caught:
        JUnitLimits(**{field.name: field.default + 1})
    assert caught.value.exit_code == 2


@pytest.mark.parametrize('raw', ['<testsuite/>', bytearray(b'<testsuite/>'), memoryview(b'<testsuite/>'), None])
def test_only_owned_immutable_bytes_are_accepted(raw):
    with pytest.raises(XmlImportError) as caught:
        JUnitDocument(raw)
    assert caught.value.reason == 'xml_bytes_required'


def test_limits_are_typed_and_revalidated_at_the_read_boundary():
    with pytest.raises(XmlImportError) as caught:
        JUnitDocument(b'<testsuite/>', limits={})
    assert caught.value.reason == 'typed_xml_limits_required'
    forged = JUnitLimits()
    object.__setattr__(forged, 'max_bytes', 100000000)
    with pytest.raises(XmlImportError) as caught:
        JUnitDocument(b'<testsuite/>', limits=forged)
    assert caught.value.reason == 'invalid_xml_limits'


def test_default_depth_and_element_boundaries_are_usable():
    doc = JUnitDocument(b'<testsuite>' * 64 + b'</testsuite>' * 64)
    node = doc.data['root']
    for _ in range(63):
        node, = node['children']
    assert node['children'] == []
    raw = b'<testsuite>' + b'<testcase/>' * 9999 + b'</testsuite>'
    assert len(JUnitDocument(raw).data['root']['children']) == 9999


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_passive_parser_and_security_failure_work_in_isolated_distribution(tmp_path, mode):
    body = ('import json\nfrom specroad.verification import JUnitDocument, XmlImportError\n'
            'value=JUnitDocument(' + repr(REPORT) + ').data\n'
            'try: JUnitDocument(b"<!DOCTYPE testsuite><testsuite/>")\n'
            'except XmlImportError as error: reason=error.reason\n'
            'else: raise AssertionError("DTD accepted")\n'
            'print(json.dumps({"value":value,"reason":reason},sort_keys=True))\n')
    if mode == 'core':
        process = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'dist')
        prefix = 'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n'
        process = run_python(['-I', '-S', '-B', '-c', prefix + body], tmp_path, capture=True)
    assert process.returncode == 0, process.stderr.decode()
    assert json.loads(process.stdout) == {'value': JUnitDocument(REPORT).data,
                                         'reason': 'xml_dtd_or_entity_forbidden'}
