"""Concurrent operators, stale generations and rejected host execution evidence."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os

import pytest

from dev.test_control.store import Owner, change, configure, lane, read_status
from dev.test_hosts.contract import public_proof, verify_pool, validate_profile
from test_remote_test_hosts_right import profile


def test_parallel_operator_updates_merge_without_crossing_apply_lanes(tmp_path):
    root, home = tmp_path / 'apply', tmp_path / 'state'
    values = {f'host{i}': 2 for i in range(8)}
    owner = Owner(root, values, values, home=home)
    try:
        def update(item):
            configure(root, {item: 1}, home=home)
            change(root, owner.run, {item: 0}, home=home)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(update, values))
        assert configure(root, home=home) == dict.fromkeys(values, 1)
        assert owner.refresh() == dict.fromkeys(values, 0)
        assert read_status(tmp_path/'apply2', home=home) is None
    finally:
        owner.close()


@pytest.mark.parametrize('fault', ['linked', 'hardlinked', 'public', 'duplicate', 'version', 'unknown', 'missing'])
def test_bad_request_cannot_turn_into_permission(tmp_path, fault):
    root, home = tmp_path / 'apply', tmp_path / 'state'
    owner = Owner(root, {'host': 2}, {'host': 2}, home=home)
    request = owner.root / 'request.json'
    try:
        if fault == 'linked':
            raw = request.read_bytes(); request.unlink()
            target = tmp_path / 'outside'; target.write_bytes(raw); request.symlink_to(target)
        elif fault == 'hardlinked':
            os.link(request, tmp_path / 'alias')
        elif fault == 'public':
            request.chmod(0o644)
        elif fault == 'duplicate':
            request.write_text('{"version":1,"version":1}')
        elif fault == 'missing':
            request.unlink()
        else:
            value = json.loads(request.read_bytes())
            if fault == 'version': value['version'] = True
            else: value['workers']['unknown'] = 0
            request.write_text(json.dumps(value))
        with pytest.raises((ValueError, OSError)):
            owner.refresh()
        assert owner.desired == {'host': 2}
    finally:
        owner.close()


def test_missing_reader_is_read_only_and_crashed_generation_is_not_active(tmp_path):
    root, home = tmp_path / 'apply', tmp_path / 'state'
    assert read_status(root, home=home) is None and not home.exists()
    owner = Owner(root, {'host': 2}, {'host': 2}, home=home)
    owner.close()
    before = {p.name:p.read_bytes() for p in lane(root, home).iterdir() if p.is_file()}
    assert not read_status(root, home=home)['active']
    with pytest.raises(ValueError):
        change(root, owner.run, {'host': 0}, home=home)
    assert before == {p.name:p.read_bytes() for p in lane(root, home).iterdir() if p.is_file()}


def test_replaced_owner_lock_rejects_further_dispatch(tmp_path):
    owner = Owner(tmp_path/'apply', {'host': 2}, {'host': 2}, home=tmp_path/'state')
    try:
        (owner.root/'owner').unlink()
        (owner.root/'owner').touch(mode=0o600)
        with pytest.raises(ValueError):
            owner.refresh()
    finally:
        owner.close()


def live_evidence():
    value = profile()
    value.update(format_version=2, live=dict(repository='/tmp/fixture/apply', home='/tmp/fixture/state', overrides={}))
    value['selected'] = {'tests/test_x.py::test_a': 'case-a', 'tests/test_x.py::test_b': 'case-b'}
    binding = public_proof(value); expected = value['workers']['gw0']
    row = dict(host=expected['host'], hostname=expected['hostname'], account=expected['account'],
        environment_sha256=expected['environment_sha256'], source_sha256=value['source_sha256'],
        snapshot_sha256=value['snapshot_sha256'], resources={**expected['resources'], 'nice_actual': 10},
        io_priority={'class': 2, 'priority': 7})
    workers = {f'gw{i}': {**row, 'leases': [dict(nodeid=node, slot=0, start=10*i+1, end=10*i+9)]}
               for i, node in enumerate(value['selected'])}
    observed = dict(nodeids=list(value['selected']), workers=list(workers), worker_test_counts={'gw0':1, 'gw1':1},
        host_pool=dict(binding=binding, workers=workers, launched={'gw0':'gw0', 'gw1':'gw0'}, errors=[],
            selected=list(value['selected']), grants={f'gw{i}':[dict(index=i, slot=0)] for i in range(2)}))
    return observed, binding


@pytest.mark.parametrize('fault', [None, 'duplicate', 'overlap', 'missing', 'extra', 'source', 'environment', 'priority', 'permission', 'selection', 'template'])
def test_dynamic_proof_accepts_serial_slot_reuse_but_rejects_lost_or_forged_attempts(fault):
    observed, binding = live_evidence()
    if fault is None:
        verify_pool(observed, binding)
        return
    pool = observed['host_pool']; worker = pool['workers']['gw1']
    if fault == 'duplicate': worker['leases'][0]['nodeid'] = observed['nodeids'][0]
    elif fault == 'overlap': worker['leases'][0]['start'] = 5
    elif fault == 'missing': worker['leases'] = []
    elif fault == 'extra': observed['workers'].append('gw9')
    elif fault == 'source': worker['source_sha256'] = '0'*64
    elif fault == 'environment': worker['environment_sha256'] = '0'*64
    elif fault == 'priority': worker['io_priority'] = {'class': 1, 'priority': 0}
    elif fault == 'permission': pool['grants']['gw1'][0]['index'] = 0
    elif fault == 'selection': pool['selected'].append('uncollected')
    elif fault == 'template': pool['launched']['gw1'] = 'unapproved'
    with pytest.raises(ValueError):
        verify_pool(observed, binding)


@pytest.mark.parametrize('override', [{'sample': 2}, {'unknown': 1}, {'sample': -1}, {'sample': True}])
def test_invocation_override_cannot_expand_checked_environment(override):
    value = profile()
    value.update(format_version=2, live=dict(repository='/tmp/fixture/apply', home='/tmp/fixture/state', overrides=override))
    with pytest.raises(ValueError):
        validate_profile(value)
