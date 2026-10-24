"""14.k.W: real canonical container bytes, explicit documents and attachments."""
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import stat
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from specroad.exchange import (ReqIFError, ReqIFAttachment, decode_reqif_structure,
                              decode_reqifz, encode_reqifz)
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes
from support.read_only import inventory, no_write_attempts
from support.reqif_objects import LIMITS, document, one
from support.reqif_structure import xdocument
from test_work_archive import foreign_zip


def write(files, paths=('document.reqif',), **options):
    args = {'document_paths': paths, 'limits': LIMITS, 'max_uncompressed_bytes': 8*1024*1024}
    args.update(options)
    return encode_reqifz(files, **args)


def read(raw, paths=('document.reqif',), **options):
    args = {'document_paths': paths, 'limits': LIMITS, 'max_uncompressed_bytes': 8*1024*1024,
            'expected_sha256': sha256(raw).hexdigest()}
    args.update(options)
    return decode_reqifz(raw, **args)


def independent(files, **options):
    return foreign_zip(sorted(files.items(), key=lambda row: row[0].encode('utf-8')), **options)


def test_container_roundtrip_keeps_every_original_byte_and_derives_external_manifest(tmp_path):
    xml = xdocument('<p><object data="pictures/a.png" type="image/png"/></p>')
    files = {'document.reqif': xml.replace(b'\n', b'\r\n'), 'pictures/a.png': b'\x89PNG\r\n\x1a\nowned',
             'manifest.json': b'not trusted metadata', 'unused/other.reqif': b'not selected XML',
             'unused/data.zip': b'not a nested ZIP', 'ä.bin': b'\0\xff'}
    before = inventory(tmp_path)
    with no_write_attempts():
        raw = write(files)
        assert raw == independent(files)
        value = read(raw)
        assert value.source_bytes == raw and value.files == files
        assert write(value.files, value.document_paths) == raw
        assert write(dict(reversed(list(files.items())))) == raw
        manifest = value.manifest
    assert inventory(tmp_path) == before
    expected = {'format_version': 'reqifz-container-v1', 'archive_sha256': sha256(raw).hexdigest(),
        'entries': [{'path': p, 'size': len(files[p]), 'sha256': sha256(files[p]).hexdigest()}
                    for p in sorted(files, key=lambda p: p.encode('utf-8'))],
        'documents': ['document.reqif'],
        'references': [{'document_path': 'document.reqif', 'reference': 'pictures/a.png',
                        'member_path': 'pictures/a.png'}]}
    assert manifest == expected and value.manifest_bytes == canonical_json_bytes(expected)
    with ZipFile(BytesIO(raw)) as archive:
        assert set(archive.namelist()) == set(files)
        assert archive.read('manifest.json') == files['manifest.json']


def test_multiple_documents_bind_same_reference_to_their_own_directory_without_merging_ids():
    xml = xdocument('<p><a href="a%20b.bin">one</a><a href="a%20b.bin">two</a></p>')
    files = {'docs/a.xml': xml, 'other/anything': xml, 'docs/a b.bin': b'first',
             'other/a b.bin': b'second', 'a b.bin': b'root decoy'}
    with no_write_attempts():
        raw = write(files, ['other/anything', 'docs/a.xml'])
        first = read(raw, ['docs/a.xml', 'other/anything'])
        second = read(raw, ['other/anything', 'docs/a.xml'])
    assert first.files == files and first.manifest_bytes == second.manifest_bytes
    assert first.manifest['documents'] == ['docs/a.xml', 'other/anything']
    assert first.manifest['references'] == [
        {'document_path': 'docs/a.xml', 'reference': 'a%20b.bin', 'member_path': 'docs/a b.bin'},
        {'document_path': 'other/anything', 'reference': 'a%20b.bin', 'member_path': 'other/a b.bin'}]


def test_owned_container_data_cannot_be_changed_through_input_or_returned_collections():
    files = {'document.reqif': one()}; paths = ['document.reqif']
    raw = write(files, paths); value = read(raw, paths)
    original = value.manifest_bytes
    files.clear(); paths.append('absent'); value.files.clear(); value.manifest['entries'].clear()
    assert value.source_bytes == raw and value.document_paths == ('document.reqif',)
    assert value.manifest_bytes == original and value.files['document.reqif'] == one()
    with pytest.raises(AttributeError): value.source_bytes = b'changed'


