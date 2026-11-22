"""Closed native fault catalog and clients, shared independently of assertions.

The original expected-prefix and corruption/receipt oracles are retained byte
for byte. This module never runs clients during import or collection.
"""
import errno
import json
import os
from pathlib import Path
import signal

import pytest

from specroad.changes import (guarded_write, schema_transition, inspect_write_state,
    read_guarded_completion, transaction_preflight)
from specroad.changes.receipt_values import request_receipt_path, transaction_receipt_path
from specroad.cli.contracts import CommandClass
from support.read_only import inventory, no_write_attempts
from test_snapshot_guard import scenario, FAILURES
from support.write_fault_process import native_call, fault_process

CLIENTS = ('change', 'migration', 'merge')
BOUNDARIES = ('before_lock', 'before_marker', 'marker_synced', 'staged', 'effect',
    'effect_synced', 'transaction_receipt', 'request_receipt', 'completion_receipt',
    'receipts_synced', 'before_marker_unlink', 'marker_unlinked', 'marker_removed', 'after_return')
FAULTS = ('kill', 'io', 'space', 'quota')


def client(directory, kind):
    directory.mkdir(parents=True)
    if kind != 'change':
        root, before, plan, args, target, apply = scenario(directory, kind)
        project_id = json.loads(before['specroad.json'])['project_id']
        run = native_call(directory, kind, root, plan, args, lambda: apply(root, plan, args))
        return root, before, target, plan.data['request_id'], args['transaction_id'], project_id, run
    from test_write_guard import setup, publish
    from support.folds import create, edit, goal
    from support.targets import plan as make_plan, ACTOR, TIME, POLICY
    from support.publication import TRANSACTION
    from specroad.changes import prepare_publication_check
    root = directory / 'project'; model, _, _ = setup(root)
    fresh = goal(2, revision=1, created_at=TIME, updated_at=TIME, created_by=ACTOR, updated_by=ACTOR)
    plan = make_plan(model, [edit(model.artifacts[0], 'New owned statement'), create(fresh)], request_id='matrix-request')
    check = prepare_publication_check(plan, model, policy=POLICY)
    before = dict(model.source_files)
    target = {**before, **{d.path: d.content for d in check.request.documents}}
    run = native_call(directory, kind, root, plan, {}, lambda: publish(root, check).data, before=before)
    return root, before, target, plan.data['request_id'], TRANSACTION, 'sample', run


def points(boundary, before, target, request):
    changed = sorted(p for p in before.keys() | target.keys() if before.get(p) != target.get(p))
    if boundary == 'staged':
        return ['staged:' + str(i) for i, p in enumerate(changed) if p in target]
    if boundary in ('effect', 'effect_synced'):
        return [('effect_synced:' if boundary == 'effect_synced' else
                 'effect_replaced:' if p in target else 'effect_unlinked:') + str(i)
                for i, p in enumerate(changed)]
    if boundary == 'transaction_receipt': return ['receipt:transaction.json']
    if boundary == 'completion_receipt': return ['receipt:committed.json']
    if boundary == 'request_receipt':
        assert request is not None, 'Each matrix client must use a real request receipt'
        return ['receipt:' + request_receipt_path(request).rsplit('/', 1)[-1]]
    return [boundary]


def expected_prefix(point, before, target):
    if point.startswith(('effect_replaced:', 'effect_unlinked:', 'effect_synced:')):
        index = int(point.rsplit(':', 1)[1]); result = dict(before)
        changed = sorted(p for p in before.keys() | target.keys() if before.get(p) != target.get(p))
        for path in changed[:index + 1]:
            if path in target: result[path] = target[path]
            else: result.pop(path)
        return result
    if point.startswith('receipt:') or point in ('receipts_synced', 'before_marker_unlink',
            'marker_unlinked', 'marker_removed', 'after_return'):
        return target
    return before


def execute(run, point, fault):
    reached = []
    def stop(event):
        if event != point: return
        reached.append(event)
        if fault == 'kill': os.kill(os.getpid(), signal.SIGKILL)
        raise OSError({'io': errno.EIO, 'space': errno.ENOSPC, 'quota': errno.EDQUOT}[fault], 'owned boundary fault')
    guarded_write._checkpoint = schema_transition._checkpoint = stop
    try:
        stop('before_lock'); run(); stop('after_return')
    except FAILURES:
        os._exit(83 if reached == [point] else 85)
    os._exit(84)  # A missing fault boundary is never accepted as a pass.


def child(run, point, fault):
    process = fault_process(run, point, fault)
    assert process.returncode == (-signal.SIGKILL if fault == 'kill' else 83), {
        'point': point, 'fault': fault, 'returncode': process.returncode,
        'stdout': process.stdout.decode(errors='replace'),
        'stderr': process.stderr.decode(errors='replace'),
    }


def assert_preserved(root, before, target, point, fault, request, transaction, project):
    expected = expected_prefix(point, before, target)
    for path in before.keys() | target.keys():
        if path in expected: assert (root / path).read_bytes() == expected[path]
        else: assert not (root / path).exists()
    snapshot = inventory(root)
    with no_write_attempts():
        state = inspect_write_state(root, expected_project_id=project)
        if point == 'after_return':
            assert state['state'] == 'clean'
            completion = read_guarded_completion(root, transaction, expected_project_id=project).data
            assert completion['replayed'] and completion['commit_completed']
            assert not completion['current_target_verified']
            assert completion['result_object']['request_id'] == request
            receipts = list((root / '.specroad/transactions/receipts').glob('*/transaction.json'))
            assert receipts == [root / transaction_receipt_path(transaction)]
        elif point == 'before_lock' or (point == 'before_marker' and fault != 'kill'):
            assert state['state'] == 'clean'
            with pytest.raises(FAILURES): read_guarded_completion(root, transaction, expected_project_id=project)
        else:
            assert state['state'] == 'corrupted' and state['manual_git_restore_required']
            for command in (CommandClass.READ_ONLY, CommandClass.NORMATIVE_WRITE):
                assert transaction_preflight(root, command_class=command).exit_code == 5
            with pytest.raises(FAILURES): read_guarded_completion(root, transaction, expected_project_id=project)
    assert inventory(root) == snapshot
