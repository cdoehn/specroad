"""Source-backup publication and reopening; no migration/write authority."""
from ..bundles.errors import BundleError
from ..bundles.manifest import require, require_hash
from ..bundles.migration_source import SourceBackup, prepare_source_backup, verify_source_backup
from ..bundles.publication import _publish
from ..model.canonical import canonical_json_sha256 as digest
from .plan_values import file_bindings
from ._backup_source import _observe

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
        return verify_source_backup_file(root, output=published['file']['path'],
            output_root=output_root, expected_sha256=verified.sha256,
            expected_source_files_sha256=expected_source_files_sha256)
    except OSError as error:
        raise BundleError('migration_backup_host_io', code=None, exit_code=5) from error


def verify_source_backup_file(root, *, output, output_root, expected_sha256,
                              expected_source_files_sha256):
    """Reopen a concrete backup against the actual complete current source.

    Neither a stored report nor a forged SourceBackup instance is admitted.
    This is a precondition for later migration admission, not a writer lock.
    """
    from ..documents._export_targets import _output_boundary, _target_path
    require(output_root is not None, 'migration_backup_external_output_required')
    require_hash(expected_sha256); require_hash(expected_source_files_sha256)
    try:
        files, source, check_current = _observe(root)
        require(digest(file_bindings(files)) == expected_source_files_sha256,
                'migration_backup_source_changed', code='SRV060')
        boundary = _output_boundary(output_root, source)
        path, _ = _target_path(output, source, output_root)
        raw = boundary.read_bytes(path)
        verified = verify_source_backup(raw, expected_sha256=expected_sha256,
                                         expected_source_files_sha256=expected_source_files_sha256)
        # Compare all originals as well as the independently recomputed binding.
        require(verified.files == files, 'migration_backup_source_changed', code='SRV060')
        check_current()
        require(boundary.read_bytes(path) == raw, 'migration_backup_published_changed', code='SRV060')
        check_current()
        return _report(verified, boundary.root / path)
    except OSError as error:
        raise BundleError('migration_backup_host_io', code=None, exit_code=5) from error
