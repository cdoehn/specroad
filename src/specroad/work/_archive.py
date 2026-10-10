"""Canonical stored ZIP data with an exact, nonrecursive payload inventory.

No extraction, executable loading or filesystem access. The caller supplies
the manifest name and its domain metadata. ZIP32 and whole-byte processing are
explicit limits of this initial codec; multipart/streaming is separate work.
"""

from hashlib import sha256
from io import BytesIO
import re
import unicodedata
from zipfile import BadZipFile, LargeZipFile, ZipFile, ZipInfo, ZIP_STORED

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


class ArchiveError(ValueError):
    def __init__(self, reason, *, exit_code=3):
        super().__init__(reason)
        self.reason, self.exit_code = reason, exit_code

    def as_dict(self):
        return {'reason': self.reason, 'exit_code': self.exit_code}


def _require(condition, reason='invalid_archive'):
    if not condition:
        raise ArchiveError(reason)


def _path(name):
    if (type(name) is not str or not name or unicodedata.normalize('NFC', name) != name
            or '\\' in name or ':' in name
            or any(part in ('', '.', '..') for part in name.split('/'))
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ArchiveError('unsafe_archive_path', exit_code=7)
    try:
        return name.encode('utf-8')
    except UnicodeError as error:
        raise ArchiveError('unsafe_archive_path', exit_code=7) from error


def _hash(value):
    _require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
             'invalid_archive_hash')


def _paths(names):
    """A regular file cannot also be an ancestor of another archive entry."""
    for name in names:
        _path(name)
    names = set(names)
    for name in names:
        parts = name.split('/')
        if any('/'.join(parts[:end]) in names for end in range(1, len(parts))):
            raise ArchiveError('unsafe_archive_path_collision', exit_code=7)


def _inventory(payloads):
    _require(type(payloads) is dict and all(type(v) is bytes for v in payloads.values()))
    for name in payloads:
        _path(name)
    return [{'path': name, 'size': len(payloads[name]),
             'media_type': 'application/json' if name.endswith('.json') else 'application/octet-stream',
             'sha256': sha256(payloads[name]).hexdigest()}
            for name in sorted(payloads, key=lambda item: item.encode('utf-8'))]


def _zip(entries):
    output = BytesIO()
    try:
        with ZipFile(output, 'w', compression=ZIP_STORED, allowZip64=False) as archive:
            for name in sorted(entries, key=lambda item: item.encode('utf-8')):
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.create_version = info.extract_version = 20
                info.compress_type = ZIP_STORED
                info.external_attr = 0o100644 << 16
                info.internal_attr = 0
                archive.writestr(info, entries[name])
    except LargeZipFile as error:
        raise ArchiveError('archive_requires_multipart', exit_code=5) from error
    return output.getvalue()


def encode_archive(manifest_name, metadata, payloads):
    """Build canonical ZIP bytes; the manifest never inventories itself."""
    _path(manifest_name)
    _require(type(metadata) is dict and 'entries' not in metadata)
    entries = _inventory(payloads)
    _require(manifest_name not in payloads, 'recursive_archive_manifest')
    _paths([manifest_name, *payloads])
    try:
        manifest = canonical_json_bytes({**metadata, 'entries': entries})
    except ModelError as error:
        raise ArchiveError('invalid_archive_metadata') from error
    return _zip({manifest_name: manifest, **payloads})


def decode_archive(raw, *, manifest_name, expected_sha256):
    """Verify external identity, canonical container and exact payload bytes."""
    _require(type(raw) is bytes, 'archive_bytes_required')
    _path(manifest_name); _hash(expected_sha256)
    _require(sha256(raw).hexdigest() == expected_sha256, 'archive_hash_mismatch')
    try:
        with ZipFile(BytesIO(raw), 'r') as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            _require(len(names) == len(set(names)) and names.count(manifest_name) == 1,
                     'archive_entry_set_invalid')
            _paths(names)
            for info in infos:
                if info.external_attr != 0o100644 << 16:
                    raise ArchiveError('unsafe_archive_entry', exit_code=7)
                _require(info.compress_type == ZIP_STORED
                    and info.file_size == info.compress_size and info.file_size <= len(raw)
                    and info.date_time == (1980, 1, 1, 0, 0, 0)
                    and info.create_system == 3 and info.create_version == info.extract_version == 20
                    and info.flag_bits == (0 if info.filename.isascii() else 0x800)
                    and info.internal_attr == 0 and not info.extra and not info.comment,
                    'noncanonical_archive_entry')
            _require(not archive.comment, 'noncanonical_archive')
            entries = {info.filename: archive.read(info) for info in infos}
    except (BadZipFile, OSError, ValueError, NotImplementedError) as error:
        if isinstance(error, ArchiveError):
            raise
        raise ArchiveError('invalid_archive_container') from error
    _require(raw == _zip(entries), 'noncanonical_archive')
    manifest_raw = entries.pop(manifest_name)
    try:
        manifest = parse_json_object(manifest_raw)
        _require(canonical_json_bytes(manifest) == manifest_raw, 'noncanonical_archive_manifest')
    except ModelError as error:
        raise ArchiveError('invalid_archive_manifest') from error
    _require(canonical_json_bytes(manifest.get('entries')) == canonical_json_bytes(_inventory(entries)),
             'archive_inventory_mismatch')
    metadata = {key: value for key, value in manifest.items() if key != 'entries'}
    return metadata, entries
