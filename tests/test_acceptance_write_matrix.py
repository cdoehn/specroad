"""Every durable boundary through actual native clients, never a writer model.

Owned process loss and actual I/O exceptions preserve the observed partial
prefix. No test invokes recovery, clears a marker, or resumes the old write.
"""
import errno
import json
import multiprocessing
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
        return root, before, target, plan.data['request_id'], args['transaction_id'], project_id, lambda: apply(root, plan, args)
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
    return root, before, target, plan.data['request_id'], TRANSACTION, 'sample', lambda: publish(root, check).data


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
    process = multiprocessing.get_context('fork').Process(target=execute, args=(run, point, fault))
    process.start(); process.join(60)
    if process.is_alive():
        process.kill(); process.join(); pytest.fail('Native client did not reach its selected boundary')
    assert process.exitcode == (-signal.SIGKILL if fault == 'kill' else 83)


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


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('boundary', BOUNDARIES)
@pytest.mark.parametrize('fault', FAULTS)
def test_every_native_boundary_retains_exact_prefix_and_never_replays(tmp_path, kind, boundary, fault):
    # Obtain the full effect inventory from a real plan, not from hardcoded
    # indices. Each effect gets its own fresh original project and killed writer.
    first = client(tmp_path / 'case-0', kind)
    root, before, target, request, transaction, project, run = first
    selected = points(boundary, before, target, request)
    assert selected
    for index, point in enumerate(selected):
        if index:
            root, before, target, request, transaction, project, run = client(tmp_path / ('case-' + str(index)), kind)
            assert point in points(boundary, before, target, request)
        directory = tmp_path / ('case-' + str(index))
        retained = {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob('*.zip')}
        if kind != 'change': assert retained
        child(run, point, fault)
        assert_preserved(root, before, target, point, fault, request, transaction, project)
        assert {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob('*.zip')} == retained


@pytest.mark.parametrize('point', ['marker_synced', 'effect_synced:0', 'receipts_synced'])
def test_real_kill_then_full_fresh_git_checkout_never_unlocks_original(tmp_path, point):
    from test_git_restart import saved_project
    from support.git_restart import project_files, checkout, new_write
    root = tmp_path / 'original'; commit, saved = saved_project(root)
    child(lambda: new_write(root, 'interrupted', 'interrupted', 'Unconfirmed write'), point, 'kill')
    retained = inventory(root)
    fresh = checkout(root, tmp_path / 'fresh', commit)
    assert project_files(fresh) == saved
    result = new_write(fresh, 'new-intent', 'new-transaction', 'Independent new write')
    assert result['commit_completed'] and not result['replayed']
    assert not (fresh / request_receipt_path('interrupted')).exists()
    assert {p: raw for p, raw in saved.items() if p.startswith('.specroad/')}.items() <= project_files(fresh).items()
    assert transaction_preflight(root, command_class=CommandClass.NORMATIVE_WRITE).exit_code == 5
    assert inventory(root) == retained
