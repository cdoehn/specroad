"""Unchanged host limits keep their durable file and still enforce slot locks."""
import json
import os

import pytest

from dev.test_hosts.lease import Lease, LeaseBusy


def fingerprint(path):
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_mtime_ns, path.read_bytes()


def test_reused_limit_preserves_budget_file_while_slots_remain_exclusive(tmp_path):
    root = tmp_path / 'slots'
    first = Lease(2, directory=root)
    second = None
    try:
        budget = root / 'budget.json'
        before = fingerprint(budget)
        second = Lease(2, directory=root)
        assert first.slot != second.slot
        assert fingerprint(budget) == before
        with pytest.raises(LeaseBusy):
            Lease(2, directory=root)
        assert fingerprint(budget) == before
    finally:
        first.close()
        if second is not None:
            second.close()
    reused = Lease(2, directory=root)
    try:
        assert fingerprint(budget) == before
    finally:
        reused.close()


@pytest.mark.parametrize('wanted', [1, 3])
def test_changed_limit_requires_idle_slots_then_persists_new_limit(tmp_path, wanted):
    root = tmp_path / 'slots'
    first = Lease(2, directory=root)
    budget = root / 'budget.json'
    before = fingerprint(budget)
    try:
        with pytest.raises(ValueError, match='budget change'):
            Lease(wanted, directory=root)
        assert fingerprint(budget) == before
    finally:
        first.close()
    changed = Lease(wanted, directory=root)
    try:
        assert json.loads(budget.read_bytes()) == wanted
        assert 0 <= changed.slot < wanted
    finally:
        changed.close()


@pytest.mark.parametrize('fault', ['symlink', 'dangling', 'hardlink', 'corrupt', 'boolean'])
def test_each_reuse_rechecks_budget_safety_instead_of_trusting_a_cache(tmp_path, fault):
    root = tmp_path / 'slots'
    first = Lease(1, directory=root)
    first.close()
    budget = root / 'budget.json'
    if fault in ('symlink', 'dangling'):
        budget.unlink()
        target = tmp_path / 'other'
        if fault == 'symlink':
            target.write_text('1')
        budget.symlink_to(target)
    elif fault == 'hardlink':
        os.link(budget, tmp_path / 'alias')
    else:
        budget.write_text('{' if fault == 'corrupt' else 'true')
    with pytest.raises(ValueError):
        Lease(1, directory=root)


def test_reuse_retains_existing_file_mode_and_bytes(tmp_path):
    root = tmp_path / 'slots'
    first = Lease(1, directory=root)
    first.close()
    budget = root / 'budget.json'
    budget.chmod(0o400)
    before = fingerprint(budget)
    reused = Lease(1, directory=root)
    try:
        assert fingerprint(budget) == before
        assert budget.stat().st_mode & 0o777 == 0o400
    finally:
        reused.close()


def test_failed_changed_budget_write_keeps_old_limit_and_releases_locks(tmp_path, monkeypatch):
    root = tmp_path / 'slots'
    first = Lease(1, directory=root)
    first.close()
    budget = root / 'budget.json'
    before = fingerprint(budget)

    def fail(_):
        raise OSError('fixture sync failure')

    with monkeypatch.context() as patch:
        patch.setattr('dev.test_hosts.lease.os.fsync', fail)
        with pytest.raises(OSError, match='fixture sync'):
            Lease(2, directory=root)
    assert fingerprint(budget) == before
    assert not list(root.glob('.budget-*'))
    after = Lease(1, directory=root)
    after.close()
