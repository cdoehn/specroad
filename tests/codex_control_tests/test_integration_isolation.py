"""Regressions for repository-local Apply temp paths and library import leaks."""
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
from unittest.mock import patch
import zipfile

import pytest

from codex_control_tests.external_temp import temporary_directory
from codex_control_tests.support import LocalCase
from specroad_control.local import outside, private_dir
from specroad_control.mixed_contract import CAPABILITY, CAPABILITY_PATH
from specroad_control.ph_bridge import development_capability


def test_local_case_ignores_inherited_git_tmpdir_and_cleans_its_home(tmp_path):
    repository = tmp_path / 'repository'
    repository.mkdir()
    (repository / '.git').write_text('gitdir: isolated-test-double')
    inherited = repository / 'build' / ('long-stage-' + 'x' * 80)
    inherited.mkdir(parents=True)
    overrides = {name: str(inherited) for name in ('TMPDIR', 'TMP', 'TEMP')}
    with patch.dict(os.environ, overrides), patch.object(tempfile, 'tempdir', str(inherited)):
        environment = dict(os.environ)
        case = LocalCase()
        try:
            case.setUp()
            home = case.home
            assert outside(home) == home
            assert not home.is_relative_to(repository)
            assert stat.S_IMODE(home.stat().st_mode) == 0o700
            assert case.paths.config.is_relative_to(home)
            private_dir(case.paths.runtime)
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(case.paths.socket))
            assert tempfile.tempdir == str(inherited)
            assert all(os.environ[key] == value for key, value in overrides.items())
        finally:
            case.doCleanups()
        assert not home.exists()
        assert dict(os.environ) == environment
        assert tempfile.tempdir == str(inherited)


def test_short_external_root_can_bind_codex_hash_socket():
    suffix = 'codex-daemon-' + str(os.getuid()) + '/' + 'a' * 64
    with temporary_directory(prefix='sx-', socket_suffix=suffix) as raw:
        root = Path(raw)
        target = root / suffix
        target.parent.mkdir(mode=0o700)
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(target))
        assert outside(target) == target
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert not root.exists()


@pytest.mark.parametrize('case', ['valid', 'absent', 'malformed', 'wrong-hash'])
def test_capability_reader_preserves_import_path_on_every_outcome(tmp_path, case):
    path = tmp_path / 'result.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        if case != 'absent':
            document = CAPABILITY if case != 'malformed' else CAPABILITY | {'implementation_required': 1}
            archive.writestr('base/' + CAPABILITY_PATH, json.dumps(document))
    expected = '0' * 64 if case == 'wrong-hash' else sha256(path.read_bytes()).hexdigest()
    # Restore even on a regression; assert the mutation before restoring it.
    with patch.object(sys, 'path', list(sys.path)):
        original = list(sys.path)
        for _ in range(2):
            if case in ('malformed', 'wrong-hash'):
                with pytest.raises(ValueError):
                    development_capability(path, expected)
            else:
                actual = development_capability(path, expected)
                assert actual == (None if case == 'absent' else CAPABILITY)
            assert sys.path == original


def test_external_home_survives_git_marker_in_shared_temporary_root(monkeypatch):
    """Model the sandbox race in owned directories, never in the host /tmp."""
    from codex_control_tests import external_temp
    with temporary_directory(prefix='sr-') as raw:
        root = Path(raw)
        shared, persistent = root / 't', root / 'v'
        shared.mkdir(); persistent.mkdir()
        parents = {Path('/tmp'): shared, Path('/var/tmp'): persistent}
        real_outside = external_temp.outside
        real_temporary = external_temp.tempfile.TemporaryDirectory

        def observed_outside(path):
            return real_outside(parents.get(path, path))

        def observed_temporary(*, prefix, dir):
            return real_temporary(prefix=prefix, dir=parents.get(dir, dir))

        monkeypatch.setattr(external_temp, 'outside', observed_outside)
        monkeypatch.setattr(external_temp.tempfile, 'TemporaryDirectory', observed_temporary)
        with external_temp.temporary_directory(prefix='h-', socket_suffix='s') as home:
            # The marker appears after initial admission but before later I/O.
            (shared / '.git').mkdir()
            private_dir(Path(home) / 'state')
            assert real_outside(Path(home)) == Path(home)
            assert Path(home).parent == persistent
            assert list(shared.iterdir()) == [shared / '.git']
        assert not Path(home).exists()
