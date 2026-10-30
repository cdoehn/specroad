"""Confirm the native Restore unit under one retained external Work lease.

The result-delivery unit remains pending. This embedding API neither registers
a public resume command nor treats passive Work evidence as project authority.
"""
from dataclasses import dataclass
from pathlib import Path

from ..changes.recovery_values import RecoveryAuthority
from ..model.canonical import canonical_json_bytes
from ..recovery._execution_lock import takeover_options
from ..recovery.values import RestoreError, guarded, persisted_contract, require
from ..storage.json_syntax import parse_json_object
from .checkpoints import CheckpointStore
from .manifest import _bytes, partition_work_manifest
from .restore_execution import _bound, _build, _checked, _native_held
from .restore_owner import _held, _recover, _history
from ._restore_owner_files import HandoffFiles


_COMPLETION = frozenset(('format_version', 'request_sha256', 'request', 'result',
    'expected_target_root', 'backup_manifest_sha256', 'authority_id', 'authority_version',
    'historical_findings'))


class RestoreWorkProgressError(RestoreError):
    """Retain possible Work effects separately from native project effects."""
    def __init__(self, error, progress):
        super().__init__(error.reason, path=error.path, exit_code=error.exit_code,
            mutation_possible=error.mutation_possible or progress['mutation_possible'],
            recovery_required=error.recovery_required or progress['recovery_required'])
        self.work_mutation_possible = progress['writes']
        self.owner_recovery_required = progress['owner']

    def diagnostic(self):
        return {**super().diagnostic(), 'work_mutation_possible': self.work_mutation_possible,
                'owner_recovery_required': self.owner_recovery_required}


@dataclass(frozen=True, init=False)
class RestoreWorkProgress:
    manifest: object
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use advance_restore_work')

    def as_dict(self):
        return parse_json_object(self._raw)

    def __bool__(self):
        raise TypeError('Inspect native Restore and pending delivery separately')


def _evidence(initial, unit_id, completion):
    return canonical_json_bytes({'format_version': 'restore-work-transaction-v1',
        'work_id': initial.as_dict()['work_id'], 'unit_id': unit_id,
        'initial_checkpoint_sha256': initial.as_dict()['checkpoint_sha256'],
        'tool_build': initial.as_dict()['tool_build'], 'completion': completion})


def _progress(current, initial, registry, build):
    current, raw = _bound(current, registry, build)
    value = current.as_dict()
    require(value['state'] == 'running' and not value['result_parts']
            and not value['diagnostic_parts'], 'restore_work_pending_delivery_required', exit_code=6)
    done = current.entries('completed')
    unit = current.entries('tasks')[0]['unit_id']
    require(value['checkpoint_generation'] == len(done) and len(done) <= 1
            and (not done or done[0]['unit_id'] == unit),
            'restore_work_progress_conflict', exit_code=6)
    if not done:
        return current, raw, unit, None
    evidence = _bytes(done[0]['evidence'], current.objects)
    record = parse_json_object(evidence)
    completion = record.get('completion')
    require(type(completion) is dict and set(completion) == _COMPLETION
            and completion['format_version'] == 'restore-completion-v1'
            and completion['result'] == 'restored', 'restore_work_completion_invalid')
    require(_evidence(initial, unit, completion) == evidence,
            'restore_work_evidence_binding_conflict', exit_code=6)
    # The complete native comparison occurs before any project write. This
    # stored attribution/request is never used as a current actor or authority.
    return current, raw, unit, canonical_json_bytes(completion)


def advance_restore_work(store, *, registry, authority, actor, force=False,
                         expected_lock_sha256=None, reason=None, accept_remote_risk=False,
                         owner_probe=None, expected_work_lock_sha256=None,
                         work_recovery_reason=None, work_owner_probe=None, services=None):
    """Execute/recover once, recording only a proven successful native unit.

    A partial native publication rolls back and leaves Work unchanged. An
    already confirmed unit requires its original native completion again; lost
    native evidence cannot start a second publication. Current outer and project
    owner consents remain independent and are never copied into Work bindings.
    """
    return _run(store, registry=registry, authority=authority, actor=actor,
        force=force, expected_lock_sha256=expected_lock_sha256, reason=reason,
        accept_remote_risk=accept_remote_risk, owner_probe=owner_probe,
        expected_work_lock_sha256=expected_work_lock_sha256,
        work_recovery_reason=work_recovery_reason, work_owner_probe=work_owner_probe,
        finish=False, services=services)


def resume_restore_work(store, *, registry, authority=None, actor=None, force=False,
                        expected_lock_sha256=None, reason=None, accept_remote_risk=False,
                        owner_probe=None, expected_work_lock_sha256=None,
                        work_recovery_reason=None, work_owner_probe=None, services=None):
    """Complete native execution and delivery, or read an already saved result.

    Unfinished Work requires fresh independent native authority. Terminal Work
    uses only its checked saved bytes: it does not recheck or change the project.
    This is a host API, not public command registration or a resume loop.
    """
    return _run(store, registry=registry, authority=authority, actor=actor,
        force=force, expected_lock_sha256=expected_lock_sha256, reason=reason,
        accept_remote_risk=accept_remote_risk, owner_probe=owner_probe,
        expected_work_lock_sha256=expected_work_lock_sha256,
        work_recovery_reason=work_recovery_reason, work_owner_probe=work_owner_probe,
        finish=True, services=services)


