"""Run a bound Restore through its native journal, retaining the Work mutex.

This embedding adapter does not register a public command, publish progress or
finalize Work delivery. Its two pending units keep native execution and complete
result delivery explicit. Only installed code chooses the executor; neither a
stored task nor a registered command handler is invoked as executable input.
"""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from ..changes.recovery_values import RecoveryAuthority
from ..model.canonical import canonical_json_bytes
from ..recovery import execute_restore
from ..recovery.values import RestoreError, RestorePlan, guarded, persisted_contract, require
from ..storage.json_syntax import parse_json_object
from .checkpoints import CheckpointStore
from .manifest import _bytes
from .restore import create_restore_work_manifest, read_restore_work_manifest
from .resume import _runtime_build, WorkResumeError


def _build():
    try:
        return _runtime_build()
    except WorkResumeError as error:
        raise RestoreError(error.reason, exit_code=error.exit_code) from error


def _units(raw):
    return [{'key': key, 'phase': phase, 'range': {
        'adapter': 'native-restore-work-v1', 'plan_bytes_sha256': sha256(raw).hexdigest()}}
        for key, phase in (('restore_transaction', 'execute'), ('restore_result', 'deliver'))]


@guarded
@persisted_contract
def prepare_restore_work(registry, request, *, plan, affected_journals=None):
    """Bind native execution and pending delivery without reading live sources.

    The host retains this independent initial binding and separately publishes
    it through CheckpointStore. Planning-mode Work is not this execution path.
    """
    require(type(plan) is RestorePlan, 'restore_work_plan_required')
    return create_restore_work_manifest(registry, request, plan=plan,
        affected_journals=affected_journals, tool_build=_build(), units=_units(plan.source_bytes))


@guarded
@persisted_contract
def _bound(current, registry, build):
    require(current.as_dict()['tool_build'] == build, 'restore_work_build_changed', exit_code=6)
    current = read_restore_work_manifest(current.raw, current.objects, registry=registry,
                                         expected_tool_build=build)
    value = current.as_dict()
    raw = _bytes(value['plan_binding']['plan_source'], current.objects)
    require([{key: task[key] for key in ('key', 'phase', 'range')}
             for task in current.entries('tasks')] == _units(raw),
            'restore_work_execution_plan_required', exit_code=6)
    return current, raw


@guarded
@persisted_contract
def _checked(current, registry, build):
    current, raw = _bound(current, registry, build)
    value = current.as_dict()
    require(value['state'] == 'running' and not current.entries('completed')
            and not value['result_parts'] and not value['diagnostic_parts'],
            'restore_work_pending_execution_required', exit_code=6)
    return current, raw


@dataclass(frozen=True, init=False)
class RestoreWorkExecution:
    """Actual native outcome; a rollback is not success or completed Work."""
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use execute_restore_work')

    def as_dict(self):
        return parse_json_object(self._raw)

    def __bool__(self):
        raise TypeError('Inspect the native Restore outcome explicitly')


def execute_restore_work(store, *, registry, authority, actor, force=False,
                         expected_lock_sha256=None, reason=None,
                         accept_remote_risk=False, owner_probe=None):
    """Run or recover exactly the saved order with fresh, explicit authority.

    Takeover arguments come only from this call, never saved flags. The native
    executor discovers prior effects before checking live original sources; a
    partial target rolls back, a proven full target completes. No Work generation
    is written, so an abrupt process exit leaves only native Restore recovery to
    resolve before outer result delivery can be implemented/confirmed.
    """
    progress = {'mutation_possible': False, 'recovery_required': False}
    try:
        return _execute_restore_work(store, registry=registry, authority=authority,
            actor=actor, force=force, expected_lock_sha256=expected_lock_sha256,
            reason=reason, accept_remote_risk=accept_remote_risk,
            owner_probe=owner_probe, progress=progress)
    except RestoreError as error:
        # A failing Work-lease exit must not hide already possible native effects.
        error.mutation_possible |= progress['mutation_possible']
        error.recovery_required |= error.mutation_possible or progress['recovery_required']
        raise


