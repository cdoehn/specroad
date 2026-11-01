"""Native capture setup for tests whose subject is qualification or delivery.

The public argv Bundle reference still resumes every individual capture.
Baseline source captures and inventory boundaries can stay public as well.
This helper retains real originals and never qualifies or delivers a plan.
"""
from specroad.cli.commands import builtin_registry
from specroad.model.canonical import canonical_json_bytes
from specroad.work._restore_capture import ADAPTER, capture
from specroad.work.manifest import partition_work_manifest
from specroad.work.open_existing import open_restore_work
from specroad.work.restore_planning import checked


def capture_pending_planning_units(location, *, keep_last_inventory=False):
    store = open_restore_work(location, registry=builtin_registry())
    current = store.read()
    options, _ = checked(current)
    remaining = current.entries('remaining')
    assert current.entries('completed') and len(remaining) > 2
    assert [task['phase'] for task in remaining[-2:]] == ['qualify_plan', 'deliver_plan']
    assert all(task['range']['adapter'] == ADAPTER for task in remaining)
    tasks = remaining[:-2]
    if keep_last_inventory:
        # Only the middle inventory may be batched; the last capture stays public.
        assert len(tasks) > 1 and all(task['phase'] == 'inventory_capture' for task in tasks)
        tasks = tasks[:-1]
    captured = {}
    for task in tasks:
        assert task['phase'] in ('source_capture', 'inventory_capture')
        captured[task['unit_id']] = canonical_json_bytes({
            'phase': task['phase'], 'work_id': current.as_dict()['work_id'],
            'chunk': capture(options, task)})
    candidate = partition_work_manifest(current, captured)
    assert candidate.entries('remaining') == remaining[len(tasks):]
    return store.publish(candidate)
