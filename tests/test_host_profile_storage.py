"""Large selected pools remain exact and bounded, including native read boundaries."""
from copy import deepcopy
import json

import pytest

from dev.test_hosts import pool
from dev.test_hosts.config import MAX_HOST_INPUT_BYTES, read_json
from dev.test_hosts.profile_io import read_profile, write_profile
from test_remote_test_hosts_right import profile as small_profile


def test_selected_history_over_input_limit_is_losslessly_prepared(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    for name in ('src/specroad', 'tests', 'tools', 'verification'):
        (root / name).mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[project]\nname="profile-storage"\n')
    output = tmp_path / 'output'; output.mkdir()
    config = tmp_path / 'hosts.json'
    config.write_text(json.dumps({'format_version': 1, 'hosts': [dict(
        name='local', ssh=None, directory=str(tmp_path / 'host'), workers=2)]}))
    env = {'packages': {'pytest-xdist': '3.8.0', 'execnet': '2.1.2'}}
    monkeypatch.setattr(pool, 'environment', lambda: env)
    monkeypatch.setattr(pool, 'available_cpus', lambda: 2)
    monkeypatch.setattr(pool, 'Transport', lambda host: object())
    monkeypatch.setattr(pool, 'check', lambda *a, **kw: dict(hostname='synthetic', account='a' * 64))
    # Every long ID belongs to the actual selection and host. Filtering unrelated
    # history cannot fix this regression. No external host or large project.
    ids = [f'tests/test_subject.py::test_value[{i}-' + 'x' * 1000 + ']' for i in range(4000)]
    selected = {identity: identity for identity in ids}
    selected['tests/test_subject.py::test_mapped'] = 'stable-mapped-id'
    measured = {identity + '\nlocal': float(i % 11) for i, identity in enumerate(selected.values())}
    snapshot = {'tests': [dict(test_id=identity, valid=True, duration_ns=i * 1_000_000)
                          for i, identity in enumerate(selected.values())]}
    original = deepcopy((selected, measured, snapshot))
    monkeypatch.setattr(pool, 'estimates', lambda *a: measured)
    profile, path = pool.prepare_pool(root, output, config, selected, snapshot, 2)
    assert len(json.dumps(profile, sort_keys=True).encode()) > MAX_HOST_INPUT_BYTES
    assert 0 < path.stat().st_size <= MAX_HOST_INPUT_BYTES
    assert path.stat().st_mode & 0o777 == 0o600
    restored = read_profile(path)
    assert restored == profile
    assert pool.public_proof(restored) == pool.public_proof(profile)
    assert restored['selected'] == selected and len(restored['workers']) == 2
    assert restored['estimates'] == measured
    assert restored['baseline'] == {row['test_id']: row['duration_ns'] / 1e9 for row in snapshot['tests']}
    assert (selected, measured, snapshot) == original


@pytest.mark.parametrize('encoded', [False, True])
def test_profile_reader_retains_distinct_identities_and_all_values(tmp_path, encoded):
    value = small_profile()
    node = 'tests/test_x.py::test_ä'
    value['selected'][node] = node
    value['estimates'] = {node + '\nsample': 0.0, 'case\nsample': 9.5}
    value['baseline'][node] = 1.125
    original = deepcopy(value)
    path = tmp_path / 'run.json'
    write_profile(path, value)
    assert read_json(path) == value  # small historical representation is retained
    if encoded:
        wire = dict(value, storage_encoding='selected-key-alias-v1',
                    selected={**value['selected'], node: None})
        path.write_text(json.dumps(wire))
    assert read_profile(path) == original == value


@pytest.mark.parametrize('fault', ['encoding', 'selection-type', 'empty-id', 'duplicate-id',
                                 'worker-gap', 'source', 'extra', 'raw-null', 'duplicate-key', 'utf16', 'nonfinite'])
def test_compact_input_keeps_closed_profile_and_identity_checks(tmp_path, fault):
    value = small_profile()
    node = next(iter(value['selected']))
    value.update(storage_encoding='selected-key-alias-v1', selected={node: None})
    if fault == 'encoding': value['storage_encoding'] = 'unknown'
    elif fault == 'selection-type': value['selected'] = []
    elif fault == 'empty-id': value['selected'][node] = ''
    elif fault == 'duplicate-id': value['selected']['tests/test_x.py::test_b'] = node
    elif fault == 'worker-gap': value['workers']['gw2'] = value['workers'].pop('gw0')
    elif fault == 'source': value['source_sha256'] = 'wrong'
    elif fault == 'extra': value['extra'] = True
    elif fault == 'raw-null': value.pop('storage_encoding')
    elif fault == 'nonfinite': value['baseline']['case'] = float('nan')
    raw = json.dumps(value)
    if fault == 'duplicate-key': raw = '{"storage_encoding":"selected-key-alias-v1",' + raw[1:]
    path = tmp_path / 'run.json'
    path.write_bytes(raw.encode('utf-16' if fault == 'utf16' else 'utf-8'))
    with pytest.raises(ValueError):
        read_profile(path)


@pytest.mark.parametrize('fault', ['linked', 'oversized', 'directory'])
def test_profile_reader_keeps_native_file_guards(tmp_path, fault):
    target = tmp_path / 'target.json'; write_profile(target, small_profile())
    path = tmp_path / 'run.json'
    if fault == 'linked': path.symlink_to(target)
    elif fault == 'directory': path.mkdir()
    else:
        with path.open('wb') as stream:
            stream.truncate(MAX_HOST_INPUT_BYTES + 1)
    with pytest.raises(ValueError):
        read_profile(path)


def test_still_oversized_profile_fails_before_publishing_or_overwriting(tmp_path):
    value = small_profile()
    # No alias can shorten a distinct stable ID. The original size limit stays.
    value['selected'] = {'tests/test_x.py::test_a': 'x' * MAX_HOST_INPUT_BYTES}
    path = tmp_path / 'run.json'
    for existing in (False, True):
        if existing: path.write_bytes(b'previous input')
        with pytest.raises(ValueError):
            write_profile(path, value)
        assert path.read_bytes() == b'previous input' if existing else not path.exists()