def test_native_projection_still_requires_explicit_native_attachment_descriptor():
    xml = xdocument('<p><object data="p.png" type="image/png"/></p>')
    content = b'\x89PNG\r\n\x1a\nowned'
    files = {'docs/source.reqif': xml, 'docs/p.png': content}
    with no_write_attempts():
        container = read(write(files, ['docs/source.reqif']), ['docs/source.reqif'])
        doc = decode_reqif_structure(container.files['docs/source.reqif'], limits=LIMITS)
        with pytest.raises(ReqIFError): doc.project_xhtml('object', 'field')
        descriptor = AttachmentDescriptor('attachments/explicit.png', 'image/png', len(content), sha256(content).hexdigest())
        binding = ReqIFAttachment('p.png', descriptor, container.files['docs/p.png'])
        projected = doc.project_xhtml('object', 'field', attachments=[binding])
    assert projected['content'] == {'type': 'document', 'children': [
        {'type': 'paragraph', 'children': [
            {'type': 'image', 'attachment_path': 'attachments/explicit.png', 'children': []}]}]}
    assert projected['attachments'] == [descriptor.data]
    assert not projected['import_complete'] and not projected['write_authorized']
    assert not doc.observation()['write_authorized']


@pytest.mark.parametrize('files,paths', [
    ({'document.reqif': one()}, ['absent']),
    ({'docs/source.reqif': xdocument('<a href="p.bin">link</a>'), 'p.bin': b'root decoy'}, ['docs/source.reqif']),
    ({'document.reqif': xdocument('<a href="p.bin">link</a>'), 'P.bin': b'case decoy'}, ['document.reqif']),
])
def test_missing_document_or_exact_relative_member_is_a_conflict(files, paths):
    with no_write_attempts():
        for call in (lambda: write(files, paths), lambda: read(independent(files), paths)):
            with pytest.raises(ReqIFError) as error: call()
            assert error.value.exit_code == 6


@pytest.mark.parametrize('paths', [[], ['document.reqif', 'document.reqif'], 'document.reqif', [None]])
def test_document_selection_is_explicit_nonempty_and_unique(paths):
    files = {'document.reqif': one()}
    with no_write_attempts():
        for call in (lambda: write(files, paths), lambda: read(independent(files), paths)):
            with pytest.raises(ReqIFError) as error: call()
            assert error.value.exit_code == 2


def test_expected_hash_binds_actual_container_and_selected_xml_is_really_parsed():
    raw = independent({'document.reqif': one()})
    with no_write_attempts():
        with pytest.raises(ReqIFError) as error: read(raw, expected_sha256='0'*64)
        assert error.value.exit_code == 6
        for call in (lambda: write({'document.reqif': b'<not-reqif/>'}),
                     lambda: read(independent({'document.reqif': b'<not-reqif/>'}))):
            with pytest.raises(ReqIFError) as error: call()
            assert error.value.exit_code == 3


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'a\\b', 'a//b', 'a/./b',
    'a/../b', 'e\u0301', '.git/config', 'NUL.bin', 'trailing.', 'a:stream'])
def test_all_member_paths_are_checked_even_for_unused_members(name):
    files = {'document.reqif': one(), name: b'not referenced'}
    with no_write_attempts():
        for call in (lambda: write(files), lambda: read(independent(files))):
            with pytest.raises(ReqIFError) as error: call()
            assert error.value.exit_code == 7


@pytest.mark.parametrize('other', [{'a': b'file', 'a/b': b'child'}, {'A': b'file', 'a/b': b'child'},
    {'A.bin': b'first', 'a.bin': b'second'}, {'A/b': b'first', 'a/c': b'second'}])
def test_portable_collisions_fail_before_any_payload_is_read(other):
    files = {'document.reqif': one(), **other}
    raw = independent(files)
    with no_write_attempts(), patch.object(ZipFile, 'read', side_effect=AssertionError('payload read')):
        for call in (lambda: write(files), lambda: read(raw)):
            with pytest.raises(ReqIFError) as error: call()
            assert error.value.exit_code == 7


@pytest.mark.parametrize('mode', [stat.S_IFLNK | 0o777, stat.S_IFDIR | 0o755, stat.S_IFIFO | 0o600])
def test_special_members_are_not_materialized(tmp_path, mode):
    raw = independent({'document.reqif': one()}, change=lambda info: setattr(info, 'external_attr', mode << 16))
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ReqIFError) as error: read(raw)
    assert error.value.exit_code == 7 and inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['tail', 'prefix', 'compressed', 'comment', 'duplicate'])
