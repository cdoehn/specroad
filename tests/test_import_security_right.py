"""14.n.R: hostile complete inputs cannot resolve, execute or partly write.

SR-FIX-IMPORT-SECURITY-RIGHT-v1 owns all bytes and project fixtures. These
probes exercise real adapters in fresh Core/PYZ processes, not external tools.
"""
from dataclasses import asdict
import json
import stat
import struct
from xml.sax.saxutils import quoteattr

import pytest

from specroad.model.canonical import canonical_json_bytes
from support.exchange_mappings import registry_value
from support.import_execution import project
from support.import_security import run_isolated
from support.import_security_cases import (READER_IMPORTS, XML_PARSERS, XML_ATTACKS,
    input_resources, parser_bounds, reader, wrapped, hostile_xml)
from support.read_only import inventory
from support.reqif_objects import LIMITS, document, one
from support.reqif_structure import xdocument
from test_work_archive import foreign_zip


R_IMPORTS = READER_IMPORTS + '''
import codecs
from zipfile import ZipFile
'''


def refusal(tmp_path, mode, raw, parser, reason, *, code=7, limits=None,
            paths=('document.reqif',), maximum=8*1024*1024, before_member_read=False):
    sandbox = tmp_path / 'sandbox'; sandbox.mkdir()
    project(sandbox / 'project')
    (sandbox / 'private.txt').write_bytes(b'owned unchanged secret')
    before = inventory(sandbox)
    body = R_IMPORTS + 'raw=' + repr(raw) + '\nbounds=' + repr(limits or parser_bounds(parser)) + '\n'
    body += '''
codec_requests = []
def foreign_codec(name):
    codec_requests.append(name)
    raise AssertionError('input selected a host codec')
codecs.register(foreign_codec)
'''
    if before_member_read:
        body += '''
def forbidden_member_read(*args, **kwargs):
    attempts.append('archive.member_read')
    raise ForbiddenEffect('unsafe metadata was used')
ZipFile.read = forbidden_member_read
'''
    body += "phase='parse'\ntry:\n    " + reader(parser, paths=paths, maximum=maximum) + '''
except ModelError as error:
    result = {'reason': error.reason, 'exit_code': error.exit_code}
    diagnostic = json.dumps(error.diagnostic())
    assert 'owned unchanged secret' not in diagnostic
else:
    raise AssertionError('hostile input was accepted')
assert attempts == [] and codec_requests == []
print(json.dumps({'error': result, 'attempts': attempts, 'codec_requests': codec_requests}))
'''
    process = run_isolated(body, sandbox, mode=mode)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {
        'error': {'reason': reason, 'exit_code': code}, 'attempts': [], 'codec_requests': []}
    # Includes artifacts, attachments, mappings, lock directories and receipts.
    assert inventory(sandbox) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('parser', XML_PARSERS)
@pytest.mark.parametrize('attack', XML_ATTACKS)
def test_xml_resolution_expansion_and_host_plugins_are_refused_in_all_adapters(tmp_path, mode, parser, attack):
    raw, reason, code = hostile_xml(parser, attack)
    refusal(tmp_path, mode, raw, parser, reason, code=code)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('parser', XML_PARSERS)
@pytest.mark.parametrize('limit,reason', [
    ('max_bytes', 'xml_byte_limit'), ('max_depth', 'xml_depth_limit'),
    ('max_elements', 'xml_element_limit'), ('max_text_chars', 'xml_text_limit'),
])
def test_xml_hard_bounds_refuse_complete_inputs_without_partial_project_state(tmp_path, mode, parser, limit, reason):
    xml = b'<testsuite><testcase name="too much text"/></testsuite>' if parser == 'junit' else one()
    bounds = {**parser_bounds(parser), limit: len(xml)-1 if limit == 'max_bytes' else 1}
    refusal(tmp_path, mode, wrapped(xml, parser), parser, reason, limits=bounds)


URI_ATTACKS = [
    ('opaque', 'src', 'https://supplier.invalid/image'),
    ('original', 'data', 'file:///private/image'),
    ('opaque', 'href', '%2e%2e/private'),
    ('original', 'href', '%252e%252e/private'),
    ('opaque', 'href', '//server/share'),
    ('original', 'href', 'C%3A/private'),
    ('opaque', 'href', 'image%3Fquery'),
    ('original', 'href', 'image%23fragment'),
]


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('parser', ['reqif-structure', 'reqifz'])
@pytest.mark.parametrize('surface,attribute,reference', URI_ATTACKS,
                         ids=['network', 'file', 'traversal', 'double-decode', 'unc', 'drive', 'query', 'fragment'])