@guarded
@persisted_contract
def _execute_restore_work(store, *, registry, authority, actor, force,
                          expected_lock_sha256, reason, accept_remote_risk,
                          owner_probe, progress):
    require(type(store) is CheckpointStore, 'restore_trusted_work_store_required', exit_code=2)
    require(type(authority) is RecoveryAuthority, 'restore_authority_required', exit_code=2)
    build = _build()
    initial, raw = _checked(store._initial, registry, build)
    require(initial.as_dict()['checkpoint_generation'] == 0,
            'restore_initial_work_required', exit_code=6)
    data = parse_json_object(raw)
    require(any(boundary.root == Path(data['project_root']) for boundary in store._location._protected),
            'restore_work_unprotected_project', exit_code=7)
    with store._location.inspect_checkpoint() as held:
        # No probe of a possibly lost origin: native journal recovery has priority.
        origin = Path(data['source']['root'])
        require(not held.path.is_relative_to(origin) and not origin.is_relative_to(held.path),
                'restore_work_source_overlap', exit_code=7)
        pointer = store._pointer(held)
        require(pointer is not None, 'restore_published_work_required', exit_code=5)
        current, raw = _checked(store._read_chain(held, pointer[0]), registry, build)
        outcome = _native_held(store, held, current, raw, pointer, registry=registry, build=build,
            authority=authority, actor=actor, force=force, expected_lock_sha256=expected_lock_sha256,
            reason=reason, accept_remote_risk=accept_remote_risk, owner_probe=owner_probe,
            progress=progress)
        value = current.as_dict()
        result = object.__new__(RestoreWorkExecution)
        object.__setattr__(result, '_raw', canonical_json_bytes({
            'format_version': 'restore-work-execution-v1', 'work_id': value['work_id'],
            'checkpoint_generation': value['checkpoint_generation'],
            'checkpoint_sha256': value['checkpoint_sha256'], 'checkpoint_changed': False,
            'work_completion_recorded': False, 'restore': outcome.data}))
        return result


@guarded
@persisted_contract
def _native_held(store, held, current, raw, pointer, *, registry, build, authority, actor,
                 force, expected_lock_sha256, reason, accept_remote_risk, owner_probe,
                 progress, expected_completed_bytes=None, work_guard=None):
    """One native execution with fresh Work checks under the caller's lease."""
    value = current.as_dict()

    @guarded
    @persisted_contract
    def ensure_work():
        require(_build() == build, 'restore_work_build_changed', exit_code=6)
        require(store._pointer(held) == pointer, 'restore_work_pointer_changed', exit_code=6)
        require(store._read_chain(held, pointer[0]).raw == current.raw,
                'restore_work_bytes_changed', exit_code=6)
        require(store._pointer(held) == pointer, 'restore_work_pointer_changed', exit_code=6)
        held.check()
        if work_guard is not None:
            work_guard()

    failure = []

    def ensure_bound_work():
        try:
            ensure_work()
        except RestoreError as error:
            failure.append(error)
            raise

    def authorize(request):
        ensure_bound_work()
        try:
            return authority.check(request)
        finally:
            ensure_bound_work()

    live = RecoveryAuthority(authority.authority_id, authority.version, authorize)
    ensure_work()
    try:
        outcome = execute_restore(raw,
            expected_target_root=value['normalized_arguments']['options']['--expected-target-root'],
            authority=live, actor=actor, request_id=value['request_id'],
            expected_original_actor=value['actor'],
            affected_journals=_bytes(value['plan_binding']['journal_selection'], current.objects),
            force=force, expected_lock_sha256=expected_lock_sha256, reason=reason,
            accept_remote_risk=accept_remote_risk, owner_probe=owner_probe,
            expected_completed_bytes=expected_completed_bytes)
    except RestoreError as error:
        progress.update(mutation_possible=error.mutation_possible,
                        recovery_required=error.recovery_required)
        if failure:
            # Native authorization catches callback errors. Retain the actual
            # Work diagnostic as well as the native mutation/recovery state.
            bound_error = failure[0]
            bound_error.mutation_possible |= error.mutation_possible
            bound_error.recovery_required |= error.recovery_required
            raise bound_error from error
        raise
    # Native completion can be durable even if observation or lease exit fails.
    progress.update(mutation_possible=True, recovery_required=True)
    ensure_work()
    return outcome
