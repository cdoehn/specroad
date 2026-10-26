"""Backup-file observations, independent of ongoing Work execution.

The publisher supplies an already checked checkpoint identity and local file
observation. This projection reads no live Work state and performs no I/O.
A generated package proves neither completion of the work nor external
retention after sandbox loss; those facts are not inferred from this record.
"""


def package_export_result(*, work_id, checkpoint_generation, checkpoint_sha256,
                          root, path, size, digest):
    """Preserve the export contract for exactly the retained generation."""
    return {'format_version': 'work-package-export-v1', 'package_kind': 'work',
        'work_id': work_id, 'checkpoint_generation': checkpoint_generation,
        'checkpoint_sha256': checkpoint_sha256,
        'file': {'root': str(root), 'path': path, 'size': size, 'sha256': digest},
        'generated': True, 'normative': False, 'source_bytes_rechecked': True,
        'external_backup_confirmed': False}