def test_opaque_and_original_references_cannot_request_resolution(tmp_path, mode, parser, surface, attribute, reference):
    content = '<foreign xmlns:q="urn:attributes" q:' + attribute + '=' + quoteattr(reference) + '/>'
    xml = xdocument('<p>safe</p>', original=content) if surface == 'original' else document(
        extensions='<TOOL-EXTENSIONS><foreign xmlns="urn:foreign">' + content + '</foreign></TOOL-EXTENSIONS>')
    refusal(tmp_path, mode, wrapped(xml, parser), parser, 'reqif_attachment_reference_unsafe')


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('parser', ['reqif-structure', 'reqifz'])
@pytest.mark.parametrize('content,reason', [
    ('<script>touch NEVER_EXECUTED</script>', 'reqif_xhtml_active_content'),
    ('<foreign onclick="touch NEVER_EXECUTED"/>', 'reqif_xhtml_event_attribute'),
], ids=['script', 'event-handler'])
def test_active_original_content_is_not_a_passive_fallback(tmp_path, mode, parser, content, reason):
    refusal(tmp_path, mode, wrapped(xdocument('<p>safe</p>', original=content), parser), parser, reason)


ARCHIVE_ATTACKS = ['reserved-path', 'private-metadata', 'backslash', 'unc', 'drive',
                   'unicode-alias', 'parent-alias', 'directory', 'executable', 'fifo',
                   'nul-name', 'aggregate-bound', 'crc-late', 'xml-late']


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('attack', ARCHIVE_ATTACKS)
def test_archive_preflight_and_late_failures_never_extract_or_publish_prefixes(tmp_path, mode, attack):
    entries = [('document.reqif', one()), ('unused.bin', b'owned binary payload')]
    reason, code, pre_read = 'unsafe_archive_path', 7, True
    maximum, paths, change = 8*1024*1024, ['document.reqif'], None
    bad_names = {'reserved-path': 'dir/NUL.txt', 'private-metadata': '.GiT/config',
                 'backslash': 'a\\b', 'unc': '//server/share', 'drive': 'C:/private'}
    if attack in bad_names:
        entries.append((bad_names[attack], b'unused'))
    elif attack in ('unicode-alias', 'parent-alias'):
        entries += [('Straße', b'a'), ('STRASSE', b'b')] if attack == 'unicode-alias' else [('a/b', b'a'), ('A', b'b')]
        reason = 'unsafe_archive_path_collision'
    elif attack in ('directory', 'executable', 'fifo'):
        mode_bits = {'directory': stat.S_IFDIR | 0o755, 'executable': stat.S_IFREG | 0o755,
                     'fifo': stat.S_IFIFO | 0o600}[attack]
        change = lambda info: setattr(info, 'external_attr', mode_bits << 16) if info.filename == 'unused.bin' else None
        reason = 'unsafe_archive_entry'
    elif attack == 'aggregate-bound':
        maximum = sum(len(b) for _, b in entries)-1
        reason = 'archive_byte_limit'
    elif attack == 'xml-late':
        entries.append(('z.reqif', b'<!DOCTYPE REQ-IF SYSTEM "https://supplier.invalid/private"><REQ-IF/>'))
        paths.append('z.reqif'); pre_read = False
        reason = 'xml_dtd_or_entity_forbidden'
    raw = foreign_zip(sorted(entries, key=lambda e: e[0].encode()), change=change)
    if attack == 'nul-name':
        # Keep both real name byte extents; hide no bytes behind ZipInfo's NUL truncation.
        assert raw.count(b'unused.bin') == 2
        raw = raw.replace(b'unused.bin', b'un\x00sed.bin')
    elif attack == 'crc-late':
        start = raw.index(b'PK\x03\x04', 4)
        name_size, extra_size = struct.unpack_from('<HH', raw, start+26)
        altered = bytearray(raw); altered[start+30+name_size+extra_size] ^= 1; raw = bytes(altered)
        reason, code, pre_read = 'invalid_archive_container', 3, False
    refusal(tmp_path, mode, raw, 'reqifz', reason, code=code, paths=paths,
            maximum=maximum, before_member_read=pre_read)


