"""Create a minimum project without treating a new root as an existing Change Plan."""
from contextlib import ExitStack
from hashlib import sha256
import os
import stat

from ..changes._lock_files import LockFiles
from ..cli.result_schemas import validate_result_document
from ..security import SafetyViolation
from ..security import paths as guards
from ._bootstrap_io import (BootstrapError, BootstrapTree, STAGING, directory,
                            info_at, metadata, rename_function)
from ._bootstrap_root import BootstrapRoot, root_destination
from ._initial_content import ROOT_DIRECTORIES, initial_content
from ._bootstrap_recovery import recover_bootstrap


def _portable_names(held):
    held.require_held()
    names = os.listdir(held.root_fd)
    claimed = {'specroad.json', STAGING, *ROOT_DIRECTORIES}
    if any(name.casefold() in {p.casefold() for p in claimed} and name not in claimed for name in names):
        raise BootstrapError('bootstrap_portable_path_collision')


def _preflight(held):
    _portable_names(held)
    if info_at(held.root_fd, STAGING) is not None:
        raise BootstrapError('bootstrap_recovery_required', path=STAGING)
    reused = {}
    for name in ('specroad.json', *ROOT_DIRECTORIES):
        info = info_at(held.root_fd, name)
        if info is None: continue
        if stat.S_ISLNK(info.st_mode):
            raise SafetyViolation('Linked bootstrap destination')
        if name == 'specroad.json' or not stat.S_ISDIR(info.st_mode):
            raise BootstrapError('bootstrap_target_exists', path=name)
        guards._regular(info, directory=True)
        with directory(held.root_fd, (name,)) as fd:
            if os.listdir(fd):
                raise BootstrapError('bootstrap_target_not_empty', path=name)
            reused[name] = metadata(os.fstat(fd))
    return reused


def initialize_project(path='.', *, cwd=None):
    """Default de-DE/SR project on the currently supported native Linux filesystem.

    A missing final directory or a collision-free existing repository is allowed.
    Existing empty claimed root directories retain their identities. An unknown
    prior bootstrap is a conflict unless its complete journal, identities and
    actual bytes prove the exact prepared state or a published prefix of it.
    """
    parent, target = root_destination(path, cwd=cwd, invalid_reason='bootstrap_path_invalid')
    function = rename_function()
    tree = None
    with ExitStack() as stack:
        parent_held = stack.enter_context(LockFiles(parent)); parent_held.acquire()
        destination = BootstrapRoot(parent_held, target)
        try:
            if destination.current is None:
                content, directories, configuration, document_id = initial_content(target.name)
                destination.create()
            held = destination.acquire(stack)
            _portable_names(held)
            recovered = None if destination.created else recover_bootstrap(held, function, target.name)
            if recovered is not None:
                content, directories, configuration, document_id = recovered
            else:
                reused = _preflight(held)
                if not destination.created:
                    content, directories, configuration, document_id = initial_content(target.name)
                tree = BootstrapTree(held, function, reused)
                tree.create()
                tree.prepare(content, directories, destination.created)
                tree.publish()
                tree.cleanup()
        except BaseException as original:
            destination.rollback(tree, original)
            raise
        finally:
            if tree is not None: tree.close()
    payload = {'format_version': 'project-init-v1', 'project_root': str(target),
        'project_id': configuration.project_id, 'primary_document_id': document_id,
        'files': [{'path': p, 'size': len(raw), 'sha256': sha256(raw).hexdigest()} for p, raw in sorted(content.items())],
        'directories': sorted(directories), 'bootstrap_state': 'complete',
        'validation_scope': 'configuration_record_fields_and_distribution_bindings',
        'full_semantic_validation': False}
    validate_result_document('project-init-v1', payload)
    return payload


def initialize_command(invocation):
    """Keep the registered entry point while isolating CLI result projection."""
    from ._initialization_command import initialize_command as execute
    return execute(invocation)
