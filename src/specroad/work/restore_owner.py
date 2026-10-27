"""Explicit native recovery of an orphan outer Restore Work owner only.

This embedding API never executes Restore, publishes Work progress or grants
project recovery authority. The host supplies an independent CheckpointStore
and fresh consent. Stored audit records are observations, never consent.
"""
from dataclasses import dataclass
from contextlib import contextmanager
import os
from pathlib import Path
import re
import secrets

from ..changes._lock_process import LinuxOwnerProbe
from ..changes.lock_values import OwnerIdentity
from ..changes._publication_io import replace_bound_image
from ..changes._staging_files import _write_new
from ..model.canonical import canonical_json_bytes
from ..recovery.values import RestoreError, guarded, persisted_contract, require
from ..security import paths as guards
from ..storage.json_syntax import parse_json_object
from .checkpoints import CheckpointStore, CheckpointStorageError
from ._root_lock import WorkBindingViolation
from .manifest import _bytes
from .restore import read_restore_work_manifest
from .restore_execution import _build
from ._restore_owner_files import HandoffFiles
from ._restore_owner_records import (blob, digest, owner, file_binding,
    read_file_binding, read_intent, completion, unblob)


class RestoreWorkOwnerError(RestoreError):
    """External Work effects are distinct from native project Restore writes."""
    def __init__(self, error, progress):
        super().__init__(error.reason, path=error.path, exit_code=error.exit_code)
        self.work_mutation_possible = progress['writes']
        self.owner_recovery_required = progress['owner']

    def diagnostic(self):
        return {**super().diagnostic(), 'work_mutation_possible': self.work_mutation_possible,
                'owner_recovery_required': self.owner_recovery_required}


@dataclass(frozen=True, init=False)
class RestoreWorkOwnerRecovery:
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use recover_restore_work_owner')

    def as_dict(self):
        return parse_json_object(self._raw)

    def __bool__(self):
        raise TypeError('Inspect the outer Work owner outcome explicitly')


def _observe(probe, previous):
    current = probe.current()
    require(type(current) is OwnerIdentity and current.process_id == os.getpid()
            and current.host_id is not None and current.process_start_id is not None
            and current.host_id == previous.host_id
            and previous.process_start_id is not None,
            'restore_work_owner_unverifiable', exit_code=5)
    state, start = probe.process(previous.process_id)
    require((state == 'absent' and start is None)
            or (state in ('alive', 'dead') and type(start) is str and bool(start)
                and (state == 'dead' or start != previous.process_start_id)),
            'restore_work_owner_not_dead', exit_code=5)
    return current, {'host_id': current.host_id, 'state': state, 'process_start_id': start}


@contextmanager
def _held(location):
    try:
        with location.inspect_checkpoint() as held:
            yield held
    except WorkBindingViolation as error:
        raise RestoreError('restore_work_binding_changed', exit_code=6) from error
    except CheckpointStorageError as error:
        conflict = error.reason in ('checkpoint_binding_changed', 'checkpoint_bytes_changed',
                                     'checkpoint_pointer_changed')
        raise RestoreError(error.reason, path=error.path, exit_code=6 if conflict else 3) from error


def _history(files, held, store, pointer):
    records = files.load()
    intents, completed = {}, set()
    for name, raw in records.items():
        require(re.fullmatch('[0-9a-f]{64}(?:\\.complete)?\\.json', name) is not None,
                'restore_work_handoff_name_invalid')
        if not name.endswith('.complete.json'):
            key = digest(raw)
            require(name == key + '.json', 'restore_work_handoff_hash_changed', exit_code=6)
            intents[key] = read_intent(raw, held, store)
    for name, raw in records.items():
        if name.endswith('.complete.json'):
            key = name[:64]
            require(key in intents, 'restore_work_handoff_intent_missing')
            require(raw == completion(records[key + '.json'], intents[key]),
                    'restore_work_handoff_completion_changed', exit_code=6)
            completed.add(key)
    old_completed = [read_file_binding(intents[k]['old_owner']) for k in completed]
    new_owners = [read_file_binding(v['new_owner']) for v in intents.values()]
    require(len(set(old_completed)) == len(old_completed)
            and len(set(new_owners)) == len(new_owners), 'restore_work_handoff_ambiguous')
    if held._owner is not None and parse_json_object(held._owner[0])['format_version'] == 'restore-work-lock-v1':
        # A replacement owner is distinguishable from an ordinary checkpoint
        # owner even if the entire required handoff directory has disappeared.
        require(new_owners.count(held._owner) == 1, 'restore_work_handoff_intent_missing')
    pending = []
    for key, value in intents.items():
        if key in completed:
            continue
        old, new = (read_file_binding(value[k]) for k in ('old_owner', 'new_owner'))
        if new == held._owner:
            require(unblob(value['checkpoint']) == pointer[0],
                    'restore_work_handoff_checkpoint_changed', exit_code=6)
            pending.append((key + '.complete.json', completion(records[key + '.json'], value)))
        else:
            require(old == held._owner or old in old_completed,
                    'restore_work_handoff_unresolved')
    require(len(pending) <= 1, 'restore_work_handoff_ambiguous')
    return pending


def recover_restore_work_owner(store, *, registry, expected_work_lock_sha256, reason,
                               owner_probe=None):
    """Recover only a proven dead local owner, preserving all actual old bytes.

    ``owner_probe`` is a trusted host/test adapter, never a deserialized task.
    The installed Linux adapter is the default. Every further owner transition
    requires new consent and fresh process evidence, including after a crash.
    """
    progress = {'writes': False, 'owner': False}
    try:
        return _recover(store, registry, expected_work_lock_sha256, reason, owner_probe, progress)
    except RestoreError as error:
        raise RestoreWorkOwnerError(error, progress) from error


