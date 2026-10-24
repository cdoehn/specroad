"""14.k.R: hostile real ZIP/XML bytes, exact bounds and passive ownership."""
from dataclasses import asdict, replace
from hashlib import sha256
from io import BytesIO
import stat
import struct
from unittest.mock import patch
from xml.sax.saxutils import quoteattr
from zipfile import ZipFile

import pytest

from specroad.exchange import ReqIFError
from support.read_only import inventory, no_write_attempts
from support.reqif_objects import LIMITS, document, one
from support.reqif_structure import xdocument
from test_reqifz import independent, read, write
from test_work_archive import foreign_zip


def source_files():
    return {'document.reqif': one(), 'unused.bin': b'unused complete bytes'}


def offsets(raw):
    """Locate records in independently generated fixtures, not product helpers."""
    end = raw.rindex(b'PK\x05\x06')
    cursor = struct.unpack_from('<I', raw, end + 16)[0]
    central = {}
    with ZipFile(BytesIO(raw)) as archive:
        local = {info.filename: info.header_offset for info in archive.infolist()}
        for info in archive.infolist():
            assert raw[cursor:cursor+4] == b'PK\x01\x02'
            central[info.filename] = cursor
            lengths = struct.unpack_from('<3H', raw, cursor + 28)
            cursor += 46 + sum(lengths)
    return local, central, end


def refuse(raw, code, *, pre_read=False):
    with no_write_attempts(), pytest.raises(ReqIFError) as caught:
        if pre_read:
            with patch.object(ZipFile, 'read', side_effect=AssertionError('premature payload read')):
                read(raw)
        else:
            read(raw)
    assert caught.value.exit_code == code


@pytest.mark.parametrize('offset,value', [
    (0, 0), (4, 21), (6, 1), (6, 8), (6, 0x800), (8, 8),
    (10, 1), (12, 34), (14, 123), (18, 1), (22, 1), (26, 1), (28, 1),
], ids=['signature','version','encrypted','descriptor','utf8','method',
        'time','date','crc','compressed-size','size','name-size','extra-size'])
def test_local_header_of_unused_member_must_match_before_any_payload_read(offset, value):
    raw = independent(source_files()); local, _, _ = offsets(raw)
    altered = bytearray(raw)
    width = '<I' if offset in (14, 18, 22) else '<H'
    struct.pack_into(width, altered, local['unused.bin'] + offset, value)
    refuse(bytes(altered), 3, pre_read=True)


@pytest.mark.parametrize('offset,value,code', [
    (4, 21, 3), (6, 21, 3), (8, 1, 3), (8, 8, 3), (8, 0x800, 3), (10, 8, 3),
    (12, 1, 3), (14, 34, 3), (16, 123, 3), (20, 1, 3), (24, 1, 3),
    (34, 1, 3), (36, 1, 3), (38, (stat.S_IFLNK | 0o777) << 16, 7),
    (42, 0, 3),
], ids=['creator','version','encrypted','descriptor','utf8','method','time','date',
        'crc','compressed-size','size','volume','internal-mode','symlink','overlap'])
def test_central_header_of_unused_member_is_bound_before_reading(offset, value, code):
    raw = independent(source_files()); _, central, _ = offsets(raw)
    altered = bytearray(raw)
    width = '<I' if offset in (16, 20, 24, 38, 42) else '<H'
    struct.pack_into(width, altered, central['unused.bin'] + offset, value)
    refuse(bytes(altered), code, pre_read=True)


@pytest.mark.parametrize('offset,value', [(4, 1), (6, 1), (8, 1), (10, 1), (12, 1), (16, 1), (20, 1)],
                         ids=['disk','central-disk','disk-count','count','size','offset','comment-size'])
def test_end_record_must_describe_exactly_the_real_single_disk_archive(offset, value):
    raw = independent(source_files()); _, _, end = offsets(raw)
    altered = bytearray(raw)
    struct.pack_into('<I' if offset in (12, 16) else '<H', altered, end + offset, value)
    refuse(bytes(altered), 3, pre_read=True)


@pytest.mark.parametrize('size', [0, 1, 0x7fffffff, 0xfffffffe], ids=['zero','short','huge','near-zip32'])
def test_matching_forged_sizes_do_not_hide_gaps_or_trigger_declared_allocations(size):
    raw = independent(source_files()); local, central, _ = offsets(raw)
    altered = bytearray(raw)
    for offset in (18, 22): struct.pack_into('<I', altered, local['unused.bin']+offset, size)
    for offset in (20, 24): struct.pack_into('<I', altered, central['unused.bin']+offset, size)
    refuse(bytes(altered), 3, pre_read=True)


