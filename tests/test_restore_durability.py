"""Restore I/O boundaries: actual effects, retained originals and fresh recovery.

Faults are injected in native syscalls, not reported as real storage failures.
All authorities and projects are synthetic; no human approval is asserted.
"""
from contextlib import contextmanager
import errno
from hashlib import sha256
import json
import os

import pytest

from specroad.changes.recovery_values import RecoveryAuthority
from specroad.model.canonical import canonical_json_bytes
from specroad.recovery import RestoreError
from specroad.recovery._execution_store import RestoreStore
from specroad.security import ProjectBoundary
from specroad.storage.operational_preflight import observe_operational_preflight
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.restore import plan_for, restore_case
from test_restore_execution import ACTOR, execute, files, selected
from test_restore_execution_right import fixture, continue_restore


@contextmanager
def io_fault(monkeypatch, method, choose, syscall, *, after=False, arm_after=None,
             error_number=errno.EIO, short_write=False):
    """Fail one selected real storage operation, leaving every actual effect."""
    native_method = getattr(RestoreStore, method)
    reached = []

    def operation(store, *args):
        if reached or not choose(args):
            return native_method(store, *args)
        native_call = getattr(os, syscall)
        armed = arm_after is None

        def fail(*positional, **keywords):
            nonlocal armed
            if not armed:
                return native_call(*positional, **keywords)
            # One fault only; cleanup still uses the real syscalls.
            armed = False
            reached.append((method, syscall))
            if after:
                native_call(*positional, **keywords)
            if short_write:
                return 0
            raise OSError(error_number, 'Synthetic Restore durability fault')

        with monkeypatch.context() as patch:
            if arm_after is not None:
                native_arm = getattr(os, arm_after)

                def arm(*positional, **keywords):
                    nonlocal armed
                    result = native_arm(*positional, **keywords)
                    armed = True
                    return result

                patch.setattr(os, arm_after, arm)
            patch.setattr(os, syscall, fail)
            return native_method(store, *args)

    with monkeypatch.context() as patch:
        patch.setattr(RestoreStore, method, operation)
        yield reached
    assert len(reached) == 1, 'The selected native I/O boundary must be reached'


def failure_state(error, root):
    assert error.exit_code == 5
    assert error.mutation_possible and error.recovery_required
    assert observe_operational_preflight(ProjectBoundary(root))['recovery_required']


def reject_stored_permission(plan, selection, root):
    before = inventory(root)
    with no_write_attempts(), pytest.raises(RestoreError) as failed:
        continue_restore(plan, selection,
            authority=RecoveryAuthority('synthetic-current-denial', '1', lambda _: False))
    assert failed.value.exit_code == 7 and not failed.value.mutation_possible
    assert failed.value.recovery_required and inventory(root) == before


def recovered(plan, selection, root, *, restored, originals):
    calls = []

    def authorize(request):
        calls.append(request)
        return True

    result = continue_restore(plan, selection,
        actor={'actor_type': 'human', 'actor_id': 'synthetic-current-operator'},
        authority=RecoveryAuthority('synthetic-current-authority', '2', authorize))
    assert calls and all(call['actor']['actor_id'] == 'synthetic-current-operator' for call in calls)
    assert result['request']['actor'] == ACTOR
    assert result['request']['request_id'] == 'restore-test'
    assert result['request']['plan_bytes_sha256'] == plan.sha256
    assert result['result'] == ('restored' if restored else 'rolled_back')
    assert result['recovery_required'] is not restored
    expected = files(plan, 'target') if restored else originals
    assert {p: (root / p).read_bytes() for p in expected} == expected
    assert observe_operational_preflight(ProjectBoundary(root))['recovery_required'] is not restored
    audit = json.loads((root / result['audit_path']).read_bytes())
    assert audit['request'] == result['request'] and audit['result'] == result['result']
    before = inventory(root)
    replay = continue_restore(plan, selection)
    assert replay['replayed'] and replay['result'] == result['result']
    assert inventory(root) == before
    return result


