"""Canonical stored ZIP data with an exact, nonrecursive payload inventory.

No extraction, executable loading or filesystem access. The caller supplies
the manifest name and its domain metadata. ZIP32 and whole-byte processing are
explicit limits of this initial codec; multipart/streaming is separate work.
"""

from hashlib import sha256
from io import BytesIO
import re
import struct
import unicodedata
from zipfile import BadZipFile, LargeZipFile, ZipFile, ZipInfo, ZIP_STORED

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.paths import project_path
from ..storage.json_syntax import parse_json_object


_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_ZIP_DOS_DATE = 33
_ZIP_SYSTEM = 3
_ZIP_VERSION = 20
_ZIP_EXTERNAL_ATTR = 0o100644 << 16


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


def validate_portable_archive_paths(names):
    """Check all file/directory targets, including unused members, pre-read."""
    _paths(names)
    if len(names) != len(set(names)):
        raise ArchiveError('unsafe_archive_path_collision', exit_code=7)
    prefixes, files = {}, {name.casefold() for name in names}
    for name in names:
        try:
            project_path(name)
        except ModelError as error:
            raise ArchiveError('unsafe_archive_path', exit_code=7) from error
        parts = name.split('/')
        for end in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:end])
            key = prefix.casefold()
            if ((key in prefixes and prefixes[key] != prefix)
                    or (end < len(parts) and key in files)):
                raise ArchiveError('unsafe_archive_path_collision', exit_code=7)
            prefixes[key] = prefix


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
                info = ZipInfo(name, date_time=_ZIP_TIMESTAMP)
                info.create_system = _ZIP_SYSTEM
                info.create_version = info.extract_version = _ZIP_VERSION
                info.compress_type = ZIP_STORED
                info.external_attr = _ZIP_EXTERNAL_ATTR
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
    entries = _read_zip(raw, manifest_name=manifest_name)
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


def _byte_limit(value):
    if type(value) is not int or value < 1:
        raise ArchiveError('invalid_archive_byte_limit', exit_code=2)


def encode_zip(payloads, *, max_uncompressed_bytes):
    """Canonical members only; domain manifests are the caller's concern."""
    _byte_limit(max_uncompressed_bytes)
    _require(type(payloads) is dict and all(type(v) is bytes for v in payloads.values()))
    if sum(map(len, payloads.values())) > max_uncompressed_bytes:
        raise ArchiveError('archive_byte_limit', exit_code=7)
    _inventory(payloads)  # Hash every name/payload before inclusion, as for bundles.
    _paths(payloads)
    return _zip(payloads)


def decode_zip(raw, *, max_uncompressed_bytes, validate_paths=None):
    """Bounded canonical members, without an implied domain manifest.

    A trusted domain path validator may raise ArchiveError before any payload
    read. The manifest-bound legacy API retains its original error contracts.
    """
    _byte_limit(max_uncompressed_bytes)
    _require(type(raw) is bytes, 'archive_bytes_required')
    return _read_zip(raw, max_uncompressed_bytes=max_uncompressed_bytes,
                     validate_paths=validate_paths)


def _entry_profile(info, archive_size):
    """Shared entry invariants, preserving security-before-format failures."""
    if info.external_attr != _ZIP_EXTERNAL_ATTR:
        raise ArchiveError('unsafe_archive_entry', exit_code=7)
    _require(info.compress_type == ZIP_STORED
        and info.file_size == info.compress_size and info.file_size <= archive_size
        and info.date_time == _ZIP_TIMESTAMP
        and info.create_system == _ZIP_SYSTEM
        and info.create_version == info.extract_version == _ZIP_VERSION
        and info.flag_bits == (0 if info.filename.isascii() else 0x800)
        and info.internal_attr == 0 and not info.extra and not info.comment,
        'noncanonical_archive_entry')


def _stored_layout(raw, infos):
    """Check ZIP32 header agreement and contiguous extents before payload reads.

    This is a preflight of the shared stored profile, not an unpacker. ZipFile
    still owns decoding and CRC checks; the common writer remains the final
    byte oracle. Only small fixed headers and names are copied here.
    """
    _require(len(infos) <= 0xffff, 'noncanonical_archive')
    cursor = 0
    for info in infos:
        name = info.filename.encode('utf-8')
        header = struct.pack('<4s5H3I2H', b'PK\x03\x04', _ZIP_VERSION, info.flag_bits,
                             ZIP_STORED, 0, _ZIP_DOS_DATE, info.CRC, info.file_size,
                             info.file_size, len(name), 0) + name
        _require(info.header_offset == cursor and raw[cursor:cursor+len(header)] == header,
                 'archive_header_mismatch')
        cursor += len(header) + info.file_size
        _require(cursor <= len(raw), 'archive_data_extent_invalid')
    central_start = cursor
    for info in infos:
        name = info.filename.encode('utf-8')
        header = struct.pack('<4s6H3I5H2I', b'PK\x01\x02', (_ZIP_SYSTEM << 8) | _ZIP_VERSION,
                             _ZIP_VERSION, info.flag_bits, ZIP_STORED, 0, _ZIP_DOS_DATE, info.CRC,
                             info.file_size, info.file_size, len(name), 0, 0, 0,
                             0, _ZIP_EXTERNAL_ATTR, info.header_offset) + name
        _require(raw[cursor:cursor+len(header)] == header, 'archive_header_mismatch')
        cursor += len(header)
    _require(central_start <= 0xffffffff and cursor - central_start <= 0xffffffff,
             'noncanonical_archive')
    end = struct.pack('<4s4H2IH', b'PK\x05\x06', 0, 0, len(infos), len(infos),
                      cursor - central_start, central_start, 0)
    _require(len(raw) == cursor + len(end) and raw[cursor:] == end,
             'noncanonical_archive')


def _read_zip(raw, *, manifest_name=None, max_uncompressed_bytes=None, validate_paths=None):
    try:
        with ZipFile(BytesIO(raw), 'r') as archive:
            infos = archive.infolist()
            # ZipInfo truncates a NUL-bearing filename. Validate its original
            # decoded spelling before that convenience can hide an unsafe path.
            names = [info.orig_filename if max_uncompressed_bytes is not None
                     else info.filename for info in infos]
            if validate_paths is not None:
                validate_paths(names)
            _require(len(names) == len(set(names))
                     and (manifest_name is None or names.count(manifest_name) == 1),
                     'archive_entry_set_invalid')
            _paths(names)
            for info in infos:
                _entry_profile(info, len(raw))
            _require(not archive.comment, 'noncanonical_archive')
            if max_uncompressed_bytes is not None:
                _require(names == sorted(names, key=lambda name: name.encode('utf-8')),
                         'noncanonical_archive')
                _stored_layout(raw, infos)
            if (max_uncompressed_bytes is not None
                    and sum(info.file_size for info in infos) > max_uncompressed_bytes):
                raise ArchiveError('archive_byte_limit', exit_code=7)
            entries = {info.filename: archive.read(info) for info in infos}
    except (BadZipFile, OSError, ValueError, NotImplementedError) as error:
        if isinstance(error, ArchiveError):
            raise
        if isinstance(error, UnicodeError) and manifest_name is None:
            raise ArchiveError('unsafe_archive_path', exit_code=7) from error
        if isinstance(error, OSError) and manifest_name is None:
            raise  # A real host failure is not an ordinary malformed ReqIFZ.
        raise ArchiveError('invalid_archive_container') from error
    _require(raw == _zip(entries), 'noncanonical_archive')
    return entries
