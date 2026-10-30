"""Passive Restore Work controls with native publication boundaries.

Transport is a Work checkpoint copy, never a project Recovery backup. A
pending execution can be transported or cancelled only while its exact
original inventory still exists. A completed Work result is historical data.
"""
from contextlib import contextmanager

from ..changes._lock_files import LockFiles
from ..recovery._inventory import boundary
from ..recovery._observations import verify_live
from ..recovery.values import RestorePlan, guarded, persisted_contract, require
from .control import _cancel
from .manifest import _bytes
from .restore_execution import _build
from ._public_errors import work_errors


@contextmanager
def passive_guard(current):
    value = current.as_dict()
    if value['command_id'] != 'recover.restore' or '--from' in value['normalized_arguments']['options']:
        yield
        return
    if value['state'] == 'completed':
        # The closed completion contract is verified by the chain reader. No
        # assertion about the current project or its Recovery state is made.
        yield
        return
    require(not current.entries('completed'), 'restore_work_native_delivery_pending', exit_code=5)
    raw = _bytes(value['plan_binding']['plan_source'], current.objects)
    plan = RestorePlan(raw)
    project = value['normalized_arguments']['options']['--project']
    with LockFiles(project) as files:
        files.acquire()
        # Cancel/export preserves a passive request; it neither qualifies a
        # new target nor publishes it. Still require the complete original
        # inventory, so an active or completed native transaction cannot be
        # hidden by transporting/cancelling its pending outer checkpoint.
        project_boundary = boundary(project)
        origin = boundary(plan.data['source']['root'])
        verify_live(plan, project_boundary, origin)
        files.require_held()
        yield
        verify_live(plan, project_boundary, origin)
        files.require_held()


@guarded
@persisted_contract
@work_errors
def cancel_restore_work(store, *, reason):
    def check(current):
        value = current.as_dict()
        require(value['command_id'] == 'recover.restore', 'restore_work_command_required', exit_code=2)
        if '--from' in value['normalized_arguments']['options']:
            from .restore_planning import checked
            checked(current)
        else:
            from .restore_execution import _bound
            _bound(current, store._registry, _build())
    return _cancel(store, reason, _build(), check, passive_guard)


def delivered_files(current):
    """Reconstruct exact result files already declared by immutable evidence."""
    value = current.as_dict()
    if value['command_id'] != 'recover.restore':
        return ()
    if '--from' in value['normalized_arguments']['options']:
        from ..model.canonical import canonical_json_bytes
        from .restore_planning import checked
        _, evidence = checked(current)
        return (('restore-plan.json', canonical_json_bytes(evidence[-1]['result']['restore_plan'])),
                ) if evidence and evidence[-1]['phase'] == 'deliver_plan' else ()
    if len(current.entries('completed')) < 2:
        return ()
    from ._restore_completion import projection, saved_delivery
    return projection(value, current.objects, saved_delivery(value, current.objects))
