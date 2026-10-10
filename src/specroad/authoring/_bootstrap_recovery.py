"""Closed bootstrap replay: prove the entire state before publishing a prefix.

The journal is passive evidence, not a script or permission to delete anything.
Only the exact minimum project and the current distribution's pinned resources
can be resumed. An incomplete or changed record is retained for diagnosis.
"""
from hashlib import sha256
import os
import stat

from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from ._bootstrap_io import (BootstrapError, BootstrapTree, COMPLETED, STAGING,
    check_entry, directory, identity, info_at, metadata)
from ._initial_content import distribution_content, initial_directories
from ._bootstrap_record import _invalid, _record, _validated_values

JOURNAL_LIMIT = 262144


def _read(parent, name, limit, expected=None):
    """Bounded, no-link, single-inode read with fresh name and fd checks."""
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    guards._regular(before, directory=False)
    if before.st_nlink != 1 or before.st_size > limit:
        _invalid()
    if expected is not None: check_entry(parent, name, expected)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        signature = guards._signature(before)
        if guards._signature(os.fstat(fd)) != signature: _invalid()
        raw = bytearray()
        while len(raw) <= limit:
            block = os.read(fd, min(65536, limit + 1 - len(raw)))
            if not block: break
            raw.extend(block)
        if len(raw) != before.st_size or guards._signature(os.fstat(fd)) != signature:
            _invalid()
        after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if guards._signature(after) != signature: _invalid()
    finally:
        os.close(fd)
    raw = bytes(raw)
    if expected is not None and sha256(raw).hexdigest() != expected['sha256']: _invalid()
    return raw, metadata(before, raw)


def _content(tree, locations, resources):
    content = {}
    for path, expected in sorted(tree.inventory.items()):
        if expected['kind'] != 'file' or path == 'journal.json': continue
        unit = next(unit for unit in tree.units if path == unit or path.startswith(unit + '/'))
        source = tree.held.root_fd if locations[unit] else tree.fd
        parts = path.split('/')
        with directory(source, parts[:-1]) as parent:
            content[path], _ = _read(parent, parts[-1], expected['size'], expected)
        if path in resources and content[path] != resources[path]: _invalid()
    return content


def _receipt_present(held):
    # A missing/non-directory ordinary target will be diagnosed by fresh init's
    # preflight; do not follow it while searching for an optional receipt.
    parent = held.root_fd
    with directory(parent) as root:
        info = info_at(root, COMPLETED[0])
        if info is None or not stat.S_ISDIR(info.st_mode): return False
        with directory(root, COMPLETED[:1]) as operational:
            info = info_at(operational, COMPLETED[1])
            if info is None or not stat.S_ISDIR(info.st_mode): return False
            with directory(operational, COMPLETED[1:2]) as recovery:
                return info_at(recovery, COMPLETED[-1]) is not None


def recover_bootstrap(held, function, name):
    """Return the original successful payload values, or None for a fresh root.

    Failed replays retain their actual state. Only a fresh in-memory attempt
    may use its own rollback inventory; stored records never authorize deletion.
    """
    held.require_held()
    staged = info_at(held.root_fd, STAGING) is not None
    receipt = _receipt_present(held)
    if not staged and not receipt: return None
    if staged and receipt: raise BootstrapError('bootstrap_multiple_records')
    tree = BootstrapTree(held, function, {})
    tree.stage_parts = COMPLETED if receipt else (STAGING,)
    publishing = False
    try:
        with directory(held.root_fd, tree.stage_parts) as fd:
            tree.fd = os.dup(fd)
            tree.stage_identity = identity(os.fstat(fd))
        tree.check()
        if info_at(tree.fd, 'journal.json') is None: _invalid()
        raw, journal_metadata = _read(tree.fd, 'journal.json', JOURNAL_LIMIT)
        registry, profiles, packages, resources = distribution_content()
        document = _record(tree, raw, resources)
        if journal_metadata['identity'] in [v['identity'] for v in tree.inventory.values()]:
            _invalid()
        tree.inventory['journal.json'] = journal_metadata
        locations = tree.checked_locations()
        if receipt and not all(locations.values()): _invalid()
        content = _content(tree, locations, resources)
        configuration, document_id = _validated_values(content, document, name, registry, packages)
        tree.checked_locations()
        publishing = True
        tree.publish()
        tree.retain_completed()
        return content, initial_directories(), configuration, document_id
    except SafetyViolation:
        raise
    except (ModelError, ValueError, TypeError, KeyError, RecursionError) as error:
        raise BootstrapError('bootstrap_journal_invalid', path=STAGING) from error
    except FileNotFoundError as error:
        raise BootstrapError('bootstrap_inventory_changed', path=STAGING,
                             mutation_possible=publishing) from error
    except OSError as error:
        raise BootstrapError('bootstrap_recovery_io', exit_code=5, path=STAGING,
                             mutation_possible=publishing) from error
    finally:
        tree.close()