@pytest.mark.parametrize('kind', ['prefix','tail','local-gap','reversed','central-name','local-name','truncated'])
def test_unused_bytes_order_and_member_names_cannot_be_repaired_or_ignored(kind):
    files = source_files(); raw = independent(files); local, central, _ = offsets(raw)
    if kind == 'prefix': raw = b'MZ executable prefix' + raw
    elif kind == 'tail': raw += b'unbound trailer'
    elif kind == 'local-gap':
        # Both index and local offsets remain consistent with the new gap.
        at = local['unused.bin']; altered = bytearray(raw[:at] + b'!' + raw[at:])
        for name, offset in local.items():
            struct.pack_into('<I', altered, central[name]+1+42, offset + (offset >= at))
        end = raw.rindex(b'PK\x05\x06')+1
        struct.pack_into('<I', altered, end+16, min(central.values())+1)
        raw = bytes(altered)
    elif kind == 'reversed': raw = foreign_zip(list(reversed(list(files.items()))))
    elif kind in ('central-name','local-name'):
        altered = bytearray(raw)
        at = central['unused.bin']+46 if kind == 'central-name' else local['unused.bin']+30
        altered[at] = ord('v'); raw = bytes(altered)
    else: raw = raw[:-1]
    refuse(raw, 3, pre_read=True)


@pytest.mark.parametrize('which', ['selected','unused','both-crcs'])
def test_actual_crc_is_checked_for_every_member_even_with_consistent_headers(which):
    raw = independent(source_files()); local, central, _ = offsets(raw)
    name = 'document.reqif' if which == 'selected' else 'unused.bin'
    altered = bytearray(raw)
    if which == 'both-crcs':
        for at in (local[name]+14, central[name]+16):
            struct.pack_into('<I', altered, at, 0)
    else:
        altered[local[name]+30+len(name)] ^= 1
    refuse(bytes(altered), 3)


@pytest.mark.parametrize('name', ['dir/', '.GiT/config', '.PATCHHARBOR/id', 'COM1.txt', 'a/LPT9',
    'a/trailing ', 'a/PRN.ext', 'a?b', 'a<b', 'a\x7fb', '//host/share', 'C:/drive'])
def test_unsafe_unreferenced_member_paths_fail_before_reading(name):
    refuse(independent({**source_files(), name: b'passive'}), 7, pre_read=True)


@pytest.mark.parametrize('other', [
    {'Straße': b'a', 'STRASSE': b'b'}, {'Dir/a': b'a', 'dir/b': b'b'},
    {'a/b': b'a', 'A': b'b'}, {'a/b/c': b'a', 'a/B': b'b'},
], ids=['unicode-casefold','directory-alias','file-parent','nested-file-parent'])
def test_casefold_and_parent_collisions_cover_the_whole_portable_target_set(other):
    files = {**source_files(), **other}
    refuse(independent(files), 7, pre_read=True)
    with no_write_attempts(), pytest.raises(ReqIFError) as caught: write(files)
    assert caught.value.exit_code == 7


def test_duplicate_unused_member_is_unsafe_before_any_payload_read():
    files = list(source_files().items())
    with pytest.warns(UserWarning): raw = foreign_zip([*files, files[-1]])
    refuse(raw, 7, pre_read=True)


@pytest.mark.parametrize('kind', ['nul','bad-utf8'], ids=['no-NUL-truncation','strict-UTF8'])
def test_raw_member_spelling_cannot_be_hidden_by_zip_filename_decoding(kind):
    raw = independent(source_files()); local, central, _ = offsets(raw); altered = bytearray(raw)
    for at in (local['unused.bin']+30, central['unused.bin']+46): altered[at+1] = 0 if kind=='nul' else 0xff
    if kind == 'bad-utf8':
        struct.pack_into('<H', altered, local['unused.bin']+6, 0x800)
        struct.pack_into('<H', altered, central['unused.bin']+8, 0x800)
    refuse(bytes(altered), 7, pre_read=True)


@pytest.mark.parametrize('mode', [stat.S_IFCHR | 0o600, stat.S_IFBLK | 0o600, stat.S_IFSOCK | 0o600,
    stat.S_IFREG | 0o755, stat.S_IFREG | 0o4644, stat.S_IFREG | 0o644 | stat.S_ISGID],
    ids=['device','block-device','socket','executable','setuid','setgid'])
