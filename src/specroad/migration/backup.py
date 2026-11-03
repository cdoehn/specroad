"""Complete original-byte source backups; never migration/write authority."""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
import stat
from types import MappingProxyType, SimpleNamespace

from .._metadata import __version__
from ..bundles.errors import BundleError
from ..bundles.manifest import require, require_hash, check_entries
from ..bundles.container import _archive_failure
from ..bundles.publication import _publish
from ..changes._lock_files import LockFiles
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..model.operational_paths import PASSIVE_ROOTS, PASSIVE_JOURNAL_DIRECTORIES
from ..security import paths as guards
from ..storage.archive import (ArchiveError, encode_archive, decode_zip,
    validate_portable_archive_paths, _inventory)
from ..storage.json_syntax import parse_json_object
from ..storage.operational_preflight import observe_operational_preflight
from .reference01 import inventory_bytes
from .reference01.values import CONTRACT_ID, CONTRACT_VERSION, SCOPE
from .plan_values import SOURCE_CONTRACT, file_bindings

MANIFEST = 'migration-source-manifest.json'
FORMAT = 'migration-source-backup-v1'
ADMIN_ROOTS = frozenset(('.git', '.codex', '.agents', '.aws', '.ssh', '.patchharbor'))
PASSIVE = tuple(PASSIVE_ROOTS) + tuple('.specroad/' + a + '/' + b
                                      for a, b in PASSIVE_JOURNAL_DIRECTORIES)


def _safe(ok, reason):
    if not ok:
        raise BundleError(reason, code='SRV083', exit_code=7)


def _source(files):
    require(type(files) is dict and all(type(p) is str and type(b) is bytes
            for p, b in files.items()), 'migration_backup_bytes_required')
    files = dict(files)
    validate_portable_archive_paths(list(files))
    for name in files:
        parts = name.split('/')
        _safe(not any(p.casefold() in ADMIN_ROOTS for p in parts),
              'migration_backup_protected_path')
        _safe('.specroad' not in [p.casefold() for p in parts[1:]],
              'migration_backup_protected_path')
        if parts[0].casefold() == '.specroad':
            require(any(name.startswith(p + '/') for p in PASSIVE),
                    'migration_backup_operational_state')
        _safe(name == 'specroad.json' or parts[-1].casefold() != 'specroad.json',
              'migration_backup_nested_project')
    # Retained passive operational bytes are not normative source resources,
    # portable receipts or authority. The source reader verifies all closure.
    source = inventory_bytes({p: b for p, b in files.items() if not p.startswith('.specroad/')})
    return files, source


def _metadata(files, source, tool_version):
    require(type(tool_version) is str and bool(tool_version.strip()) and '\0' not in tool_version,
            'migration_backup_tool_version')
    return {'backup_format_version': FORMAT, 'bundle_kind': 'migration_source',
        'read_only': True, 'project_id': source.data['project_id'], 'tool_version': tool_version,
        'source_contract': {'contract_id': CONTRACT_ID, 'contract_version': CONTRACT_VERSION, **SOURCE_CONTRACT},
        'scope_descriptor': SCOPE, 'source_model_root_sha256': source.model_root_sha256,
        'source_files_sha256': digest(file_bindings(files))}


@dataclass(frozen=True, init=False)
class SourceBackup:
    source_bytes: bytes
    _files: object
    _manifest_bytes: bytes

    @property
    def files(self):
        return dict(self._files)

    @property
    def manifest(self):
        return json.loads(self._manifest_bytes)

    @property
    def sha256(self):
        return sha256(self.source_bytes).hexdigest()

    @property
    def write_authorized(self):
        return False

    def __bool__(self):
        raise TypeError('A source backup is not migration authorization')


def verify_source_backup(raw, *, expected_sha256, expected_source_files_sha256):
    """Verify actual ZIP bytes, independent source closure and both external hashes."""
    require(type(raw) is bytes, 'migration_backup_bytes_required')
    require_hash(expected_sha256); require_hash(expected_source_files_sha256)
    require(sha256(raw).hexdigest() == expected_sha256, 'migration_backup_hash_mismatch', code='SRV060')
    try:
        payloads = decode_zip(raw, max_uncompressed_bytes=max(1, len(raw)),
                              validate_paths=validate_portable_archive_paths)
        require(MANIFEST in payloads, 'migration_backup_manifest_missing')
        manifest_raw = payloads.pop(MANIFEST)
        manifest = parse_json_object(manifest_raw)
        require(jcs(manifest) == manifest_raw, 'migration_backup_manifest_noncanonical')
        require('entries' in manifest, 'migration_backup_entries_missing')
        check_entries(manifest['entries'])
        require(jcs(manifest['entries']) == jcs(_inventory(payloads)),
                'migration_backup_inventory_mismatch', code='SRV060')
        require(all(p.startswith('source/') for p in payloads), 'migration_backup_payload_namespace')
        files, source = _source({p[len('source/'):]: b for p, b in payloads.items()})
        expected = _metadata(files, source, manifest.get('tool_version'))
        require(jcs({k: v for k, v in manifest.items() if k != 'entries'}) == jcs(expected),
                'migration_backup_source_binding', code='SRV060')
        require(expected['source_files_sha256'] == expected_source_files_sha256,
                'migration_backup_source_changed', code='SRV060')
    except ArchiveError as error:
        raise _archive_failure(error) from error
    except ModelError as error:
        raise BundleError(error.reason, exit_code=getattr(error, 'exit_code', 3)) from error
    result = object.__new__(SourceBackup)
    object.__setattr__(result, 'source_bytes', raw)
    object.__setattr__(result, '_files', MappingProxyType(files))
    object.__setattr__(result, '_manifest_bytes', manifest_raw)
    return result


