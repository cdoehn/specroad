"""Installed-code reads retain complete inventory, type, link and permission guards."""
import os
from unittest.mock import patch

import pytest

from codex_control_tests.test_release_runtime import installed_case
from specroad_control import local, releases
from specroad_control.errors import ControlError


@pytest.mark.parametrize('fault', ['changed', 'extra', 'receipt', 'file-symlink',
    'directory-symlink', 'root-symlink', 'fifo', 'hardlink', 'file-permissions',
    'directory-permissions', 'root-permissions', 'oversized', 'git-directory'])
def test_self_verification_rejects_unsafe_release_without_repair(installed_case, fault):
    case = installed_case
    root = case.paths.home / 'releases' / ('a' * 40)
    target = root / 'control'
    if fault == 'changed':
        target.write_bytes(b'changed')
    elif fault == 'extra':
        (root / 'untracked.py').write_bytes(b'pass')
    elif fault == 'receipt':
        (root / 'release.json').write_text('{}')
    elif fault == 'file-symlink':
        saved = case.home / 'saved-control'
        target.rename(saved)
        target.symlink_to(saved)
    elif fault == 'directory-symlink':
        saved = case.home / 'saved-package'
        (root / 'specroad_control').rename(saved)
        (root / 'specroad_control').symlink_to(saved, target_is_directory=True)
    elif fault == 'root-symlink':
        saved = case.home / 'saved-release'
        root.rename(saved)
        root.symlink_to(saved, target_is_directory=True)
    elif fault == 'fifo':
        target.unlink()
        os.mkfifo(target, mode=0o600)
    elif fault == 'hardlink':
        os.link(target, case.home / 'other-link')
    elif fault == 'file-permissions':
        target.chmod(0o640)
    elif fault == 'directory-permissions':
        (root / 'specroad_control').chmod(0o750)
    elif fault == 'root-permissions':
        root.chmod(0o750)
    elif fault == 'oversized':
        target.write_bytes(b'x' * 65537)
    else:
        (root / '.git').mkdir()
    # The running package location is the release itself, as in a real worker.
    with patch.object(local, 'REPO', root):
        with pytest.raises(ControlError) as caught:
            releases.active_entrypoint(case.paths)
        assert caught.value.code == 'release_unproven'
    assert os.path.lexists(root)
    if fault == 'file-permissions':
        assert target.stat().st_mode & 0o777 == 0o640
    if fault == 'file-symlink':
        assert target.is_symlink()
    if fault == 'extra':
        assert (root / 'untracked.py').read_bytes() == b'pass'
