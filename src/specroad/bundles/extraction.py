"""Verify owned bundle bytes before journaled, no-replace root publication."""
from contextlib import ExitStack
from hashlib import sha256
import os

from ..authoring._bootstrap_io import (BootstrapError, BootstrapTree, STAGING,
    directory, identity, info_at, rename_function)
from ..authoring._bootstrap_recovery import _read
from ..authoring._bootstrap_root import BootstrapRoot, root_destination
from ..changes._lock_files import LockFiles
from ..cli.result_schemas import validate_result_document
from ..model.errors import ModelError
from ..security import SafetyViolation
from ._extraction_record import COMPLETED, FORMAT, restore_inventory
from .container import BundleContainer
from .errors import BundleError
from .manifest import MANIFEST_NAME
from .verification import verify_bundle


def _directories(content):
    # ZIP has no directory entries. Only necessary parents and the local
    # recovery namespace are created; no project defaults replace bundle bytes.
    result = {'.specroad', '.specroad/recovery'}
    for path in content:
        parts = path.split('/')
        result.update('/'.join(parts[:n]) for n in range(1, len(parts)))
    return result


def _recover(held, function, content, directories, guard):
    staged = info_at(held.root_fd, STAGING) is not None
    with held.directory(COMPLETED[:-1]) as parent:
        receipt = parent is not None and info_at(parent, COMPLETED[-1]) is not None
    if not staged and not receipt:
        return False
    if staged and receipt:
        raise BootstrapError('bootstrap_multiple_records')
    tree = BootstrapTree(held, function, {}, completed=COMPLETED)
    tree.stage_parts = COMPLETED if receipt else (STAGING,)
    publishing = False
    try:
        with directory(held.root_fd, tree.stage_parts) as fd:
            tree.fd = os.dup(fd)
        tree.stage_identity = identity(os.fstat(tree.fd))
        # Bound control input by the expected inventory, never an input-declared
        # payload size. The native file reader checks links and concurrent edits.
        limit = 4096 + sum(1024 + 2 * len(p.encode('utf-8')) for p in set(content) | directories)
        raw, journal = _read(tree.fd, 'journal.json', limit)
        restore_inventory(tree, raw, content, directories)
        if journal['identity'] in [v['identity'] for v in tree.inventory.values()]:
            raise BootstrapError('bundle_bootstrap_journal_invalid')
        tree.inventory['journal.json'] = journal
        guard(tree)
        if receipt and not all(tree.checked_locations().values()):
            raise BootstrapError('bootstrap_publication_incomplete')
        publishing = True
        tree.publish(guard=lambda: guard(tree))
        tree.retain_completed()
        guard(tree)
        return True
    except (SafetyViolation, BundleError):
        raise
    except BootstrapError as error:
        error.mutation_possible = error.mutation_possible or publishing
        raise
    except (ModelError, ValueError, TypeError, KeyError, RecursionError) as error:
        raise BootstrapError('bundle_bootstrap_journal_invalid') from error
    except FileNotFoundError as error:
        raise BootstrapError('bootstrap_inventory_changed', path=STAGING,
                             mutation_possible=publishing) from error
    except OSError as error:
        raise BootstrapError('bootstrap_recovery_io', exit_code=5, path=STAGING,
                             mutation_possible=publishing) from error
    finally:
        tree.close()


def _check_names(held, tree):
    held.require_held()
    locations = tree.checked_locations()
    expected = {p for p, moved in locations.items() if moved}
    if tree.stage_parts == (STAGING,): expected.add(STAGING)
    if set(os.listdir(held.root_fd)) != expected:
        raise BootstrapError('bundle_extraction_target_changed')


def _publish(container, target, *, cwd=None, recheck_input=lambda: None):
    parent, target = root_destination(target, cwd=cwd, invalid_reason='bundle_extraction_target_invalid')
    content = {**container.files, MANIFEST_NAME: container.manifest_bytes}
    directories = _directories(content)
    function = rename_function()
    tree = None
    with ExitStack() as stack:
        parent_held = stack.enter_context(LockFiles(parent)); parent_held.acquire()
        destination = BootstrapRoot(parent_held, target)
        recheck_input()
        try:
            if destination.current is None:
                destination.create()
            held = destination.acquire(stack)
            def guard(tree):
                parent_held.require_held()
                _check_names(held, tree)
                recheck_input()
            recovered = False if destination.created else _recover(held, function, content, directories, guard)
            if not recovered:
                if os.listdir(held.root_fd):
                    raise BootstrapError('bundle_extraction_target_not_empty')
                tree = BootstrapTree(held, function, {}, completed=COMPLETED)
                tree.create()
                tree.prepare(content, directories, destination.created, journal_format=FORMAT)
                guard(tree)
                tree.publish(guard=lambda: guard(tree))
                tree.cleanup()
                guard(tree)
        except BaseException as original:
            destination.rollback(tree, original)
            raise
        finally:
            if tree is not None: tree.close()
    return target, content, directories


def extract_bundle(raw, target, *, expected_sha256=None, cwd=None, _recheck_input=lambda: None):
    """Materialize only a verified inventory, retaining the original manifest.

    A partial is not a normal ProjectSource; its permitted reader integration
    remains separate. No receipt import, source authentication or approval.
    """
    verified = verify_bundle(raw, expected_sha256=expected_sha256)
    container = BundleContainer(raw, expected_sha256=expected_sha256)
    target, content, directories = _publish(container, target, cwd=cwd, recheck_input=_recheck_input)
    result = {'format_version': 'bundle-extract-v1', 'project_root': str(target),
        'manifest': container.manifest, 'file': verified['file'],
        'validation_scope': verified['validation_scope'], 'bootstrap_state': 'complete',
        'external_hash_verified': verified['external_hash_verified'],
        'creator_authenticated': False, 'approval_granted': False, 'full_semantic_validation': False,
        'files': [{'path': p, 'size': len(b), 'sha256': sha256(b).hexdigest()} for p, b in sorted(content.items())],
        'directories': sorted(directories)}
    validate_result_document('bundle-extract-v1', result)
    return result
