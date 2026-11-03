"""Real installed-process startup and read-only self-verification regressions."""
from hashlib import sha256
from unittest.mock import patch

import pytest

from codex_control_tests.support import LocalCase
from specroad_control import local, releases
from specroad_control.errors import ControlError
from specroad_control.ipc import request


@pytest.fixture
def installed_case():
    case = LocalCase()
    try:
        case.setUp()
        yield case
    finally:
        case.doCleanups()


def inventory(root):
    return {p.relative_to(root).as_posix(): (sha256(p.read_bytes()).hexdigest(),
            p.stat().st_mode, p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


def test_installed_worker_verifies_itself_without_writing_runtime_code(installed_case):
    case = installed_case
    root = case.paths.home / 'releases' / ('a' * 40)
    before = inventory(root)
    child, reply = case.spawn()
    assert reply['state']['phase'] == 'idle'
    assert reply['state']['development_enabled'] is False
    request(case.paths, 'stop')
    assert child.wait(timeout=5) == 0
    assert inventory(root) == before


def test_self_verification_does_not_admit_operational_writes_into_code(installed_case):
    paths = installed_case.paths
    root = paths.home / 'releases' / ('a' * 40)
    before = inventory(root)
    with patch.object(local, 'REPO', root):
        assert releases.active_entrypoint(paths) == root / 'control'
        with pytest.raises(ControlError) as caught:
            local.write_private(root / 'new-state.json', b'{}')
        assert caught.value.code == 'local_path_in_repository'
        with pytest.raises(ControlError):
            local.private_dir(root / 'state')
    assert inventory(root) == before
    assert not (root / 'new-state.json').exists()
    assert not (root / 'state').exists()


def test_missing_release_is_rejected_without_recreating_directories(installed_case):
    paths = installed_case.paths
    root = paths.home / 'releases' / ('a' * 40)
    root.rename(root.with_name('saved'))
    with pytest.raises(ControlError) as caught:
        releases.active_entrypoint(paths)
    assert caught.value.code == 'release_unproven'
    assert not root.exists()
