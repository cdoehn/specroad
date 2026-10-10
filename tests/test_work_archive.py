"""Canonical binary container and inventory contracts, with no extraction."""

from hashlib import sha256
from io import BytesIO
import json
import stat
from zipfile import ZipFile, ZipInfo, ZIP_STORED

import pytest

from specroad.model.canonical import canonical_json_bytes
from specroad.work._archive import ArchiveError, encode_archive, decode_archive
from support.read_only import inventory, no_write_attempts


NAME = 'bundle-manifest.json'


def read(raw, **options):
    return decode_archive(raw, manifest_name=NAME,
                          expected_sha256=options.get('expected_sha256', sha256(raw).hexdigest()))


def foreign_zip(entries, *, change=None, comment=b''):
    """Independent stdlib construction of actual foreign ZIP bytes."""
    stream = BytesIO()
    with ZipFile(stream, 'w', compression=ZIP_STORED, allowZip64=False) as archive:
        archive.comment = comment
        for name, raw in entries:
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3; info.create_version = info.extract_version = 20
            info.external_attr = 0o100644 << 16; info.internal_attr = 0
            if change is not None:
                change(info)
            archive.writestr(info, raw)
    return stream.getvalue()


def entries(raw):
    with ZipFile(BytesIO(raw)) as archive:
        return [(info.filename, archive.read(info)) for info in archive.infolist()]


def test_canonical_container_retains_all_bytes_and_has_nonrecursive_inventory(tmp_path):
    payloads = {'z/raw': b'\0\xff\x80', 'ä.json': canonical_json_bytes({'owned': 'value'}), 'a.json': b'{}'}
    metadata = {'format_version': 'owned-archive-fixture-v1', 'package_kind': 'fixture'}
    before = inventory(tmp_path)
    with no_write_attempts():
        raw = encode_archive(NAME, metadata, payloads)
        assert encode_archive(NAME, metadata, dict(reversed(list(payloads.items())))) == raw
        decoded, files = read(raw)
    assert decoded == metadata and files == payloads and inventory(tmp_path) == before
    with ZipFile(BytesIO(raw)) as archive:
        names = archive.namelist()
        assert names == sorted([NAME, *payloads], key=lambda name: name.encode('utf-8'))
        manifest = json.loads(archive.read(NAME))
        assert [item['path'] for item in manifest['entries']] == sorted(payloads, key=lambda name: name.encode('utf-8'))
        assert all(item['path'] != NAME for item in manifest['entries'])
        assert 'sha256' not in manifest and 'size' not in manifest
        for item in manifest['entries']:
            assert item['size'] == len(payloads[item['path']])
            assert item['sha256'] == sha256(payloads[item['path']]).hexdigest()
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0) and info.compress_type == ZIP_STORED
            assert info.create_system == 3 and info.create_version == info.extract_version == 20
            assert info.external_attr == 0o100644 << 16 and info.internal_attr == 0
            assert not info.extra and not info.comment and not info.flag_bits & 8
        assert archive.comment == b''


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'a//b', 'a/./b', 'a/../b',
                                  'a\\b', 'x:stream', 'a\nb', 'e\u0301'])
def test_unsafe_or_non_normalized_paths_are_refused_without_effects(tmp_path, name):
    raw = foreign_zip([(NAME, b'{}'), (name, b'payload')]); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        read(raw)
    assert caught.value.exit_code == 7 and inventory(tmp_path) == before
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        encode_archive(NAME, {}, {name: b'payload'})
    assert caught.value.exit_code == 7


@pytest.mark.parametrize('mode', [stat.S_IFLNK | 0o777, stat.S_IFDIR | 0o755,
                                 stat.S_IFIFO | 0o600, stat.S_IFCHR | 0o600, stat.S_IFREG | 0o755])
def test_special_entries_and_unapproved_modes_are_never_extracted(tmp_path, mode):
    raw = foreign_zip([(NAME, b'{}')], change=lambda info: setattr(info, 'external_attr', mode << 16))
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        read(raw)
    assert caught.value.as_dict() == {'reason': 'unsafe_archive_entry', 'exit_code': 7}
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('which', ['tail', 'prefix', 'order', 'comment', 'timestamp', 'duplicate'])
def test_noncanonical_container_bytes_are_not_accepted_as_the_bound_archive(tmp_path, which):
    raw = encode_archive(NAME, {}, {'a': b'payload'}); members = entries(raw)
    if which == 'tail': raw += b'foreign'
    elif which == 'prefix': raw = b'foreign' + raw
    elif which == 'order': raw = foreign_zip(list(reversed(members)))
    elif which == 'comment': raw = foreign_zip(members, comment=b'foreign')
    elif which == 'timestamp': raw = foreign_zip(members, change=lambda info: setattr(info, 'date_time', (2020, 1, 1, 0, 0, 0)))
    else:
        with pytest.warns(UserWarning):
            raw = foreign_zip([*members, members[0]])
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError):
        read(raw)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('which', ['missing', 'additional', 'bytes', 'manifest_self_reference', 'boolean_size'])
def test_inventory_must_bind_exactly_every_actual_payload(tmp_path, which):
    raw = encode_archive(NAME, {}, {'a': b'x'}); values = dict(entries(raw))
    if which == 'missing': del values['a']
    elif which == 'additional': values['extra'] = b'owned'
    elif which == 'bytes': values['a'] = b'y'
    else:
        manifest = json.loads(values[NAME])
        if which == 'manifest_self_reference': manifest['entries'][0]['path'] = NAME
        else: manifest['entries'][0]['size'] = True
        values[NAME] = canonical_json_bytes(manifest)
    altered = foreign_zip(sorted(values.items())); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        read(altered)
    assert caught.value.reason == 'archive_inventory_mismatch' and inventory(tmp_path) == before


def test_an_external_hash_is_required_and_a_manifest_cannot_include_itself(tmp_path):
    raw = encode_archive(NAME, {}, {'a': b'payload'}); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        read(raw, expected_sha256='0' * 64)
    assert caught.value.reason == 'archive_hash_mismatch'
    with no_write_attempts(), pytest.raises(ArchiveError) as caught:
        encode_archive(NAME, {}, {NAME: b'{}'})
    assert caught.value.reason == 'recursive_archive_manifest' and inventory(tmp_path) == before
