"""Operator intent, native host quota and the exact running-gate contract."""
import json
from types import SimpleNamespace

import pytest

from dev.test_control.store import Owner, change, configure, read_status
from dev.test_hosts.lease import Lease, LeaseBusy


def test_defaults_overrides_and_live_changes_remain_separate(tmp_path):
    root, home = tmp_path / 'apply', tmp_path / 'state'
    configure(root, {'local': 1}, home=home)
    owner = Owner(root, {'local': 3}, {'local': 3}, {'local': 2}, home=home)
    try:
        assert owner.desired == {'local': 2}
        request = change(root, owner.run, {'local': 0}, home=home)
        assert not request['acknowledged'] and owner.desired == {'local': 2}
        owner.refresh(); owner.publish({'local': {'running': 1, 'draining': 1, 'processes': 1}})
        status = read_status(root, home=home)
        assert status['active'] and status['desired'] == {'local': 0}
        assert status['hosts']['local']['running'] == 1
        assert configure(root, home=home) == {'local': 1}
    finally:
        owner.close()
    assert read_status(root, home=home)['active'] is False
    fresh = Owner(root, {'local': 3}, {'local': 3}, home=home)
    try:
        assert fresh.desired == {'local': 1} and fresh.run != owner.run
        with pytest.raises(ValueError):
            change(root, owner.run, {'local': 3}, home=home)
    finally:
        fresh.close()


def test_two_lines_have_independent_requests_but_share_atomic_host_slots(tmp_path):
    one = Owner(tmp_path / 'apply', {'host': 1}, {'host': 1}, home=tmp_path / 'state')
    two = Owner(tmp_path / 'apply2', {'host': 1}, {'host': 1}, home=tmp_path / 'state')
    first = Lease(1, directory=tmp_path / 'slots')
    try:
        change(tmp_path / 'apply', one.run, {'host': 0}, home=tmp_path / 'state')
        assert one.refresh() == {'host': 0} and two.refresh() == {'host': 1}
        with pytest.raises(LeaseBusy):
            Lease(1, directory=tmp_path / 'slots')
        with pytest.raises(BlockingIOError):
            Owner(tmp_path / 'apply2', {'host': 1}, {'host': 1}, home=tmp_path / 'state')
    finally:
        first.close(); one.close(); two.close()
    after = Lease(1, directory=tmp_path / 'slots'); after.close()


@pytest.mark.parametrize('value', [-1, 257, True, '2', 1.5, None])
def test_invalid_worker_counts_do_not_replace_live_request(tmp_path, value):
    owner = Owner(tmp_path / 'apply', {'host': 2}, {'host': 2}, home=tmp_path / 'state')
    try:
        before = (owner.root / 'request.json').read_bytes()
        with pytest.raises(ValueError):
            change(tmp_path / 'apply', owner.run, {'host': value}, home=tmp_path / 'state')
        assert (owner.root / 'request.json').read_bytes() == before
    finally:
        owner.close()


def test_unknown_host_and_capacity_violation_do_not_start_anything(tmp_path):
    owner = Owner(tmp_path / 'apply', {'host': 2}, {'host': 2}, home=tmp_path / 'state')
    try:
        for updates in ({'host': 3}, {'other': 1}):
            with pytest.raises(ValueError):
                change(tmp_path / 'apply', owner.run, updates, home=tmp_path / 'state')
        assert owner.refresh() == {'host': 2}
    finally:
        owner.close()


def test_machine_cli_changes_only_named_live_run(tmp_path, monkeypatch, capsys):
    from dev.test_control.cli import main
    home = tmp_path / 'state'; root = tmp_path / 'apply'
    monkeypatch.setenv('SPECROAD_TEST_CONTROL_HOME', str(home))
    owner = Owner(root, {'host': 2}, {'host': 2})
    try:
        args = ['--apply-dir', str(root), '--json']
        assert main(args + ['workers', '--run', owner.run, '--host', 'host', '--workers', '0']) == 0
        assert json.loads(capsys.readouterr().out)['requested'] == {'host': 0}
        assert owner.refresh() == {'host': 0}
        assert main(args + ['workers', '--run', 'stale', '--host', 'host', '--workers', '1']) == 2
        assert 'error' in json.loads(capsys.readouterr().err)
    finally:
        owner.close()