@guarded
@persisted_contract
def _recover(store, registry, expected, reason, probe, progress, continuation=None):
    require(type(store) is CheckpointStore, 'restore_trusted_work_store_required', exit_code=2)
    require(type(expected) is str and re.fullmatch('[0-9a-f]{64}', expected) is not None
            and type(reason) is str and bool(reason.strip()),
            'restore_work_owner_explicit_pair_required', exit_code=2)
    try:
        reason.encode('utf-8')
    except UnicodeError as error:
        raise RestoreError('restore_work_owner_explicit_pair_required', exit_code=2) from error
    require(store._initial.as_dict()['command_id'] == 'recover.restore',
            'restore_work_owner_command_invalid', exit_code=2)
    build = _build()
    require(store._initial.as_dict()['tool_build'] == build,
            'restore_work_build_changed', exit_code=6)
    initial = read_restore_work_manifest(store._initial.raw, store._initial.objects,
        registry=registry, expected_tool_build=build)
    plan = parse_json_object(_bytes(initial.as_dict()['plan_binding']['plan_source'], initial.objects))
    require(any(b.root == Path(plan['project_root']) for b in store._location._protected),
            'restore_work_unprotected_project', exit_code=7)
    probe = LinuxOwnerProbe() if probe is None else probe
    with _held(store._location) as held:
        origin = Path(plan['source']['root'])
        require(not held.path.is_relative_to(origin) and not origin.is_relative_to(held.path),
                'restore_work_source_overlap', exit_code=7)
        require(held._owner is not None, 'restore_work_expected_owner_missing', exit_code=6)
        progress['owner'] = True
        old = held._owner
        require(digest(old[0]) == expected, 'restore_work_owner_hash_changed', exit_code=6)
        previous = owner(old[0], held.work_id)
        pointer = store._pointer(held)
        require(pointer is not None, 'restore_published_work_required')
        current = store._read_chain(held, pointer[0])
        read_restore_work_manifest(current.raw, current.objects, registry=registry, expected_tool_build=build)
        files = HandoffFiles(held)
        pending = _history(files, held, store, pointer)

        def unchanged():
            held.check()
            require(_build() == build, 'restore_work_build_changed', exit_code=6)
            require(store._pointer(held) == pointer, 'restore_work_pointer_changed', exit_code=6)
            require(store._read_chain(held, pointer[0]).raw == current.raw,
                    'restore_work_bytes_changed', exit_code=6)
            require(store._pointer(held) == pointer, 'restore_work_pointer_changed', exit_code=6)
            files.check()

        new_identity, observation = _observe(probe, previous)
        unchanged()
        # Completing a proven installed prior transition does not reuse consent.
        for name, raw in pending:
            progress['writes'] = True
            files.write(name, raw)
        new_raw = canonical_json_bytes({'format_version': 'restore-work-lock-v1', 'work_id': held.work_id,
            'owner_nonce': secrets.token_hex(16), **new_identity.as_dict()})
        temporary = '.restore-owner-' + secrets.token_hex(16) + '.tmp'
        unchanged()
        progress['writes'] = True
        new_inode = _write_new(held._children[0], temporary, new_raw)
        value = {'format_version': 'restore-work-owner-handoff-v1',
            'root_binding': parse_json_object(held._binding), 'checkpoint': blob(pointer[0]),
            'old_owner': file_binding(*old), 'new_owner': file_binding(new_raw, new_inode),
            'observation': observation, 'reason': reason.strip()}
        raw = canonical_json_bytes(value)
        key = digest(raw)
        files.write(key + '.json', raw)

        def before_replace():
            require(_observe(probe, previous) == (new_identity, observation),
                    'restore_work_owner_observation_changed', exit_code=5)
            unchanged()

        def after_replace(info):
            # Adopt actual installed bytes before directory sync can fail. Keep
            # inspection cleanup disabled until the completion is durable.
            held._owner = (new_raw, guards._identity(info))

        replace_bound_image(held._children[0], temporary, held._root, 'work-lock.json',
            size=len(new_raw), digest=digest(new_raw), identity=new_inode,
            source_changed=lambda: RestoreError('restore_work_new_owner_changed', exit_code=6),
            before_replace=before_replace, after_replace=after_replace)
        unchanged()
        files.write(key + '.complete.json', completion(raw, value))
        unchanged()
        # Normal lease cleanup can now remove only this exact fully evidenced owner.
        held._inspection = False
        result = object.__new__(RestoreWorkOwnerRecovery)
        object.__setattr__(result, '_raw', canonical_json_bytes({
            'format_version': 'restore-work-owner-recovery-v1', 'work_id': held.work_id,
            'handoff_sha256': key, 'old_owner_sha256': expected, 'new_owner_sha256': digest(new_raw),
            'checkpoint_generation': current.as_dict()['checkpoint_generation'],
            'checkpoint_sha256': current.as_dict()['checkpoint_sha256'], 'checkpoint_changed': False,
            'project_mutation_possible': False, 'work_completion_recorded': False}))
        if continuation is not None:
            # Installed Core continuation, never deserialized Work input. The
            # same mutex and fully evidenced owner remain held until it exits.
            result = continuation(held, result)
    progress['owner'] = False
    return result
