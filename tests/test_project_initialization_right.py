"""Native hard exits, closed replay evidence and preservation of foreign state."""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.authoring import _bootstrap_io as bootstrap
from specroad.authoring import initialization
from specroad.cli.application import dispatch_result, execute_request
from specroad.model.canonical import canonical_json_bytes
from support.command_parity import process_environment, run_python
from support.read_only import inventory, no_write_attempts
from test_project_initialization import check_project, EXPECTED_DIRECTORIES


CRASH_BODY = '''
import os, sys
sys.path.insert(0, sys.argv[1])
from specroad.authoring import _bootstrap_io as io
from specroad.authoring.initialization import initialize_project
target, cut = sys.argv[2:]
prepare, move, native, finish = io.BootstrapTree.prepare, io.rename_new, io._rename_native, io.BootstrapTree.retain_completed
def prepared(self, *args):
    prepare(self, *args)
    if cut == 'prepared': os._exit(73)
def moved(function, source_fd, source, target_fd, destination):
    move(function, source_fd, source, target_fd, destination)
    if cut == destination: os._exit(73)
def native_moved(function, source_fd, source, target_fd, destination):
    native(function, source_fd, source, target_fd, destination)
    if cut == 'receipt-move' and source == io.STAGING: os._exit(73)
def finished(self):
    finish(self)
    if cut == 'complete': os._exit(73)
io.BootstrapTree.prepare, io.rename_new = prepared, moved
io._rename_native, io.BootstrapTree.retain_completed = native_moved, finished
initialize_project(target)
raise AssertionError('fault boundary was not reached')
'''


def interrupt(root, cut='prepared'):
    repository = Path(__file__).resolve().parents[1]
    result = run_python(CRASH_BODY, [str(repository / 'src'), str(root), cut],
                        cwd=root.parent, environment=process_environment())
    assert result.returncode == 73, (result.stdout, result.stderr)
    stage = root / bootstrap.STAGING
    receipt = root.joinpath(*bootstrap.COMPLETED)
    record = stage / 'journal.json' if stage.exists() else receipt / 'journal.json'
    return record, json.loads(record.read_bytes())


def preserved(root):
    return (inventory(root), tuple((str(p.relative_to(root)), p.lstat().st_dev,
            p.lstat().st_ino, p.lstat().st_nlink) for p in [root, *sorted(root.rglob('*'))]))


@contextmanager
def no_bootstrap_writes():
    with no_write_attempts(), patch.object(bootstrap, '_rename_native',
            side_effect=AssertionError('unexpected native mutation')) as native:
        yield
    native.assert_not_called()


















@pytest.mark.parametrize('damage', ['project-edit', 'receipt-extra', 'receipt-link', 'missing-journal'])
def test_completed_receipt_does_not_authorize_reinitializing_changed_project(tmp_path, damage):
    root = tmp_path / 'project'; check_project(root, dispatch_result(['init', str(root)]))
    receipt = root.joinpath(*bootstrap.COMPLETED)
    if damage == 'project-edit': (root / 'rules/new-user-rule').write_bytes(b'keep user data')
    elif damage == 'receipt-extra': (receipt / 'unlisted').write_bytes(b'keep foreign evidence')
    elif damage == 'receipt-link':
        outside = tmp_path / 'receipt'; receipt.rename(outside); receipt.symlink_to(outside, target_is_directory=True)
    else: (receipt / 'journal.json').unlink()
    before = preserved(tmp_path)
    with no_bootstrap_writes(): result = dispatch_result(['init', str(root)])
    assert result.exit_code == (7 if damage == 'receipt-link' else 6)
    assert preserved(tmp_path) == before


def test_incomplete_preparation_without_record_remains_untouched(tmp_path):
    root = tmp_path / 'project'; stage = root / bootstrap.STAGING; stage.mkdir(parents=True)
    (stage / 'fragment').write_bytes(b'unknown ownership without a closed record')
    before = preserved(tmp_path)
    with no_bootstrap_writes(): result = dispatch_result(['init', str(root)])
    assert result.exit_code == 5 and preserved(tmp_path) == before

@pytest.mark.parametrize('cut', ['prepared', '.specroad', 'archive', 'attachments',
    'generated', 'mappings', 'profiles', 'rules', 'spec', 'specroad.json', 'receipt-move', 'complete'])
@pytest.mark.parametrize('kind', ['missing', 'repository'])
def test_process_loss_preserves_prefix_and_refuses_all_reentry(tmp_path, cut, kind):
    root=tmp_path/'project'
    if kind=='repository':
        root.mkdir();(root/'README').write_bytes(b'original foreign bytes')
        # An existing empty rules directory has no rename effect. Keep that
        # reuse coverage at every other cut; this cut needs an actual rules move.
        if cut != 'rules': (root/'rules').mkdir()
    interrupt(root,cut)
    before=preserved(tmp_path)
    with no_bootstrap_writes():
        result=dispatch_result(['init',str(root)])
    assert result.exit_code==5 and preserved(tmp_path)==before
    from specroad.authoring.bootstrap_guard import observe_bootstrap
    assert observe_bootstrap(root)['state']=='corrupted'
    from specroad.storage.project import ProjectSource
    from specroad.model.errors import ModelError
    with no_write_attempts(),pytest.raises(ModelError):ProjectSource(root)
    if kind=='repository':assert (root/'README').read_bytes()==b'original foreign bytes'
    old=preserved(root)
    fresh=tmp_path/'fresh'
    check_project(fresh,dispatch_result(['init',str(fresh)]))
    assert preserved(root)==old