def test_special_or_noncanonical_permissions_never_materialize(mode, tmp_path):
    raw = independent(source_files(), change=lambda i: setattr(i, 'external_attr', mode << 16))
    before = inventory(tmp_path); refuse(raw, 7, pre_read=True)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['extra','entry-comment','archive-comment','timestamp','creator','method'])
def test_optional_zip_features_do_not_change_the_shared_transport_profile(kind):
    def change(info):
        if kind == 'extra': info.extra = b'\x01\xca\0\0'
        elif kind == 'entry-comment': info.comment = b'comment'
        elif kind == 'timestamp': info.date_time = (2026, 1, 1, 0, 0, 0)
        elif kind == 'creator': info.create_system = 0
        elif kind == 'method': info.compress_type = 8
    raw = independent(source_files(), change=change, comment=b'comment' if kind=='archive-comment' else b'')
    refuse(raw, 3, pre_read=True)


@pytest.mark.parametrize('reference', ['../x', '%2e%2e/x', 'a/../x', '%252e%252e/x', '%2Fabsolute',
    '//host/x', 'C%3A/x', 'file:///x', 'https://example.invalid/x', '%5cserver', 'a//b',
    'a/%2e/b', 'p#part', 'p?query', 'p%23part', 'p%3Fquery', 'p%', 'p%Q0', '%ff', '%c0%af',
    'p%00x', 'p%7fx', 'a/NUL.txt', '.git/config', '.patchharbor/id', 'p%25x'])
def test_unsafe_uri_decoding_is_never_loss_or_fallback(reference):
    xml = xdocument('<a href='+quoteattr(reference)+'>source</a>')
    files = {'document.reqif': xml, 'x': b'no fallback'}
    with no_write_attempts():
        for call in (lambda: write(files), lambda: read(independent(files))):
            with pytest.raises(ReqIFError) as caught: call()
            assert caught.value.exit_code == 7


@pytest.mark.parametrize('attribute', ['href','src','data','action','formaction','codebase','archive','poster'])
def test_namespaced_opaque_uri_attributes_are_checked_and_bound(attribute):
    xml = document(extensions='<TOOL-EXTENSIONS><f xmlns="urn:foreign" xmlns:q="urn:attributes" q:'
        + attribute + '="asset.bin"/></TOOL-EXTENSIONS>')
    files = {'docs/source': xml, 'docs/asset.bin': b'bound'}
    with no_write_attempts():
        value = read(write(files, ['docs/source']), ['docs/source'])
        assert value.manifest['references'] == [
            {'document_path':'docs/source','reference':'asset.bin','member_path':'docs/asset.bin'}]
        del files['docs/asset.bin']
        for call in (lambda: write(files, ['docs/source']), lambda: read(independent(files), ['docs/source'])):
            with pytest.raises(ReqIFError) as caught: call()
            assert caught.value.exit_code == 6


def test_original_fallback_and_passive_extensions_bind_independently_with_original_spellings():
    xml = xdocument('<p><object data="a%20b.bin" type="application/octet-stream">'
                    '<a href="a b.bin">fallback</a></object></p>',
                    original='<a href="a&#32;b.bin">original</a>')
    # Unsupported passive XHTML is transportable; native completeness is separate.
    files = {'nested/source': xml, 'nested/a b.bin': b'owned'}
    with no_write_attempts():
        value = read(write(files, ['nested/source']), ['nested/source'])
    assert value.files == files
    assert value.manifest['references'] == [
        {'document_path':'nested/source','reference':r,'member_path':'nested/a b.bin'}
        for r in ('a b.bin','a%20b.bin')]


@pytest.mark.parametrize('surface', ['original','opaque'])
@pytest.mark.parametrize('body', ['<script/>', '<f onclick="x"/>', '<f href="%252e%252e/x"/>',
    '<f src="https://example.invalid/x"/>'], ids=['active','event','double-decode','network'])
def test_security_checks_cover_original_and_unknown_subtrees(surface, body):
    if surface == 'original': xml = xdocument('<p>safe</p>', original=body)
    else: xml = document(extensions='<TOOL-EXTENSIONS><root xmlns="urn:foreign">'+body+'</root></TOOL-EXTENSIONS>')
    refuse(independent({'document.reqif': xml}), 7)


