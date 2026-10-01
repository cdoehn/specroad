"""Conservative recovery retention inventory and cache-removal policy boundary.

No cleanup implementation or deletion capability is introduced. Maintenance
must use this check and freshly recheck at its own authorized write boundary;
a detached observation is never a reusable permission token.
"""
import os
import stat
from ..model.paths import project_path
from ..model.errors import ModelError
from ..security import SafetyViolation
from ._lock_files import LockFiles
from ._recovery_rollback import _fingerprint
from .execution_values import ChangeExecutionError
from .recovery_values import RecoveryError, RecoveryObservation
from .recovery_read import inspect_recovery

from ..model.operational_paths import PROTECTED_ROOTS, CACHE_ROOT, recovery_resource_role


def inspect_recovery_protection(root):
    """Read all retained operational evidence, including unknown and unsafe names.

    Never follow a link, infer missing content, or regard a self-declared
    terminal journal as permission to discard files. Receipts and audits remain
    protected even after a correctly completed transaction.
    """
    status = inspect_recovery(root).data
    records = {}
    with LockFiles(root) as files:
        def scan(path):
            record = {'path': path, 'role': recovery_resource_role(path),
                      'recovery_critical': True, 'cache_removal_allowed': False,
                      'status': 'unavailable', 'size': None, 'sha256': None}
            records[path] = record
            parts = tuple(path.split('/'))
            try:
                with files.directory(parts[:-1]) as parent:
                    if parent is None:
                        record['status'] = 'missing'; return
                    try:
                        info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                    except FileNotFoundError:
                        record['status'] = 'missing'; return
                if stat.S_ISDIR(info.st_mode):
                    with files.directory(parts) as directory:
                        if directory is None:
                            raise RecoveryError('recovery_inventory_changed', exit_code=6)
                        names = sorted(os.listdir(directory))
                        record['status'] = 'directory'
                        for name in names:
                            scan(path + '/' + name)
                        if names != sorted(os.listdir(directory)):
                            raise RecoveryError('recovery_inventory_changed', exit_code=6)
                else:
                    token = _fingerprint(files, path)
                    if token is None:
                        record['status'] = 'missing'
                    else:
                        record.update(status='present', size=token['size'], sha256=token['sha256'])
            except (ChangeExecutionError, SafetyViolation, OSError) as error:
                record.update(status='unavailable', reason=getattr(error, 'reason', 'unsafe_recovery_resource'))
        for path in PROTECTED_ROOTS:
            scan(path)
    # Absent mandatory images must be visible even though enumeration cannot see them.
    for transaction in status['transactions']:
        for item in transaction['critical_resources']:
            if recovery_resource_role(item['path']) is None:
                continue
            if item['path'] not in records:
                records[item['path']] = {'path': item['path'], 'role': item['role'],
                    'recovery_critical': True, 'cache_removal_allowed': False,
                    'status': item['status'], 'size': item['observed_size'],
                    'sha256': item['observed_sha256']}
    return RecoveryObservation._create({'format_version': 'recovery-protection-v1',
        'protected_roots': list(PROTECTED_ROOTS),
        'resources': [records[p] for p in sorted(records)],
        'blockers': [b for t in status['transactions'] for b in t['blockers']],
        'model_loaded': False, 'observation_only': True, 'write_authorized': False,
        'atomic_snapshot': False, 'files_deleted': 0})


def check_cache_removal(root, paths):
    """Check an explicit file selection; never remove or repair any file.

    Only regular, singly linked files BELOW .specroad/cache can be candidates.
    Whole directories and aliases are refused, even when a caller says that
    recovery is complete or that all operational files are disposable.
    """
    if type(paths) not in (tuple, list) or not paths:
        raise RecoveryError('explicit_cache_paths_required', exit_code=2)
    try:
        names = [project_path(path) for path in paths]
    except (ModelError, TypeError, ValueError) as error:
        raise RecoveryError('unsafe_cache_path', exit_code=7) from error
    if len(set(names)) != len(names):
        raise RecoveryError('duplicate_cache_path', exit_code=2)
    for path in names:
        if not path.startswith(CACHE_ROOT + '/') or recovery_resource_role(path) is not None:
            raise RecoveryError('cache_removal_protected_path', path=path, exit_code=7)
    candidates = []
    with LockFiles(root) as files:
        for path in names:
            try:
                token = _fingerprint(files, path)
            except (ChangeExecutionError, SafetyViolation, OSError) as error:
                raise RecoveryError('unsafe_cache_resource', path=path, exit_code=7) from error
            candidates.append({'path': path, 'present': token is not None,
                'size': None if token is None else token['size'],
                'sha256': None if token is None else token['sha256']})
    return RecoveryObservation._create({'format_version': 'cache-removal-check-v1',
        'candidates': candidates, 'selection_checked': True,
        'write_authorized': False, 'recheck_at_write_required': True,
        'model_loaded': False, 'files_deleted': 0})