def test_noncanonical_container_is_rejected_instead_of_silently_repacked(change):
    files = {'document.reqif': one()}; raw = independent(files)
    if change == 'tail': raw += b'foreign'
    elif change == 'prefix': raw = b'foreign' + raw
    elif change == 'compressed': raw = independent(files, change=lambda info: setattr(info, 'compress_type', 8))
    elif change == 'comment': raw = independent(files, comment=b'foreign')
    else:
        with pytest.warns(UserWarning): raw = foreign_zip(list(files.items()) * 2)
    with no_write_attempts(), pytest.raises(ReqIFError) as error: read(raw)
    assert error.value.exit_code == (7 if change == 'duplicate' else 3)


def test_hard_expansion_limit_counts_unused_members_and_accepts_exact_boundary():
    files = {'document.reqif': one(), 'unused.bin': b'123'}; size = sum(map(len, files.values()))
    raw = independent(files)
    with no_write_attempts():
        assert write(files, max_uncompressed_bytes=size) == raw
        assert read(raw, max_uncompressed_bytes=size).files == files
        with patch.object(ZipFile, 'read', side_effect=AssertionError('payload read')):
            for call in (lambda: write(files, max_uncompressed_bytes=size-1),
                         lambda: read(raw, max_uncompressed_bytes=size-1)):
                with pytest.raises(ReqIFError) as error: call()
                assert error.value.exit_code == 7


@pytest.mark.parametrize('limit', [True, 0, -1, 1.5, None])
def test_expansion_limit_is_a_positive_integer(limit):
    files = {'document.reqif': one()}
    with no_write_attempts():
        for call in (lambda: write(files, max_uncompressed_bytes=limit),
                     lambda: read(independent(files), max_uncompressed_bytes=limit)):
            with pytest.raises(ReqIFError) as error: call()
            assert error.value.exit_code == 2


@pytest.mark.parametrize('xml', [
    xdocument('<a href="../p.bin">unsafe</a>'),
    xdocument('<p>safe</p>', original='<object data="file:///private/file" type="image/png"/>'),
    document(extensions='<TOOL-EXTENSIONS><foreign xmlns="urn:other" poster="https://example.invalid/x"/></TOOL-EXTENSIONS>'),
    document().replace(b'<REQ-IF ', b'<!DOCTYPE REQ-IF [<!ENTITY x "value">]><REQ-IF ', 1),
])
def test_xml_safety_applies_to_selected_documents_originals_and_opaque_subtrees(xml):
    files = {'document.reqif': xml}
    with no_write_attempts():
        for call in (lambda: write(files), lambda: read(independent(files))):
            with pytest.raises(ReqIFError) as error: call()
            assert error.value.exit_code == 7


def test_xml_byte_bound_remains_per_document_and_host_failures_are_not_format_success():
    files = {'document.reqif': one()}; raw = independent(files)
    with no_write_attempts(), pytest.raises(ReqIFError) as error:
        read(raw, limits=replace(LIMITS, max_bytes=len(one())-1))
    assert error.value.exit_code == 7
    for failure in (MemoryError('host'), OSError('host')):
        with patch.object(ZipFile, 'read', side_effect=failure), pytest.raises(type(failure)):
            read(raw)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_reqifz_bytes_and_external_manifest_work_in_isolated_distributions(mode, tmp_path):
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    body = '\n'.join([
        'from hashlib import sha256',
        'from specroad.exchange import decode_reqifz, encode_reqifz, ReqIFLimits',
        'files=' + repr({'document.reqif': one(), 'unreferenced': b'\0\xff'}),
        'options=dict(document_paths=["document.reqif"], limits=ReqIFLimits(8000000,128,100000,4000000,64,512,8000000), max_uncompressed_bytes=8000000)',
        'raw=encode_reqifz(files, **options)',
        'value=decode_reqifz(raw, expected_sha256=sha256(raw).hexdigest(), **options)',
        'assert value.files==files and value.source_bytes==raw',
        'assert value.manifest["archive_sha256"]==sha256(raw).hexdigest()',
        'assert encode_reqifz(value.files, **options)==raw'])
    if mode == 'core': result = run_core(body, tmp_path)
    else:
        _, app = build_distribution(tmp_path/'dist')
        result = run_python(['-I', '-S', '-B', '-c', 'import sys;sys.path.insert(0,'+repr(str(app))+');'+body], tmp_path)
    assert result.returncode == 0, result.stderr
