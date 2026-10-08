"""Bounded shallow transaction observation; no model, historical scan or writes."""
import os
import stat

from ..model.operational_paths import PASSIVE_ROOTS, passive_journal_directory
from ..security import paths as guards
from ..security.resource_access import opened_resource

MAX_ACTIVE_ENTRIES = 16
MAX_METADATA_BYTES = 1024 * 1024


def observe_operational_preflight(boundary, *, complete_inventory=False):
    """A found active entry already proves the N.3 recovery blocker.

    At most sixteen active/unclear entries are classified. Their existence is
    enough to block; an incomplete list never permits automatic selection or
    ordinary model access. Explicit metadata diagnosis can request its complete
    existing inventory contract. Exact passive directories are not scanned inside.
    """
    observed, unresolved, unknown = [], [], []
    complete = True
    metadata_bytes = 0

    def entries(path):
        nonlocal complete, metadata_bytes
        entered = False
        try:
            with opened_resource(boundary, path, directory=True) as (fd, initial):
                entered = True
                seen = set()
                with os.scandir(fd) as iterator:
                    for entry in iterator:
                        if not complete_inventory and len(unresolved) + len(unknown) >= MAX_ACTIVE_ENTRIES:
                            complete = False
                            return
                        guards._parts(entry.name)
                        if entry.name.casefold() in seen:
                            raise guards.SafetyViolation('Portable directory names collide')
                        seen.add(entry.name.casefold())
                        metadata_bytes += len(entry.name.encode('utf-8'))
                        info = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                        directory = stat.S_ISDIR(info.st_mode)
                        guards._regular(info, directory=directory)
                        yield entry.name, directory
        except FileNotFoundError:
            if entered:
                raise

    present = False
    for name, directory in entries('.specroad'):
        present = True
        path = '.specroad/' + name
        observed.append({'path': path, 'directory': directory})
        if directory and path in PASSIVE_ROOTS:
            continue
        if directory and name in ('locks', 'transactions', 'recovery'):
            for child, is_directory in entries(path):
                logical = path + '/' + child
                observed.append({'path': logical, 'directory': is_directory})
                if name == 'locks':
                    unknown.append(logical)
                elif not (is_directory and passive_journal_directory(name, child)):
                    unresolved.append(logical)
        else:
            unknown.append(path)
    # Preserve the distinction between absent and present-but-empty metadata.
    if not present:
        try:
            with opened_resource(boundary, '.specroad', directory=True):
                present = True
        except FileNotFoundError:
            pass
    state = 'recovery_required' if unresolved else 'unknown' if unknown else 'consistent'
    return {'consistency_state': state, 'recovery_required': bool(unresolved),
            'unresolved_paths': sorted(unresolved), 'unknown_paths': sorted(unknown),
            'observed_entries': sorted(observed, key=lambda value: value['path']),
            'writer_owner': None, 'writer_ownership_verified': False,
            'journal_contents_loaded': False, 'cache_contents_loaded': False,
            'recovery_performed': False, 'model_loaded': False,
            'inspection_scope': 'shallow_operational_entries',
            'operational_directory_present': present, 'atomic_snapshot': False,
            'inspection_complete': complete, 'metadata_bytes_read': metadata_bytes}
