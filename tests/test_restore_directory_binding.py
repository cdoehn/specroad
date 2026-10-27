"""Real descriptor replacement races, not a hostile-filesystem sandbox claim."""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from specroad.changes.locking import project_lock
from specroad.model.errors import ModelError
from specroad.recovery import RestoreError
from specroad.recovery import _execution_store as storage
from specroad.recovery._inventory import observe
from specroad.security import SafetyViolation
from support.model import put
from support.read_only import inventory
from support.restore import restore_case, plan_for
from test_restore_execution import execute


ACTIVE = '.specroad/recovery/restore-native'
STAGED = ACTIVE + '/staging/0'
OLD = '.specroad/transactions/old'
ARCHIVED = '.specroad/recovery/archive/native/originals/0'
TERMINAL = '.specroad/recovery/transaction-audit/restore-native'
EXISTING = 'spec/current/existing'
NEW = 'spec/current/new'
EMPTY = 'spec/current/empty'
OPERATIONS = ('publish-new', 'publish-existing', 'remove', 'archive-old',
              'archive-terminal', 'rmdir')


@contextmanager
def store_case(tmp_path):
    """Owned storage inventory under the real mutex; not a qualified project."""
    root = tmp_path / 'project'; root.mkdir()
    put(root, EXISTING, b'original bytes')
    os.chmod(root / EXISTING, 0o640)
    put(root, STAGED, b'new bytes')
    os.chmod(root / STAGED, 0o600)
    put(root, OLD + '/journal.json', b'original damaged journal')
    (root / EMPTY).mkdir()
    with project_lock(root, kind='recovery', command='recover restore',
                      project_id='synthetic-project', transaction_id='native', request_id='native') as held:
        observed, _ = observe(held._files.boundary,
                             ['.specroad/recovery', '.specroad/transactions', 'spec'])
        layout = {'own': {STAGED: b'new bytes'}, 'active': ACTIVE, 'terminal': TERMINAL,
                  'binding': {'archive_moves': [{'source': OLD, 'target': ARCHIVED}]},
                  'target': {NEW: b'new bytes', EXISTING: b'new bytes'}}
        store = storage.RestoreStore(held, SimpleNamespace(data={'inventory': observed}), layout)
        store.check()
        yield root, store


def paths(operation):
    if operation.startswith('publish'):
        return STAGED, NEW if operation == 'publish-new' else EXISTING
    if operation == 'archive-old': return OLD, ARCHIVED
    if operation == 'archive-terminal': return ACTIVE, TERMINAL
    return None, EMPTY if operation == 'rmdir' else EXISTING


def perform(store, operation):
    source, target = paths(operation)
    if operation.startswith('publish'): return store.publish(source, target, b'new bytes')
    if operation.startswith('archive'): return store.archive(source, target)
    if operation == 'rmdir': return store.remove_directory(target)
    return store.remove(target)


def exchange_parent(parent, detached, kind, *, bait):
    """A separate actor changes the namespace while an old descriptor is open."""
    parent.rename(detached)
    if kind == 'copy':
        shutil.copytree(detached, parent)
    elif kind == 'symlink':
        parent.symlink_to(detached, target_is_directory=True)
    elif kind == 'relocate':
        parent.mkdir()
        for item in detached.iterdir(): item.rename(parent / item.name)
        if bait == 'empty': (detached / bait).mkdir()
        elif bait == 'old': put(detached, bait + '/journal.json', b'foreign original')
        else: put(detached, bait, b'foreign original')
    else:
        assert kind == 'missing'


def pause_open_parents(monkeypatch, store, operation, side, change):
    """Pause when mutation descriptors are held; inventory reads stay native."""
    source, target = paths(operation)
    source_parent = None if source is None else tuple(source.split('/')[:-1])
    target_parent = tuple(target.split('/')[:-1])
    watched = source_parent if side == 'source' else target_parent
    native_check, native_directory = store.check, store.files.directory
    native_fingerprint = storage.fingerprint_recovery_file
    state = {'checking': 0, 'opened': [], 'armed': operation != 'remove', 'changed': False}

    def check():
        state['checking'] += 1
        try: return native_check()
        finally: state['checking'] -= 1

    def fingerprint(files, path):
        result = native_fingerprint(files, path)
        if files is store.files and path == target: state['armed'] = True
        return result

    @contextmanager
    def directory(parts, *, create=False):
        parts = tuple(parts)
        with native_directory(parts, create=create) as fd:
            state['opened'].append(parts)
            try:
                both = source_parent is None or source_parent in state['opened']
                if (not state['changed'] and not state['checking'] and state['armed']
                        and not create and parts == target_parent and both):
                    state['changed'] = True
                    change(watched, Path(source if side == 'source' else target).name)
                yield fd
            finally:
                state['opened'].pop()

    monkeypatch.setattr(store, 'check', check)
    monkeypatch.setattr(store.files, 'directory', directory)
    monkeypatch.setattr(storage, 'fingerprint_recovery_file', fingerprint)
    return state


PAIRS = [(operation, side) for operation in OPERATIONS
         for side in (('source', 'target') if paths(operation)[0] else ('target',))]


