"""Explicit permission configuration; no live Codex, SSH or system settings."""
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from specroad_control.config import Config, load, parse, render
from specroad_control.errors import ControlError
from specroad_control.execution_scope import policy
from specroad_control.local import Paths
from specroad_control.toml_compat import tomllib
from codex_control_tests.external_temp import temporary_directory


@pytest.fixture
def settings():
    # Apply owns a repository-local TMPDIR; Control's private-path checks need
    # the existing independent test-home provider, without weakening guards.
    with temporary_directory(prefix='control-mode-') as name:
        root = Path(name)
        dev, exchange, private = (root / part for part in ('dev', 'exchange', 'private'))
        dev.mkdir()
        exchange.mkdir()
        private.mkdir()
        paths = Paths(private / 'config.toml', private / 'state', private / 'run', private / 'unit')
        yield Config(dev, exchange, str(uuid4())), paths


def test_missing_access_setting_preserves_legacy_bytes_and_policy(settings):
    config, paths = settings
    raw = render(config).replace('access_mode = "workspace-write"\n', '').encode()
    paths.config.write_bytes(raw)
    paths.config.chmod(0o600)
    loaded = load(paths)
    assert paths.config.read_bytes() == raw
    assert loaded.access_mode == 'workspace-write'
    assert policy(loaded) == {'approvalPolicy': 'never', 'sandboxPolicy': {
        'type': 'workspaceWrite', 'writableRoots': [str(config.repository), str(config.exchange)],
        'networkAccess': False}}
    assert policy(loaded, readonly=True)['sandboxPolicy'] == {'type': 'readOnly'}


@pytest.mark.parametrize('mode', ['workspace-write', 'full-access'])
def test_explicit_access_setting_roundtrips_without_other_config_changes(settings, mode):
    config, paths = settings
    selected = replace(config, access_mode=mode)
    assert parse(tomllib.loads(render(selected)), paths) == selected


@pytest.mark.parametrize('value', ['', 'full-auto', 'danger-full-access', 'FULL-ACCESS',
                                   'full-access\n', None, True, 1, [], {}])
def test_invalid_access_setting_is_rejected_without_fallback(settings, value):
    config, paths = settings
    doc = tomllib.loads(render(config))
    doc['develop']['access_mode'] = value
    with pytest.raises(ValueError):
        parse(doc, paths)


def test_invalid_programmatic_access_setting_cannot_grant_permissions(settings):
    config, _ = settings
    with pytest.raises(ControlError) as caught:
        policy(replace(config, access_mode='typo'))
    assert caught.value.code == 'invalid_access_mode'


@pytest.mark.parametrize('readonly', [False, True])
def test_full_access_includes_probe_and_has_no_workspace_or_network_restriction(settings, readonly):
    config, _ = settings
    assert policy(replace(config, access_mode='full-access'), readonly=readonly) == {
        'approvalPolicy': 'never', 'sandboxPolicy': {'type': 'dangerFullAccess'}}
