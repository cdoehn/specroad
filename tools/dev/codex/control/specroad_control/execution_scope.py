"""One execution directory and write policy for both existing-thread transports."""
from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING
from .errors import ControlError

if TYPE_CHECKING:
    from .config import Config


def execution_directory(config: Config) -> Path:
    """The existing explicit workspace is authoritative for new turns."""
    target = config.thread_cwd
    if target is None:
        return config.repository
    try:
        repo = config.repository.resolve()
        if (not target.is_absolute() or target != target.resolve()
                or target not in (repo, repo.parent)
                or any(p.is_symlink() or not p.is_dir() for p in (target, *target.parents))):
            raise ValueError
    except (OSError, RuntimeError, ValueError):
        raise ControlError('invalid_thread_workspace',
                           'The configured thread workspace changed or is not a canonical Dev/workspace directory.') from None
    return target


def writable_roots(config: Config) -> list[str]:
    return [str(execution_directory(config)), str(config.exchange)]


def policy(config, *, readonly=False):
    # Full access is an explicit operator choice, including visibility probes:
    # Codex turn overrides persist into subsequent manual and automatic turns.
    if config.access_mode not in ('workspace-write', 'full-access'):
        raise ControlError('invalid_access_mode', 'Select workspace-write or full-access explicitly.')
    if config.access_mode == 'full-access':
        return {'approvalPolicy': 'never', 'sandboxPolicy': {'type': 'dangerFullAccess'}}
    if readonly:
        return {'approvalPolicy': 'never', 'sandboxPolicy': {'type': 'readOnly'}}
    return {'approvalPolicy': 'never', 'sandboxPolicy': {
        'type': 'workspaceWrite', 'writableRoots': writable_roots(config),
        'networkAccess': False}}


def exec_policy_options(config, *, readonly=False):
    """Encode the same policy for exec resume; do not mix sandbox modes."""
    turn_policy = policy(config, readonly=readonly)
    sandbox = turn_policy['sandboxPolicy']
    mode = {'readOnly': 'read-only', 'workspaceWrite': 'workspace-write',
            'dangerFullAccess': 'danger-full-access'}[sandbox['type']]
    args = ["-c", 'approval_policy="never"', "-c", 'sandbox_mode=' + json.dumps(mode)]
    if sandbox['type'] == 'workspaceWrite':
        args.extend(["-c", "sandbox_workspace_write.writable_roots=" + json.dumps(sandbox['writableRoots'])])
    if sandbox['type'] != 'dangerFullAccess':
        args.extend(["-c", "sandbox_workspace_write.network_access=false"])
    return args
