"""Exact retained sibling bootstrap observations, never bootstrap recovery."""
from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path

from ..model.errors import ModelError
from ..force_operations import current, selected_owner, permit
from ._guarded_io import _read_path
from .write_guard_values import require

PREFIXES = ('@bootstrap-root/', '@bootstrap-container/')
OWNER_KEYS = ('bootstrap-root.owner', 'bootstrap-container.owner')


def targets(root):
    root = Path(root)
    yield '@bootstrap-root/', root
    if root.name == 'project':
        yield '@bootstrap-container/', root.parent


@contextmanager
def addressed(files, path):
    """Resolve only two compiled sibling names; no caller-controlled traversal."""
    from ._lock_files import LockFiles
    from ..authoring.bootstrap_guard import names
    for prefix, target in targets(files.boundary.root):
        if path.startswith(prefix):
            suffix = path[len(prefix):]
            require(suffix in ('pending.json', 'owner.json'), 'bootstrap_observation_address', exit_code=6)
            name = names(target)[suffix == 'owner.json']
            with LockFiles(target.parent) as parent:
                yield parent, name
            return
    require(not path.startswith('@bootstrap-'), 'bootstrap_observation_address', exit_code=6)
    yield files, path


def observe(files):
    from ._lock_files import LockFiles
    from ..authoring.bootstrap_guard import names
    values, identities = {}, {}
    for prefix, target in targets(files.boundary.root):
        with LockFiles(target.parent) as parent:
            for suffix, name in zip(('pending.json', 'owner.json'), names(target)):
                raw = _read_path(parent, name, optional=True)
                if raw is None: continue
                info = os.stat(name, dir_fd=parent.root_fd, follow_symlinks=False)
                path = prefix + suffix
                values[path] = raw
                identities[path] = (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)
    return values, identities


def check_selection(files, originals, decisions, selected):
    from ._lock_files import LockFiles, identity
    from ..authoring.bootstrap_guard import _record
    from ._lock_owner_policy import observe_owner
    from ._lock_process import LinuxOwnerProbe
    from types import SimpleNamespace
    choices = {r['path']: r['sha256'] for r in selected['owners']}
    for prefix, target in targets(files.boundary.root):
        key = prefix[1:-1] + '.owner'
        raw = originals.get(prefix + 'owner.json', originals.get(prefix + 'pending.json'))
        if raw is None:
            require(key not in choices, 'explicit_bootstrap_owner_changed', exit_code=6)
            continue
        with LockFiles(target.parent) as parent:
            try:
                _, owner = _record(raw, target, identity(os.fstat(parent.root_fd)))
                state = observe_owner(SimpleNamespace(owner=owner), LinuxOwnerProbe())
            except (ModelError, ValueError, KeyError, TypeError):
                state = 'unknown'
            with parent.observe_mutex() as busy:
                require(not (busy or state in ('alive', 'foreign', 'unverifiable', 'unknown') or key in choices)
                    or selected_owner(key, raw), 'explicit_bootstrap_owner_required', exit_code=6)
                decisions.decide(False, gate_id='write_marker:bootstrap_retained', diagnostic_code='CORE_SECURITY',
                    subject=key, operation='operational.force',
                    observed_binding={'sha256': sha256(raw).hexdigest(), 'owner_state': state,
                        'exclusive_access_proven': not busy}, requested_binding=selected,
                    effect='preserve_sibling_bootstrap_markers_execute_own_attempt')
                if busy:
                    permit(False, gate='lock:bootstrap_exclusivity', subject=key,
                        observed={'exclusive_access_proven': False}, requested=selected)


def permit_read(root, state):
    call = current()
    if call is None or not call.decisions.request.requested:
        return False
    from ._lock_files import LockFiles
    with LockFiles(root) as files:
        original, identities = observe(files)
        check_selection(files, original, call.decisions,
            {'owners': [{'path': p, 'sha256': h} for p, h in call.owners]})
        require(observe(files) == (original, identities), 'bootstrap_observation_changed', exit_code=6)
    return permit(False, gate='write_marker:bootstrap_read', subject='project', observed=state,
        requested='read_actual_retained_bytes', effect='observe_without_bootstrap_recovery')