def _run(store, **options):
    progress = {'writes': False, 'owner': False,
                'mutation_possible': False, 'recovery_required': False}
    try:
        return _advance(store, **options, progress=progress)
    except RestoreError as error:
        held = progress.get('held')
        if held is not None and held._owner_released:
            progress['owner'] = False
        raise RestoreWorkProgressError(error, progress) from error


@guarded
@persisted_contract
def _advance(store, *, registry, authority, actor, force, expected_lock_sha256, reason,
             accept_remote_risk, owner_probe, expected_work_lock_sha256,
             work_recovery_reason, work_owner_probe, progress, finish, services):
    require(type(store) is CheckpointStore, 'restore_trusted_work_store_required', exit_code=2)
    if not finish:
        require(type(authority) is RecoveryAuthority, 'restore_authority_required', exit_code=2)
    require(store._initial.as_dict()['command_id'] == 'recover.restore',
            'restore_work_command_invalid', exit_code=2)
    takeover_options(force, expected_lock_sha256, reason, accept_remote_risk)
    build = _build()
    initial, raw = _checked(store._initial, registry, build)
    require(initial.as_dict()['checkpoint_generation'] == 0,
            'restore_initial_work_required', exit_code=6)
    plan = parse_json_object(raw)
    require(store._location.protects(Path(plan['project_root'])),
            'restore_work_unprotected_project', exit_code=7)

    def advance(held, handoff=None):
        progress['held'] = held
        progress['owner'] = held._owner is not None
        origin = Path(plan['source']['root'])
        require(not held.path.is_relative_to(origin) and not origin.is_relative_to(held.path),
                'restore_work_source_overlap', exit_code=7)
        pointer = store._pointer(held)
        require(pointer is not None, 'restore_published_work_required', exit_code=5)
        from . import restore_delivery
        reader = restore_delivery.checked_progress if finish else _progress
        current, original, unit, saved = reader(
            store._read_chain(held, pointer[0]), initial, registry, build)
        history = HandoffFiles(held)
        require(not _history(history, held, store, pointer),
                'restore_work_handoff_unresolved')
        if finish and current.as_dict()['state'] == 'completed':
            require(held._owner is None or handoff is not None,
                    'restore_work_owner_recovery_required', exit_code=5)
            document, references = restore_delivery.completed(
                store, held, current, pointer, build, history)
            return restore_delivery.result(store, registry, current, document, references,
                                           finalized=False, handoff=handoff)
        require(type(authority) is RecoveryAuthority, 'restore_authority_required', exit_code=2)
        if handoff is None:
            require(held._owner is None, 'restore_work_owner_recovery_required', exit_code=5)
            progress.update(writes=True, owner=True)
            held._claim_owner()
        outcome = _native_held(store, held, current, original, pointer, registry=registry,
            build=build, authority=authority, actor=actor, force=force,
            expected_lock_sha256=expected_lock_sha256, reason=reason,
            accept_remote_risk=accept_remote_risk, owner_probe=owner_probe,
            progress=progress, expected_completed_bytes=saved, work_guard=history.check,
            services=services)
        native = outcome.data
        confirmed = current
        if native['result'] == 'restored':
            require(native['recovery_required'] is False,
                    'restore_work_native_completion_required', exit_code=6)
            completion = {key: native[key] for key in _COMPLETION}
            if saved is None:
                candidate = partition_work_manifest(current, {unit: _evidence(initial, unit, completion)})
                require(_build() == build, 'restore_work_build_changed', exit_code=6)
                progress['writes'] = True
                confirmed = store._publish_held(held, candidate, pointer)
            else:
                require(saved == canonical_json_bytes(completion),
                        'restore_work_completion_changed', exit_code=6)
            if finish:
                confirmed, document, references = restore_delivery.finish(store, held,
                    confirmed, store._pointer(held), native, build, history, progress)
                return restore_delivery.result(store, registry, confirmed, document, references,
                                               finalized=True, handoff=handoff)
        require(_build() == build, 'restore_work_build_changed', exit_code=6)
        history.check()
        value = confirmed.as_dict()
        result = object.__new__(RestoreWorkProgress)
        object.__setattr__(result, 'manifest', confirmed)
        object.__setattr__(result, '_raw', canonical_json_bytes({
            'format_version': 'restore-work-progress-v1', 'work_id': value['work_id'],
            'checkpoint_generation': value['checkpoint_generation'],
            'checkpoint_sha256': value['checkpoint_sha256'], 'work_state': value['state'],
            'checkpoint_changed': confirmed is not current, 'progress': value['progress'],
            'work_completion_recorded': False, 'next_action': value['next_action'],
            'owner_handoff': None if handoff is None else handoff.as_dict(), 'restore': native}))
        return result

    if expected_work_lock_sha256 is not None or work_recovery_reason is not None:
        result = _recover(store, registry, expected_work_lock_sha256, work_recovery_reason,
                          work_owner_probe, progress, continuation=advance)
    else:
        with _held(store._location) as held:
            result = advance(held)
    progress['owner'] = False
    return result