@pytest.mark.parametrize('boundary', [
    'backup-write', 'backup-short-write', 'backup-link-before', 'backup-link-after',
    'manifest-directory-sync', 'staging-file-sync', 'prepared-link-after',
    'committing-directory-sync', 'first-replace-before', 'first-replace-after',
    'last-replace-sync', 'old-journal-before', 'old-journal-after',
    'terminal-before', 'terminal-after',
])
def test_forward_io_failure_preserves_actual_state_and_requires_explicit_safe_recovery(
        tmp_path, monkeypatch, boundary):
    options, plan, selection, changed, old = fixture(tmp_path)
    root = options['project_root']
    originals = {p: (root / p).read_bytes() for p in files(plan, 'target')}
    backup = files(plan, 'backup')
    method, syscall, after, arm, short = 'create', 'link', False, None, False
    code = errno.EIO
    if boundary.startswith('backup'):
        choose = lambda args: '/objects/' in args[0]
        if boundary in ('backup-write', 'backup-short-write'):
            syscall, code = 'write', errno.ENOSPC
            short = boundary == 'backup-short-write'
        after = boundary == 'backup-link-after'
    elif boundary in ('manifest-directory-sync', 'staging-file-sync',
                      'prepared-link-after', 'committing-directory-sync'):
        suffix = {'manifest-directory-sync': '/manifest.json',
                  'staging-file-sync': '/staging/0',
                  'prepared-link-after': '/prepared.json',
                  'committing-directory-sync': '/committing.json'}[boundary]
        choose = lambda args: args[0].endswith(suffix)
        syscall = 'link' if boundary == 'prepared-link-after' else 'fsync'
        after = boundary == 'prepared-link-after'
        arm = 'link' if boundary.endswith('directory-sync') else None
    elif 'replace' in boundary:
        method = 'publish'
        path = changed[-1] if boundary == 'last-replace-sync' else changed[0]
        choose = lambda args: args[1] == path
        syscall = 'fsync' if boundary == 'last-replace-sync' else 'replace'
        arm = 'replace' if syscall == 'fsync' else None
        after = boundary == 'first-replace-after'
    else:
        method, syscall = 'archive', 'rename'
        choose = (lambda args: args[0] == old) if boundary.startswith('old-journal') else (
            lambda args: args[0].startswith('.specroad/recovery/restore-'))
        after = boundary.endswith('after')
    restored = boundary in ('last-replace-sync', 'old-journal-before', 'old-journal-after',
                            'terminal-before', 'terminal-after')
    with io_fault(monkeypatch, method, choose, syscall, after=after, arm_after=arm,
                  error_number=code, short_write=short):
        with pytest.raises(RestoreError) as failed:
            execute(plan, affected_journals=selection)
    failure_state(failed.value, root)
    # No error return may conceal a real replace/rename or pretend it was undone.
    for path in changed:
        published = restored or boundary == 'first-replace-after' and path == changed[0]
        assert (root / path).read_bytes() == (files(plan, 'target')[path] if published else originals[path])
    archive = next((root / '.specroad/recovery/archive').iterdir())
    old_moved = boundary in ('old-journal-after', 'terminal-before', 'terminal-after')
    assert (root / old).exists() is not old_moved
    actual_old = archive / 'originals/0' if old_moved else root / old
    assert (actual_old / 'journal.json').read_bytes() == b'{damaged'
    assert (actual_old / 'empty').is_dir()
    existing_objects = {p.name: p.read_bytes() for p in (archive / 'objects').glob('*')}
    assert all(sha256(raw).hexdigest() == digest for digest, raw in existing_objects.items())
    if not boundary.startswith('backup'):
        assert all(existing_objects[sha256(raw).hexdigest()] == raw for raw in backup.values())
    reject_stored_permission(plan, selection, root)
    # Completion and rollback depend on the original proof, never source availability.
    (options['source_root'] / options['source_path']).unlink()
    result = recovered(plan, selection, root, restored=restored, originals=originals)
    assert result['source_observation']['status'] == 'unavailable_or_changed'
    assert all((archive / 'objects' / digest).read_bytes() == raw for digest, raw in existing_objects.items())
    if not restored:
        assert (root / old / 'journal.json').read_bytes() == b'{damaged'
        assert not (archive / 'completed.json').exists()