@pytest.mark.parametrize('kind', ['copy', 'missing', 'symlink'])
@pytest.mark.parametrize('operation,side', PAIRS)
def test_replaced_open_parent_is_rejected_before_mutating_either_tree(tmp_path, monkeypatch,
                                                                    operation, side, kind):
    with store_case(tmp_path) as (root, store):
        detached = tmp_path / 'detached'
        expected = {}
        def change(parts, bait):
            exchange_parent(root.joinpath(*parts), detached, kind, bait=bait)
            expected['root'], expected['detached'] = inventory(root), inventory(detached)
        state = pause_open_parents(monkeypatch, store, operation, side, change)
        with pytest.raises((ModelError, SafetyViolation)) as failure:
            perform(store, operation)
        assert state['changed']
        assert isinstance(failure.value, SafetyViolation) or failure.value.exit_code in (6, 7)
        assert inventory(root) == expected['root']
        assert inventory(detached) == expected['detached']


@pytest.mark.parametrize('operation,side', [('publish-existing', 'target'), ('remove', 'target'),
                                           ('rmdir', 'target'), ('archive-old', 'source')])
def test_retained_file_inode_does_not_authorize_an_old_parent_with_foreign_bytes(tmp_path, monkeypatch,
                                                                             operation, side):
    with store_case(tmp_path) as (root, store):
        detached = tmp_path / 'detached'; expected = {}
        def change(parts, bait):
            exchange_parent(root.joinpath(*parts), detached, 'relocate', bait=bait)
            expected['root'], expected['detached'] = inventory(root), inventory(detached)
        pause_open_parents(monkeypatch, store, operation, side, change)
        with pytest.raises(ModelError) as failure:
            perform(store, operation)
        assert failure.value.exit_code == 6
        assert inventory(root) == expected['root']
        assert inventory(detached) == expected['detached']


@pytest.mark.parametrize('side', ['source', 'target'])
def test_publication_rechecks_parents_after_staged_mode_is_synchronized(tmp_path, monkeypatch, side):
    with store_case(tmp_path) as (root, store):
        image = (root / STAGED).stat()
        native_sync = os.fsync
        detached = tmp_path / 'detached'; expected = {}
        def sync(fd):
            native_sync(fd)
            current = os.fstat(fd)
            if not expected and (current.st_dev, current.st_ino) == (image.st_dev, image.st_ino):
                path = STAGED if side == 'source' else NEW
                exchange_parent((root / path).parent, detached, 'copy', bait=Path(path).name)
                expected['root'], expected['detached'] = inventory(root), inventory(detached)
        monkeypatch.setattr(os, 'fsync', sync)
        with pytest.raises(ModelError) as failure:
            store.publish(STAGED, NEW, b'new bytes')
        assert failure.value.exit_code == 6 and expected
        assert inventory(root) == expected['root']
        assert inventory(detached) == expected['detached']


@pytest.mark.parametrize('operation', OPERATIONS)
def test_unchanged_parents_keep_native_effects_and_exact_original_bytes(tmp_path, operation):
    with store_case(tmp_path) as (root, store):
        source, target = paths(operation)
        perform(store, operation)
        store.check()
        if operation.startswith('publish'):
            assert (root / target).read_bytes() == b'new bytes'
            assert not (root / source).exists()
            assert (root / target).stat().st_mode & 0o777 == (
                0o640 if operation == 'publish-existing' else 0o644)
        elif operation.startswith('archive'):
            assert not (root / source).exists()
            suffix = '/journal.json' if operation == 'archive-old' else '/staging/0'
            assert (root / (target + suffix)).read_bytes() == (
                b'original damaged journal' if operation == 'archive-old' else b'new bytes')
        else:
            assert not (root / target).exists()


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
def test_public_restore_retains_backups_and_blocks_before_detached_target_write(tmp_path, monkeypatch, kind):
    options, originals, _ = restore_case(tmp_path, kind)
    root = options['project_root']
    path = next(p for p in originals if p.startswith('spec/documents/'))
    (root / path).unlink()
    plan = plan_for(options)
    native = storage.RestoreStore.publish
    expected = {}; detached = tmp_path / 'detached'
    def publish(store, staged, target, raw):
        if target == path:
            check = store.before_mutation
            def change():
                if not expected:
                    exchange_parent((root / path).parent, detached, 'copy', bait=Path(path).name)
                    expected['root'], expected['detached'] = inventory(root), inventory(detached)
                check()
            store.before_mutation = change
        return native(store, staged, target, raw)
    monkeypatch.setattr(storage.RestoreStore, 'publish', publish)
    with pytest.raises(RestoreError) as failure:
        execute(plan)
    assert failure.value.exit_code == 6 and failure.value.recovery_required
    assert failure.value.mutation_possible and expected
    # The same live process releases its exact temporary owner as usual;
    # the persistent active Restore journal remains the recovery barrier.
    assert inventory(root) == tuple(row for row in expected['root']
                                    if row[0] != '.specroad/locks/project.json')
    assert inventory(detached) == expected['detached']
    assert list((root / '.specroad/recovery/archive').glob('*/manifest.json'))
    assert list((root / '.specroad/recovery').glob('restore-*/committing.json'))
    assert not (root / '.specroad/locks/project.json').exists()
