"""Unchanged host limits keep their durable file and still enforce slot locks."""
import json

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