@pytest.mark.parametrize('effect', ['remove-created-file', 'remove-created-directory', 'restore-original'])
@pytest.mark.parametrize('after', [False, True], ids=['before', 'after'])
def test_rollback_io_failure_can_resume_without_forward_publication_or_lost_originals(
        tmp_path, monkeypatch, effect, after):
    options, original, _ = restore_case(tmp_path)
    root = options['project_root']
    document = next(p for p in original if p.startswith('spec/documents/'))
    goal = next(p for p in original if p.startswith('spec/goals/'))
    put(root, goal, b'original damaged goal')
    if effect.startswith('remove-created'):
        (root / document).unlink()
        (root / document).parent.rmdir()
    else:
        put(root, document, b'original damaged document')
    originals = {p: (root / p).read_bytes() for p in original if (root / p).exists()}
    plan = plan_for(options)
    selection = selected(plan, [])
    with io_fault(monkeypatch, 'publish', lambda args: args[1] == document, 'replace', after=True):
        with pytest.raises(RestoreError) as first:
            execute(plan, affected_journals=selection)
    failure_state(first.value, root)
    if effect == 'restore-original':
        method, syscall = 'publish', 'replace'
        choose = lambda args: args[1] == document
    else:
        method = 'remove' if effect == 'remove-created-file' else 'remove_directory'
        syscall = 'unlink' if effect == 'remove-created-file' else 'rmdir'
        choose = lambda args: args[0] == (document if method == 'remove' else document.rsplit('/', 1)[0])
    with io_fault(monkeypatch, method, choose, syscall, after=after):
        with pytest.raises(RestoreError) as failed:
            continue_restore(plan, selection)
    failure_state(failed.value, root)
    assert (root / goal).read_bytes() == b'original damaged goal'
    if effect == 'restore-original':
        assert (root / document).read_bytes() == (originals[document] if after else original[document])
    elif effect == 'remove-created-file':
        assert (root / document).exists() is not after
    else:
        assert not (root / document).exists()
        assert (root / document).parent.exists() is not after
    reject_stored_permission(plan, selection, root)
    (options['source_root'] / options['source_path']).unlink()
    recovered(plan, selection, root, restored=False, originals=originals)
    if effect.startswith('remove-created'):
        assert not (root / document).exists() and not (root / document).parent.exists()


@pytest.mark.parametrize('completed_target', [False, True], ids=['partial', 'full'])
@pytest.mark.parametrize('after', [False, True], ids=['before-sync', 'after-sync'])
def test_recovery_resynchronization_failure_preserves_proof_and_actual_target(
        tmp_path, monkeypatch, completed_target, after):
    options, plan, selection, changed, _ = fixture(tmp_path)
    root = options['project_root']
    originals = {p: (root / p).read_bytes() for p in files(plan, 'target')}
    path = changed[-1] if completed_target else changed[0]
    with io_fault(monkeypatch, 'publish', lambda args: args[1] == path, 'replace', after=True):
        with pytest.raises(RestoreError):
            execute(plan, affected_journals=selection)
    before = inventory(root)
    with io_fault(monkeypatch, 'synchronize', lambda _: True, 'fsync', after=after):
        with pytest.raises(RestoreError) as failed:
            continue_restore(plan, selection)
    failure_state(failed.value, root)
    assert inventory(root) == before
    reject_stored_permission(plan, selection, root)
    recovered(plan, selection, root, restored=completed_target, originals=originals)


@pytest.mark.parametrize('boundary', ['stage', 'published', 'release-before', 'release-after'])
def test_terminal_barrier_has_exact_original_binding_and_is_released_only_after_durable_archive(
        tmp_path, monkeypatch, boundary):
    options, plan, selection, _, _ = fixture(tmp_path)
    root = options['project_root']
    create = boundary in ('stage', 'published')
    choose = lambda args: args[0].startswith('.specroad/recovery/pending-restore-')
    with io_fault(monkeypatch, 'create' if create else 'remove', choose,
                  'link' if create else 'unlink', after=boundary in ('published', 'release-after')):
        with pytest.raises(RestoreError) as failed:
            execute(plan, affected_journals=selection)
    assert failed.value.exit_code == 5 and failed.value.mutation_possible and failed.value.recovery_required
    if boundary != 'release-after':
        assert observe_operational_preflight(ProjectBoundary(root))['recovery_required']
    barriers = list((root / '.specroad/recovery').glob('pending-restore-*.json'))
    assert len(barriers) == (1 if boundary in ('published', 'release-before') else 0)
    if barriers:
        marker = json.loads(barriers[0].read_bytes())
        intents = list((root / '.specroad/recovery').glob('restore-*/intent.json'))
        intents += list((root / '.specroad/recovery/transaction-audit').glob('restore-*/intent.json'))
        assert len(intents) == 1
        intent_raw = intents[0].read_bytes()
        intent = json.loads(intent_raw)
        assert marker == {'format_version': 'restore-terminal-barrier-v1',
            'request_sha256': intent['execution_id'],
            'original_execution_sha256': sha256(intent_raw).hexdigest(),
            'terminal_path': intent['terminal_move']['target']}
        assert barriers[0].name == 'pending-restore-' + intent['execution_id'] + '.json'
    recovered(plan, selection, root, restored=True, originals={})
    assert not list((root / '.specroad/recovery').glob('pending-restore-*.json'))


