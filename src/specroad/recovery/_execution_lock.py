"""Restore-specific owner binding on the existing native mutex and file primitives."""
from base64 import b64encode
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from uuid import uuid4

from ..changes._lock_files import LockFiles, identity
from ..changes._lock_process import LinuxOwnerProbe
from ..changes._lock_owner_policy import _recovery_permitted
from ..changes._recovery_bytes import fingerprint_recovery_file
from ..changes._publication_io import publish_recovery_owner
from ..changes.lock_values import LOCK_VERSION, LockRecord, text
from ..changes.locking import HeldProjectLock, _bound, project_lock
from ..model.canonical import canonical_json_bytes
from ._execution_events import event_files, owner_binding
from ._execution_store import RestoreStore
from .values import require, RestoreError


def takeover_options(force, expected_lock_sha256, reason, accept_remote_risk):
    require(type(force) is bool and type(accept_remote_risk) is bool,
            'restore_takeover_options_invalid', exit_code=2)
    requested = force or expected_lock_sha256 is not None or reason is not None or accept_remote_risk
    if requested:
        require(force and type(expected_lock_sha256) is str and len(expected_lock_sha256) == 64
                and all(c in '0123456789abcdef' for c in expected_lock_sha256) and reason is not None,
                'restore_takeover_options_required', exit_code=2)
        text(reason)
    return requested


@contextmanager
def restore_lock(project, plan, layout, expected, *, authority, actor, refresh, authorize,
                 progress, resuming, force, expected_lock_sha256, reason, accept_remote_risk,
                 owner_probe=None, source_check=lambda: None):
    request = layout['binding']['request']
    with LockFiles(project.root) as observed:
        old, _ = observed.read_record()
    if old is None:
        require(not force, 'restore_expected_owner_missing', exit_code=6)
        def before(files):
            refresh(files)
            progress['mutation_possible'] = True
        with project_lock(project.root, kind='recovery', command='recover restore',
                project_id=request['project_id'], transaction_id='restore-' + layout['token'],
                request_id=request['request_id'], _before_record=before) as held:
            store = RestoreStore(held, plan, layout, expected=expected)
            store.check()
            yield store
        return
    if not force:
        raise RestoreError('restore_owner_recovery_required', exit_code=5, recovery_required=True)
    probe = LinuxOwnerProbe() if owner_probe is None else owner_probe
    with LockFiles(project.root) as files:
        files.acquire()
        old, old_inode = files.read_record()
        require(old is not None and old.sha256 == expected_lock_sha256,
                'restore_owner_changed', exit_code=6)
        _bound(old, files, request['project_id'])
        location = 'terminal' if layout['terminal'] in expected else 'active'
        if resuming:
            require(layout['active'] in files.journal_entries() or location == 'terminal',
                    'restore_owner_execution_missing', exit_code=5)
        binding = owner_binding(old, layout, resuming=resuming and old.data['command'] == 'recover restore')
        refresh(files)
        state = _recovery_permitted(old, probe, accept_remote_risk)
        takeover = {'action': 'takeover', 'command': 'recover restore',
            'project_id': request['project_id'], 'root_identity': request['root_identity'],
            'restore_request': request, 'actor': actor.as_fields(), 'lock_record': old.data,
            'lock_sha256': old.sha256, 'observed_owner_state': state, 'reason': reason,
            'force': True, 'accept_remote_risk': accept_remote_risk, 'binding': binding}
        authorize(authority, takeover)
        old_guard = HeldProjectLock(files, old, old_inode)
        store = RestoreStore(old_guard, plan, layout, expected=expected)
        store.check()
        new = LockRecord(canonical_json_bytes({'format_version': LOCK_VERSION,
            'kind': 'recovery', 'lock_id': str(uuid4()), 'project_id': request['project_id'],
            'root_identity': identity(os.fstat(files.root_fd)), **LinuxOwnerProbe().current().as_dict(),
            'created_at': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
            'command': 'recover restore', 'request_id': request['request_id'],
            'transaction_id': 'restore-' + layout['token']}))
        details = {'authority_id': authority.authority_id, 'authority_version': authority.version,
            'request': takeover, 'old_bytes': b64encode(old.source_bytes).decode('ascii'),
            'new_bytes': b64encode(new.source_bytes).decode('ascii')}
        own, _ = event_files(layout, new.data['lock_id'], 'takeovers', details, location=location)
        store.own = {**store.own, **own}
        prefix = layout[location] + '/takeovers/' + new.data['lock_id']

        def unchanged():
            store.check()
            current, inode = files.read_record()
            require(current is not None and current.source_bytes == old.source_bytes and inode == old_inode,
                    'restore_owner_changed', exit_code=6)
            require(_recovery_permitted(current, probe, accept_remote_risk) == state,
                    'restore_owner_observation_changed', exit_code=6)

        unchanged()
        progress['mutation_possible'] = True
        for name in ('intent.json', 'owner.before.json', 'owner.pending.json'):
            path = prefix + '/' + name
            store.create(path, own[path])
        authorize(authority, takeover)
        unchanged()
        source_check()
        pending = prefix + '/owner.pending.json'
        token = fingerprint_recovery_file(files, pending)

        def before_replace():
            unchanged()
            source_check()

        with files.directory(prefix.split('/')) as staged:
            with files.directory(('.specroad', 'locks')) as locks:
                require(staged is not None and locks is not None, 'restore_owner_directory_changed', exit_code=6)
                publish_recovery_owner(staged, locks, size=len(new.source_bytes),
                    digest=new.sha256, identity=token['identity'], before_replace=before_replace)
        current, inode = files.read_record()
        require(current is not None and current.source_bytes == new.source_bytes and inode == token['identity'],
                'restore_owner_changed', exit_code=6)
        held = HeldProjectLock(files, current, inode)
        store.held = held
        del store.expected[pending]
        store.check()
        store.create(prefix + '/completed.json', own[prefix + '/completed.json'])
        try:
            yield store
        finally:
            if os.getpid() == held._pid:
                try:
                    held.check()
                    files.remove_record(held.record, held._inode)
                finally:
                    held._active = False
