"""Independent foreign ZIP bytes exercise container and path boundaries."""

from hashlib import sha256
from io import BytesIO
import struct
from zipfile import ZipFile

import pytest

from specroad.work._archive import ArchiveError, decode_archive, encode_archive
from support.read_only import inventory, no_write_attempts
from test_work_archive import NAME, entries, foreign_zip, read


@pytest.mark.parametrize('manifest,payloads', [
    (NAME, {'a': b'file', 'a/b': b'child'}),
    (NAME, {'a/b/c': b'child', 'a/b': b'file'}),
    (NAME, {NAME + '/child': b'child'}),
    ('metadata/manifest.json', {'metadata': b'file'}),
])
def test_file_ancestors_including_the_manifest_are_rejected_before_reading_payloads(tmp_path, manifest, payloads):
    # A deliberately invalid manifest still must encounter the unsafe path set first.
    raw = foreign_zip([(manifest, b'not JSON'), *payloads.items()])
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        decode_archive(raw, manifest_name=manifest, expected_sha256=sha256(raw).hexdigest())
    assert caught.value.as_dict() == {'reason': 'unsafe_archive_path_collision', 'exit_code': 7}
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        encode_archive(manifest, {}, payloads)
    assert caught.value.as_dict() == {'reason': 'unsafe_archive_path_collision', 'exit_code': 7}
    assert inventory(tmp_path) == before


def test_shared_directory_prefixes_and_similar_filenames_remain_distinct():
    payloads = {'a/b': b'one', 'a/bc': b'two', 'ab/c': b'three', 'a/d/e': b'four'}
    with no_write_attempts():
        raw = encode_archive(NAME, {}, payloads)
        assert read(raw) == ({}, payloads)


@pytest.mark.parametrize('kind', ['local_crc', 'central_crc', 'local_size', 'central_size',
    'local_method', 'central_method', 'local_encrypted', 'central_encrypted',
    'descriptor', 'local_utf8', 'central_offset', 'payload_crc'])
def test_actual_header_disagreements_and_corrupt_payloads_are_rejected(tmp_path, kind):
    raw = encode_archive(NAME, {}, {'data': b'original payload'})
    altered = bytearray(raw)
    central = raw.index(b'PK\x01\x02')
    if kind == 'local_crc': altered[14] ^= 1
    elif kind == 'central_crc': altered[central + 16] ^= 1
    elif kind == 'local_size': altered[22] ^= 1
    elif kind == 'central_size': altered[central + 24] ^= 1
    elif kind == 'local_method': struct.pack_into('<H', altered, 8, 8)
    elif kind == 'central_method': struct.pack_into('<H', altered, central + 10, 8)
    elif kind == 'local_encrypted': struct.pack_into('<H', altered, 6, 1)
    elif kind == 'central_encrypted': struct.pack_into('<H', altered, central + 8, 1)
    elif kind == 'descriptor':
        struct.pack_into('<H', altered, 6, 8)
        struct.pack_into('<H', altered, central + 8, 8)
    elif kind == 'local_utf8': struct.pack_into('<H', altered, 6, 0x800)
    elif kind == 'central_offset':
        end = raw.rindex(b'PK\x05\x06')
        struct.pack_into('<I', altered, end + 16, central + 1)
    else:
        with ZipFile(BytesIO(raw)) as archive:
            info = archive.getinfo('data')
            offset = info.header_offset + 30 + len(info.filename.encode('utf-8'))
        altered[offset] ^= 1
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        read(bytes(altered))
    assert caught.value.exit_code == 3 and inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['extra', 'entry_comment', 'compressed', 'internal_attribute'])
def test_real_optional_zip_features_do_not_expand_the_canonical_profile(tmp_path, kind):
    members = entries(encode_archive(NAME, {}, {'data': b'owned payload'}))
    def change(info):
        if kind == 'extra': info.extra = b'\x01\xca\x00\x00'
        elif kind == 'entry_comment': info.comment = b'foreign'
        elif kind == 'compressed': info.compress_type = 8
        else: info.internal_attr = 1
    raw = foreign_zip(members, change=change)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        read(raw)
    assert caught.value.exit_code == 3 and inventory(tmp_path) == before