def prepare_source_backup(files):
    """Pure construction from complete owned bytes; no snapshot/approval claim."""
    try:
        files, source = _source(files)
        metadata = _metadata(files, source, __version__)
        payloads = {'source/' + p: raw for p, raw in files.items()}
        validate_portable_archive_paths([MANIFEST, *payloads])
        raw = encode_archive(MANIFEST, metadata, payloads)
        return verify_source_backup(raw, expected_sha256=sha256(raw).hexdigest(),
                                    expected_source_files_sha256=metadata['source_files_sha256'])
    except ArchiveError as error:
        raise _archive_failure(error) from error
    except ModelError as error:
        raise BundleError(error.reason, exit_code=getattr(error, 'exit_code', 3)) from error


def _scan(handles):
    found, pending = [], [()]
    while pending:
        parts = pending.pop()
        with handles.directory(parts) as fd:
            require(fd is not None, 'migration_backup_source_changed')
            names = sorted(os.listdir(fd))
            _safe(len({n.casefold() for n in names}) == len(names), 'migration_backup_path_collision')
            for name in names:
                if not parts and name in ADMIN_ROOTS:
                    continue  # Outside the project; never open credentials/Git state.
                guards._parts(name)
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                directory = stat.S_ISDIR(info.st_mode)
                guards._regular(info, directory=directory)
                path = (*parts, name)
                if directory:
                    pending.append(path)
                else:
                    found.append('/'.join(path))
            require(sorted(os.listdir(fd)) == names, 'migration_backup_source_changed')
    validate_portable_archive_paths(found)
    return tuple(sorted(found, key=lambda p: p.encode('utf-8')))


def _observe(root):
    with LockFiles(root) as handles:
        boundary = handles.boundary
        def preflight():
            require(observe_operational_preflight(boundary)['consistency_state'] == 'consistent',
                    'migration_backup_operational_state')
        preflight(); names = _scan(handles)
        files = {p: boundary.read_bytes(p) for p in names}
        def check_current():
            boundary._check_root()
            with LockFiles(boundary.root) as current:
                require(current.boundary._root_identity == boundary._root_identity,
                        'migration_backup_source_changed')
                preflight()
                require(_scan(current) == names, 'migration_backup_source_changed')
                for p, raw in files.items():
                    require(boundary.read_bytes(p) == raw, 'migration_backup_source_changed')
                preflight()
                require(_scan(current) == names, 'migration_backup_source_changed')
        check_current()
    return files, SimpleNamespace(boundary=boundary), check_current


def _report(backup, path):
    manifest = backup.manifest
    return {'format_version': 'migration-source-backup-report-v1',
        'file': {'path': str(path), 'size': len(backup.source_bytes), 'sha256': backup.sha256},
        'source_model_root_sha256': manifest['source_model_root_sha256'],
        'source_files_sha256': manifest['source_files_sha256'], 'backup_verified': True,
        'source_bytes_rechecked': True, 'atomic_snapshot': False,
        'write_authorized': False, 'approval_granted': False}


def create_source_backup(root, *, output, output_root, expected_source_files_sha256):
    """Publish outside the project, preserving every source byte and existing target."""
    from ..documents._export_targets import _output_boundary
    require(output_root is not None, 'migration_backup_external_output_required')
    require_hash(expected_source_files_sha256)
    try:
        files, source, check_current = _observe(root)
        backup = prepare_source_backup(files)
        require(backup.manifest['source_files_sha256'] == expected_source_files_sha256,
                'migration_backup_source_changed', code='SRV060')
        boundary = _output_boundary(output_root, source)
        published = _publish(backup, source, check_current, output, output_root)
        raw = boundary.read_bytes(published['file']['path'])
        verified = verify_source_backup(raw, expected_sha256=backup.sha256,
                                         expected_source_files_sha256=expected_source_files_sha256)
        check_current()
        return _report(verified, boundary.root / published['file']['path'])
    except OSError as error:
        raise BundleError('migration_backup_host_io', code=None, exit_code=5) from error
