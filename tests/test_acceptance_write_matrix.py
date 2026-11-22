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

from support.write_faults import (CLIENTS, BOUNDARIES, FAULTS, client, points,
    expected_prefix, execute, child, assert_preserved)
from support.write_fault_process import restart_call


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
    child(restart_call(root, 'interrupted', 'interrupted', 'Unconfirmed write'), point, 'kill')
    retained = inventory(root)
    fresh = checkout(root, tmp_path / 'fresh', commit)
    assert project_files(fresh) == saved
    result = new_write(fresh, 'new-intent', 'new-transaction', 'Independent new write')
    assert result['commit_completed'] and not result['replayed']
    assert not (fresh / request_receipt_path('interrupted')).exists()
    assert {p: raw for p, raw in saved.items() if p.startswith('.specroad/')}.items() <= project_files(fresh).items()
    assert transaction_preflight(root, command_class=CommandClass.NORMATIVE_WRITE).exit_code == 5
    assert inventory(root) == retained