def test_selected_documents_can_refer_to_each_other_without_recursive_parsing_or_id_merging():
    files = {'docs/a': xdocument('<a href="b">b</a>'), 'docs/b': xdocument('<a href="a">a</a>'),
             'not-selected.reqif': b'<!DOCTYPE evil>not XML', 'nested.zip': b'PK not recursively opened'}
    with no_write_attempts():
        value = read(write(files, ['docs/b','docs/a']), ['docs/a','docs/b'])
        assert value.files == files and write(value.files, value.document_paths) == value.source_bytes
    assert value.manifest['references'] == [
        {'document_path':'docs/a','reference':'b','member_path':'docs/b'},
        {'document_path':'docs/b','reference':'a','member_path':'docs/a'}]


def test_unicode_names_xml_decoding_and_manifest_order_are_exact_without_name_inference():
    files = {'ä/source': xdocument('<a href="%C3%A9%26x.bin">link</a>'), 'ä/é&x.bin': b'unicode',
             'Z/empty': b'', 'é.json': b'{}', 'a/empty': b''}
    with no_write_attempts():
        raw = write(files, ['ä/source']); value = read(raw, ['ä/source'])
    assert raw == independent(files) and value.files == files
    assert [row['path'] for row in value.manifest['entries']] == ['Z/empty','a/empty','ä/source','ä/é&x.bin','é.json']
    assert value.manifest['references'] == [
        {'document_path':'ä/source','reference':'%C3%A9%26x.bin','member_path':'ä/é&x.bin'}]


def test_aggregate_limit_counts_each_physical_member_once_and_all_unused_bytes():
    xml = xdocument('<a href="empty">once</a><a href="empty">twice</a>')
    files = {'a/source': xml, 'b/source': xml, 'a/empty': b'', 'b/empty': b'', 'unused': b'123'}
    paths = ['b/source','a/source']; total = sum(map(len, files.values())); raw = independent(files)
    with no_write_attempts():
        assert write(files, paths, max_uncompressed_bytes=total) == raw
        assert read(raw, paths, max_uncompressed_bytes=total).files == files
        with patch.object(ZipFile, 'read', side_effect=AssertionError('over-limit read')):
            with pytest.raises(ReqIFError) as caught: read(raw, paths, max_uncompressed_bytes=total-1)
            assert caught.value.exit_code == 7
    # A per-document bound applies to each XML independently, not their sum.
    assert read(raw, paths, limits=replace(LIMITS, max_bytes=len(xml))).files == files


@pytest.mark.parametrize('field', list(asdict(LIMITS)))
def test_every_explicit_xml_resource_bound_remains_effective_in_the_container(field):
    raw = independent({'document.reqif': one()})
    with no_write_attempts(), pytest.raises(ReqIFError) as caught:
        read(raw, limits=replace(LIMITS, **{field:1}))
    assert caught.value.exit_code == 7


@pytest.mark.parametrize('option,value', [
    ('limits', None), ('limits', asdict(LIMITS)), ('document_paths', None),
    ('document_paths', {'document.reqif'}), ('document_paths', [1]),
    ('expected_sha256', None), ('expected_sha256', 'A'*64), ('expected_sha256', '0'*63),
], ids=['missing-limits','untyped-limits','missing-selection','set-selection','bad-path-type',
        'missing-hash','noncanonical-hash','short-hash'])
def test_invalid_calls_are_usage_errors_before_member_reads(option, value):
    raw = independent(source_files())
    with no_write_attempts(), patch.object(ZipFile,'read',side_effect=AssertionError('invalid call read')):
        with pytest.raises(ReqIFError) as caught: read(raw, **{option:value})
    assert caught.value.exit_code == 2


@pytest.mark.parametrize('failure', [MemoryError, OSError, RecursionError])
def test_real_host_failures_during_xml_assessment_are_not_container_success(failure):
    raw = independent(source_files())
    with no_write_attempts(), patch('specroad.exchange.reqifz.decode_reqif_structure', side_effect=failure):
        with pytest.raises(failure): read(raw)


def test_empty_transport_cannot_satisfy_a_document_selection():
    with no_write_attempts(), pytest.raises(ReqIFError) as caught: read(independent({}))
    assert caught.value.exit_code == 6


def test_owned_manifests_and_members_do_not_expose_an_import_or_write_capability():
    raw = independent(source_files())
    with no_write_attempts():
        value = read(raw); saved = value.manifest_bytes
        view = value.manifest; view['documents'].append('forged'); view['entries'][0]['sha256']='0'*64
        view['references'].append({'write_authorized':True}); value.files['unused.bin']=b'changed'
    assert value.manifest_bytes == saved and value.files == source_files()
    assert set(value.manifest) == {'format_version','archive_sha256','entries','documents','references'}
