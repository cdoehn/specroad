"""Pure canonical E.1/E.2 codec, without extraction or project authority."""
from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType

from .._metadata import __version__
from ..model.errors import ModelError
from ..storage.archive import (ArchiveError, encode_archive, decode_zip,
                               validate_portable_archive_paths)
from .errors import BundleError
from .manifest import (MANIFEST_NAME, require, require_hash, owned_metadata,
                       check_manifest_bytes, check_payload_binding)


def _archive_failure(error):
    return BundleError(error.reason, exit_code=error.exit_code,
        code='SRV083' if error.exit_code == 7 else ('SRV060' if error.exit_code == 3 else None))


def _owned_payloads(payloads):
    """Copy exact bytes after validating the writer's portable ZIP namespace."""
    require(type(payloads) is dict and all(type(raw) is bytes for raw in payloads.values()),
            'bundle_payload_bytes_required')
    files = dict(payloads)
    require(MANIFEST_NAME not in files, 'recursive_bundle_manifest', code='SRV060')
    validate_portable_archive_paths([MANIFEST_NAME, *files])
    require(all(len(name.encode('utf-8')) <= 0xffff for name in files),
            'bundle_path_exceeds_zip_field', code='SRV060')
    return files


def encode_bundle(metadata, payloads):
    """Bind supplied native metadata and exact payload bytes using one ZIP codec.

    The current writer's version must be explicit. No mtime, host path or
    implicit project/receipt selection enters this in-memory transport.
    """
    try:
        files = _owned_payloads(payloads)
        value = owned_metadata(metadata)
        require(value['tool_version'] == __version__, 'bundle_writer_version')
        check_payload_binding(value, files)
        return encode_archive(MANIFEST_NAME, value, files)
    except ArchiveError as error:
        raise _archive_failure(error) from error
    except ModelError as error:
        raise BundleError(error.reason) from error
    except OSError as error:
        raise BundleError('bundle_host_io', code=None, exit_code=5) from error


@dataclass(frozen=True, init=False)
class BundleContainer:
    """Owned canonical bytes. Integrity is not semantic completeness/authenticity."""
    source_bytes: bytes
    _files: object
    _manifest_bytes: bytes

    def __init__(self, raw, *, expected_sha256=None):
        require(type(raw) is bytes, 'bundle_bytes_required')
        if expected_sha256 is not None:
            require_hash(expected_sha256)
            require(sha256(raw).hexdigest() == expected_sha256, 'bundle_hash_mismatch', code='SRV060')
        try:
            # ZIP_STORED has no expansion: the already-owned input is a hard
            # upper bound on total member bytes. No soft resource goal truncates.
            files = decode_zip(raw, max_uncompressed_bytes=max(1, len(raw)),
                               validate_paths=validate_portable_archive_paths)
            require(MANIFEST_NAME in files, 'bundle_manifest_missing', code='SRV060')
            manifest_raw = files.pop(MANIFEST_NAME)
            check_manifest_bytes(manifest_raw, files)
        except ArchiveError as error:
            raise _archive_failure(error) from error
        except ModelError as error:
            raise BundleError(error.reason) from error
        except OSError as error:
            raise BundleError('bundle_host_io', code=None, exit_code=5) from error
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_files', MappingProxyType(files))
        object.__setattr__(self, '_manifest_bytes', manifest_raw)

    @property
    def files(self):
        return dict(self._files)

    @property
    def manifest(self):
        return json.loads(self._manifest_bytes)

    @property
    def manifest_bytes(self):
        return self._manifest_bytes

    @property
    def sha256(self):
        return sha256(self.source_bytes).hexdigest()

    @property
    def validation_scope(self):
        return 'container_manifest_and_payload_only'

    @property
    def project_verified(self):
        return False

    @property
    def write_authorized(self):
        return False


def decode_bundle(raw, *, expected_sha256=None):
    """Inspect bytes only; a caller-bound expected hash must be supplied here."""
    return BundleContainer(raw, expected_sha256=expected_sha256)
