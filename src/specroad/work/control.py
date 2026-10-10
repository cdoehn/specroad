"""Checked Work status and explicit cancellation of closed host-adapter work.

Status is an observation of stored data, not execution or native commit proof.
Cancellation retains every byte and never runs a handler, writer or Recovery.
These embedding APIs do not register CLI commands or emit continuation Code 8.
"""

from contextlib import contextmanager, nullcontext

from ..changes._lock_files import LockFiles
from ..changes.authoring import bind_plan_authoring
from ..changes.idempotency import resolve_normative_request
from ..cli.commands import builtin_registry
from ._cancellation import cancellation_candidate, read_cancellation
from ._data_contract import _text
from .checkpoints import CheckpointStore
from .manifest import read_work_manifest
from .publication import _arguments, _checked_work, _source, _transaction_clear
from .result_files import _ensure_work
from .resume import (_checked_plan, _compatible_read, _require, _runtime_build,
                     _saved_outcome, WorkResumeError)


def _initial(store, build):
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    _require(store._initial.as_dict()['tool_build'] == build, 'incompatible_runtime_build')
    _compatible_read(read_work_manifest, store._initial.raw, store._initial.objects,
                     registry=store._registry, expected_tool_build=build)


def _read(store, held, build):
    pointer = store._pointer(held)
    _require(pointer is not None, 'published_work_required')
    current = _compatible_read(store._read_chain, held, pointer[0])
    _compatible_read(read_work_manifest, current.raw, current.objects,
                     registry=store._registry, expected_tool_build=build)
    _ensure_work(store, held, pointer, current, build)
    return pointer, current


def inspect_work_status(store):
    """Read the complete stored chain; no handler, project read or write.

    next_action is the checked inert manifest operation, not a runnable command
    string or a newly installed work CLI. Native transaction state is unknown.
    """
    build = _runtime_build()
    _initial(store, build)
    with store._location.inspect_checkpoint() as held:
        pointer, current = _read(store, held, build)
        value = current.as_dict()
        cancellation = (read_cancellation(value, current.objects)
                        if value['state'] == 'cancelled' else None)
        result = {'format_version': 'work-status-v1', 'work_dir': str(held.path),
            **{key: value[key] for key in ('work_id', 'checkpoint_generation',
                'checkpoint_sha256', 'command_id', 'command_class', 'state',
                'source_bindings', 'tool_build', 'progress', 'remaining_manifest_sha256',
                'blocked_reason', 'next_action')},
            'remaining_manifest': value['manifests']['remaining'], 'cancellation': cancellation,
            'verification_scope': 'persisted_work_chain', 'action_is_executable_command': False,
            'native_transaction_checked': False, 'command_execution_performed': False,
            'project_writes_performed': False}
        _ensure_work(store, held, pointer, current, build)
        return result


def _reason(reason):
    try:
        _text(reason)
    except ValueError as error:
        raise WorkResumeError('cancellation_reason_required', exit_code=2) from error
    if not reason.strip():
        raise WorkResumeError('cancellation_reason_required', exit_code=2)


def _cancel(store, reason, build, check, guard):
    _reason(reason)
    _initial(store, build)
    with store._location.inspect_checkpoint() as held:
        pointer, current = _read(store, held, build)
        value = current.as_dict()
        cancelled = value['state'] == 'cancelled'
        if cancelled:
            record = read_cancellation(value, current.objects)
            _require(record['reason'] == reason, 'cancellation_reason_changed')
        else:
            _require(value['state'] == 'running', 'work_cannot_cancel')
            check(current)
            with guard(current):
                _ensure_work(store, held, pointer, current, build)
    if not cancelled:
        with store._location.for_checkpoint() as held:
            fresh_pointer, fresh = _read(store, held, build)
            _require(fresh_pointer == pointer and fresh.raw == current.raw,
                     'cancellation_source_changed')
            check(fresh)
            with guard(fresh):
                _ensure_work(store, held, pointer, current, build)
                candidate = _compatible_read(cancellation_candidate, fresh, reason)
                current = _compatible_read(store._publish_held, held, candidate, pointer)
                _ensure_work(store, held, store._pointer(held), current, build)
    result = inspect_work_status(store)
    _require(result['state'] == 'cancelled'
             and result['checkpoint_sha256'] == current.as_dict()['checkpoint_sha256'],
             'cancellation_result_changed')
    return result


def cancel_read_only_work(store, *, reason):
    """Stop an unfinished closed bootstrap Work plan without executing it."""
    registry, build = builtin_registry(), _runtime_build()
    _initial(store, build)
    _checked_plan(store._initial, registry, build)

    def check(current):
        checked, request, invocation, unit = _checked_plan(current, registry, build)
        if checked.entries('completed'):
            _saved_outcome(checked, request, invocation, unit)

    return _cancel(store, reason, build, check, lambda current: nullcontext())


def cancel_normative_preparation(store, *, registry, model, policy, actor, request_id, reason):
    """Cancel an original request only while its native publication is absent.

    The existing project root-inode mutex excludes cooperative native writers
    throughout checkpoint publication, without creating a project owner record.
    An active/orphan transaction, a committed request, or an absent request ID
    refuses cancellation. No recovery, receipt removal or target write occurs.
    """
    build = _arguments(store, registry, model, policy, actor, request_id)

    def check(current):
        _checked_work(current, registry, build)

    @contextmanager
    def unpublished(current):
        _, plan = _checked_work(current, registry, build)
        _require(plan.data['request_id'] is not None, 'normative_cancellation_requires_request_id')
        source = _source(model)
        with LockFiles(source.boundary.root) as files:
            _require(files.boundary._root_identity == source.boundary._root_identity,
                     'resume_project_root_changed')
            files.acquire()

            def ensure():
                files.require_held()
                source.check_current()
                _transaction_clear(model)
                resolution = resolve_normative_request(source, bind_plan_authoring(plan)).data
                _require(resolution['action'] == 'new_request' and not resolution['receipt_verified'],
                         'normative_request_already_committed')
                source.check_current()
                files.require_held()

            ensure()
            yield
            ensure()

    return _cancel(store, reason, build, check, unpublished)