@pytest.mark.parametrize('fault', ['bytes', 'binding', 'extra-file', 'link'])
def test_terminal_barrier_conflict_cannot_be_treated_as_completed_recovery(tmp_path, monkeypatch, fault):
    options, plan, selection, _, _ = fixture(tmp_path)
    root = options['project_root']
    with io_fault(monkeypatch, 'archive', lambda args: args[0].startswith('.specroad/recovery/restore-'),
                  'rename', after=True):
        with pytest.raises(RestoreError):
            execute(plan, affected_journals=selection)
    barrier, = (root / '.specroad/recovery').glob('pending-restore-*.json')
    if fault == 'bytes':
        barrier.write_bytes(b'foreign')
    elif fault == 'binding':
        data = json.loads(barrier.read_bytes()); data['original_execution_sha256'] = '0' * 64
        barrier.write_bytes(canonical_json_bytes(data))
    elif fault == 'extra-file':
        put(root, '.specroad/recovery/foreign', b'foreign')
    else:
        outside = tmp_path / 'foreign-marker'; outside.write_bytes(barrier.read_bytes())
        barrier.unlink(); barrier.symlink_to(outside)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(RestoreError) as failed:
        continue_restore(plan, selection)
    assert failed.value.exit_code == (7 if fault == 'link' else 6)
    assert failed.value.recovery_required and not failed.value.mutation_possible
    assert inventory(root) == before


@pytest.mark.parametrize('after', [False, True], ids=['active', 'terminal'])
def test_legacy_execution_without_terminal_derivative_keeps_its_original_bytes(tmp_path, monkeypatch, after):
    options, plan, selection, _, _ = fixture(tmp_path)
    root = options['project_root']
    # Reproduce the previous producer's on-disk effects: the new independent
    # terminal derivative is never created. Original journal bytes are not
    # edited, regenerated, or migrated by this fixture or by recovery.
    create, remove = RestoreStore.create, RestoreStore.remove
    with monkeypatch.context() as legacy:
        def original_create(store, path, raw):
            if not path.startswith('.specroad/recovery/pending-restore-'):
                return create(store, path, raw)

        def original_remove(store, path):
            if not path.startswith('.specroad/recovery/pending-restore-'):
                return remove(store, path)

        legacy.setattr(RestoreStore, 'create', original_create)
        legacy.setattr(RestoreStore, 'remove', original_remove)
        with io_fault(legacy, 'archive', lambda args: args[0].startswith('.specroad/recovery/restore-'),
                      'rename', after=after):
            with pytest.raises(RestoreError):
                execute(plan, affected_journals=selection)
    assert not list((root / '.specroad/recovery').glob('pending-restore-*.json'))
    intents = list((root / '.specroad/recovery').glob('restore-*/intent.json'))
    intents += list((root / '.specroad/recovery/transaction-audit').glob('restore-*/intent.json'))
    path, = intents; original = path.read_bytes()
    assert 'pending-restore-' not in original.decode()
    (options['source_root'] / options['source_path']).unlink()
    result = recovered(plan, selection, root, restored=True, originals={})
    terminal = root / json.loads(original)['terminal_move']['target'] / 'intent.json'
    assert terminal.read_bytes() == original and result['replayed'] is after
    assert not list((root / '.specroad/recovery').glob('pending-restore-*.json'))


def test_source_loss_after_full_durable_target_does_not_block_terminal_release(tmp_path, monkeypatch):
    options, plan, selection, _, _ = fixture(tmp_path)
    root = options['project_root']
    native = RestoreStore.archive
    observed = []

    def archive(store, path, destination):
        result = native(store, path, destination)
        if path.startswith('.specroad/recovery/restore-'):
            (options['source_root'] / options['source_path']).unlink()
            observed.append(True)
            assert observe_operational_preflight(ProjectBoundary(root))['recovery_required']
        return result

    monkeypatch.setattr(RestoreStore, 'archive', archive)
    result = execute(plan, affected_journals=selection).data
    assert observed == [True] and result['result'] == 'restored'
    assert not result['recovery_required']
    assert not observe_operational_preflight(ProjectBoundary(root))['recovery_required']
    assert all((root / p).read_bytes() == raw for p, raw in files(plan, 'target').items())
