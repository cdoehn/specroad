"""Create a minimum project without treating a new root as an existing Change Plan."""
from contextlib import ExitStack
from hashlib import sha256
import os
from pathlib import Path
import stat
import sys

from ..changes._lock_files import LockFiles
from ..changes.lock_values import ProjectLockError
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..cli.result_schemas import validate_result_document
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..security import paths as guards
from ._bootstrap_io import (BootstrapError, BootstrapTree, STAGING, directory,
                            identity, info_at, metadata, rename_function)
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
    if not isinstance(path, (str, Path)) or not str(path) or '\0' in str(path):
        raise BootstrapError('bootstrap_path_invalid', exit_code=2)
    if not sys.platform.startswith('linux') or not guards._HAS_SAFE_OPEN:
        raise BootstrapError('bootstrap_platform_unavailable', exit_code=5)
    requested = Path(path)
    if not requested.is_absolute(): requested = (Path.cwd() if cwd is None else Path(cwd)) / requested
    # Normalize lexical dots without resolving the target itself through a link.
    requested = Path(os.path.abspath(requested))
    if requested == requested.parent:
        raise BootstrapError('bootstrap_root_destination_invalid', exit_code=2)
    parent = requested.parent.resolve(strict=True)
    target = parent / requested.name
    function = rename_function()
    created = False; created_identity = None; tree = None; rollback_complete = False
    with ExitStack() as stack:
        parent_held = stack.enter_context(LockFiles(parent)); parent_held.acquire()
        current = info_at(parent_held.root_fd, target.name)
        if current is not None: guards._regular(current, directory=True)
        try:
            if current is None:
                content, directories, configuration, document_id = initial_content(target.name)
                os.mkdir(target.name, mode=0o755, dir_fd=parent_held.root_fd)
                created = True
                created_identity = identity(os.stat(target.name, dir_fd=parent_held.root_fd, follow_symlinks=False))
                os.fsync(parent_held.root_fd)
            held = stack.enter_context(LockFiles(target)); held.acquire()
            expected_identity = created_identity if created else identity(current)
            if identity(os.fstat(held.root_fd)) != expected_identity:
                raise BootstrapError('bootstrap_root_changed')
            _portable_names(held)
            recovered = None if created else recover_bootstrap(held, function, target.name)
            if recovered is not None:
                content, directories, configuration, document_id = recovered
            else:
                reused = _preflight(held)
                if not created:
                    content, directories, configuration, document_id = initial_content(target.name)
                tree = BootstrapTree(held, function, reused)
                tree.create()
                tree.prepare(content, directories, created)
                tree.publish()
                tree.cleanup()
        except BaseException as original:
            if tree is not None and tree.fd is not None:
                try:
                    tree.cleanup()
                    rollback_complete = not tree.committed
                except (BootstrapError, ProjectLockError, SafetyViolation, OSError):
                    raise BootstrapError('bootstrap_recovery_required', path=STAGING,
                                         mutation_possible=True) from original
            elif tree is None:
                rollback_complete = True
            if created and rollback_complete:
                parent_held.require_held()
                now = info_at(parent_held.root_fd, target.name)
                if now is not None and identity(now) == created_identity:
                    with directory(parent_held.root_fd, (target.name,)) as fd:
                        if os.listdir(fd):
                            raise BootstrapError('bootstrap_root_not_empty', mutation_possible=True) from original
                    os.rmdir(target.name, dir_fd=parent_held.root_fd)
                    os.fsync(parent_held.root_fd)
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
    try:
        payload = initialize_project(invocation.arguments.get('path', '.'),
                                     cwd=invocation.resolved.working_directory)
    except BootstrapError as error:
        raise OperationFailure(FailureKind(error.exit_code), 'Project initialization did not complete.',
            details={'bootstrap': {'reason': error.reason, 'path': error.path,
                                    'mutation_possible': error.mutation_possible}}) from error
    except ProjectLockError as error:
        raise OperationFailure(FailureKind(error.exit_code), 'Bootstrap lock unavailable.',
                               details={'bootstrap': {'reason': error.reason}}) from error
    except SafetyViolation as error:
        raise OperationFailure(FailureKind.SECURITY, 'Unsafe bootstrap destination.') from error
    except ModelError as error:
        raise OperationFailure(FailureKind.MODEL, 'Invalid initialization resource.',
                               details={'bootstrap': error.diagnostic()}) from error
    return CommandResult('init', result=payload)