CONVERTER_CASES = ['mapping-root', 'mapping-type', 'mapping-field', 'mapping-value',
                   'profile-root', 'profile-column', 'profile-codec', 'registry-entry']


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('case', CONVERTER_CASES)
def test_executable_control_fields_fail_at_every_declaration_boundary(tmp_path, mode, case):
    _, mapping, profile = input_resources('csv')
    parser = 'mapping' if case.startswith('mapping') else 'csv-profile' if case.startswith('profile') else 'registry'
    value = mapping.data if parser == 'mapping' else profile.data if parser == 'csv-profile' else registry_value(mapping)
    targets = {'mapping-root': lambda: value, 'mapping-type': lambda: value['types'][0],
               'mapping-field': lambda: value['fields'][0], 'profile-root': lambda: value,
               'profile-column': lambda: value['columns'][0], 'profile-codec': lambda: value['columns'][0]['codec'],
               'registry-entry': lambda: value['entries'][0]}
    if case == 'mapping-value':
        value['fields'][0]['value_map'] = [{'external_value': 'source', 'target_value': 'target'}]
        target = value['fields'][0]['value_map'][0]
    else:
        target = targets[case]()
    target['converter'] = {'command': 'touch NEVER_EXECUTED', 'url': 'https://supplier.invalid/converter'}
    refusal(tmp_path, mode, canonical_json_bytes(value), parser, 'mapping_unknown_field', code=3)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_declared_passive_values_and_registry_locations_are_not_code_or_io(tmp_path, mode):
    sandbox = tmp_path / 'sandbox'; sandbox.mkdir()
    project(sandbox / 'project'); before = inventory(sandbox)
    _, mapping, profile = input_resources('csv')
    literal = "__import__('os').system('touch NEVER_EXECUTED'); file:///private; https://supplier.invalid/data"
    value = mapping.data
    value['fields'][0]['value_map'] = [{'external_value': literal, 'target_value': literal}]
    value['extensions'] = {'security.passive': {'command': literal, 'path': '../../private'}}
    mapping_raw = canonical_json_bytes(value)
    # Rebind the data-only profile/registry to the actual changed mapping bytes.
    from specroad.mappings import ExchangeMapping
    mapping = ExchangeMapping(mapping_raw)
    profile_value = profile.data; profile_value['mapping'] = mapping.binding()
    registry = registry_value(mapping)
    registry['entries'][0]['data'] = {'source': literal, '__reduce__': ['os.system', literal]}
    body = R_IMPORTS + 'mapping_raw=' + repr(mapping_raw) + '\n'
    body += 'profile_raw=' + repr(canonical_json_bytes(profile_value)) + '\n'
    body += 'registry_raw=' + repr(canonical_json_bytes(registry)) + '\nliteral=' + repr(literal) + '\n'
    body += r'''
phase = 'parse'
mapping = ExchangeMapping(mapping_raw)
profile = CSVProfile(profile_raw)
registry = ExternalIdentityRegistry(registry_raw)
raw = ('ID,Text\r\nexternal-1,' + literal + '\r\n').encode()
row, = select_csv_profile([profile, mapping], key=profile.key, expected_sha256=profile.sha256).decode(raw).records
mapped = select_mapping([mapping], key=mapping.key, expected_sha256=mapping.sha256).artifact(row['external_type'], row['fields'])
assert mapped['artifact']['statement'] == literal
assert registry.data['entries'][0]['data']['source'] == literal
assert registry.source_bytes == registry_raw and mapping.source_bytes == mapping_raw
assert attempts == []
print(json.dumps({'statement': mapped['artifact']['statement'], 'attempts': attempts}))
'''
    process = run_isolated(body, sandbox, mode=mode)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {'statement': literal, 'attempts': []}
    assert inventory(sandbox) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('parser', XML_PARSERS)
def test_literal_xml_lookalikes_and_exact_byte_bound_remain_usable(tmp_path, mode, parser):
    sandbox = tmp_path / 'sandbox'; sandbox.mkdir()
    literal = '<!DOCTYPE inactive> & https://supplier.invalid/data'
    if parser == 'junit':
        xml = ('<testsuite><system-out><![CDATA[' + literal + ']]></system-out></testsuite>').encode()
        oracle = "value.data['root']['children'][0]['text']"
    else:
        xml = one(literal=literal)
        oracle = "value.project_object('object')['fields']['field']"
    raw = wrapped(xml, parser)
    bounds = {**parser_bounds(parser), 'max_bytes': len(xml)}
    body = R_IMPORTS + 'raw=' + repr(raw) + '\nbounds=' + repr(bounds) + "\nphase='parse'\n"
    body += 'value=' + reader(parser, maximum=len(xml)) + '\n'
    if parser == 'reqifz':
        body += "value=decode_reqif_structure(value.files['document.reqif'],limits=ReqIFLimits(**bounds))\n"
    body += 'assert value.source_bytes==' + repr(xml) + '\n'
    body += 'assert ' + oracle + '==' + repr(literal) + '\nassert attempts==[]\nprint(json.dumps(attempts))\n'
    before = inventory(sandbox)
    process = run_isolated(body, sandbox, mode=mode)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == [] and inventory(sandbox) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_archive_references_stay_local_and_unused_payloads_are_not_recursively_executed(tmp_path, mode):
    sandbox = tmp_path / 'sandbox'; sandbox.mkdir()
    files = {'docs/a.reqif': xdocument('<a href="b.reqif">local</a><a href="image%20one.bin">image</a>'),
             'docs/b.reqif': xdocument('<a href="a.reqif">cycle stays passive</a>'),
             'docs/image one.bin': b'\x00\xffowned', 'unused.reqif': b'<!DOCTYPE evil>not selected',
             'unused.zip': b'PK not recursively decoded'}
    raw = foreign_zip(sorted(files.items()))
    body = R_IMPORTS + 'raw=' + repr(raw) + '\nbounds=' + repr(asdict(LIMITS)) + "\nphase='parse'\n"
    body += 'value=' + reader('reqifz', paths=['docs/a.reqif', 'docs/b.reqif'], maximum=sum(map(len, files.values()))) + '\n'
    body += 'assert value.files==' + repr(files) + '\n'
    body += "assert len(value.manifest['references'])==3\nassert attempts==[]\nprint(json.dumps(attempts))\n"
    before = inventory(sandbox)
    process = run_isolated(body, sandbox, mode=mode)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == [] and inventory(sandbox) == before
