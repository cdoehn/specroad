"""Exact host forecasts fit bounded storage without reducing gate coverage."""
from copy import deepcopy
import json
import math

import pytest

from dev.test_hosts.config import MAX_HOST_INPUT_BYTES, read_json
from dev.test_hosts.pool import public_proof
from dev.test_hosts.profile_io import read_profile, write_profile
from test_remote_test_hosts_right import profile as small_profile


ENCODING = 'selected-key-alias-and-forecasts-v1'


def many_hosts(count):
    value = small_profile()
    template = value['workers']['gw0']
    value['workers'] = {f'gw{i}': dict(template, host=f'synthetic-{i}',
        hostname=f'synthetic-{i}', account=f'{i + 1:064x}') for i in range(count)}
    return value


def grouped_wire(value):
    groups = {}
    for key, duration in value['estimates'].items():
        identity, _, host = key.rpartition('\n')
        groups.setdefault(identity, {})[host] = duration
    return dict(value, storage_encoding=ENCODING,
        selected={n: None if n == i else i for n, i in value['selected'].items()}, estimates=groups)


def test_five_host_forecasts_preserve_every_selected_test_and_measurement(tmp_path):
    value = many_hosts(5)
    ids = [f'tests/test_subject.py::test_value[{i}-' + 'x' * 1200 + ']' for i in range(2200)]
    value['selected'] = {identity: identity for identity in ids}
    value['selected']['tests/test_subject.py::test_mapped'] = 'separate-stable-id'
    value['baseline'] = {identity: float(i % 31) for i, identity in enumerate(value['selected'].values())}
    value['estimates'] = {identity + '\n' + row['host']: float(i % 17)
        for i, identity in enumerate(value['selected'].values()) for row in value['workers'].values()}
    original = deepcopy(value)
    previous = dict(value, storage_encoding='selected-key-alias-v1',
        selected={n: None if n == i else i for n, i in value['selected'].items()})
    assert len(json.dumps(previous, separators=(',', ':')).encode()) > MAX_HOST_INPUT_BYTES
    path = tmp_path / 'profile.json'
    write_profile(path, value)
    assert 0 < path.stat().st_size <= MAX_HOST_INPUT_BYTES
    assert path.stat().st_mode & 0o777 == 0o600
    assert read_json(path)['storage_encoding'] == ENCODING
    restored = read_profile(path)
    assert restored == original == value
    assert public_proof(restored) == public_proof(original)
    assert len(restored['selected']) == 2201 and len(restored['estimates']) == 11005


@pytest.mark.parametrize('encoding', ['plain', 'selected-key-alias-v1', ENCODING])
def test_plain_and_both_compact_encodings_keep_exact_identities_and_values(tmp_path, encoding):
    value = small_profile()
    node = 'tests/test_subject.py::test_ä[quote"\\]'
    value['selected'][node] = node
    value['baseline'][node] = 1.125
    value['estimates'] = {'case\nsample': 259200, node + '\nsample': -0.0}
    wire = deepcopy(value)
    if encoding == ENCODING:
        wire = grouped_wire(value)
    elif encoding != 'plain':
        wire.update(storage_encoding=encoding, selected={n: None if n == i else i
            for n, i in value['selected'].items()})
    path = tmp_path / 'profile.json'; path.write_text(json.dumps(wire))
    restored = read_profile(path)
    assert restored == value
    assert math.copysign(1.0, restored['estimates'][node + '\nsample']) == -1.0


@pytest.mark.parametrize('fault', ['groups-list', 'row-list', 'empty-row', 'unknown-id',
    'unknown-host', 'boolean', 'negative', 'too-large', 'text', 'nan', 'infinity',
    'extra-field', 'source', 'duplicate-host', 'duplicate-identity'])
def test_grouped_forecasts_reject_malformed_or_unbound_values(tmp_path, fault):
    value = small_profile(); value['estimates'] = {'case\nsample': 1.25}
    wire = grouped_wire(value)
    if fault == 'groups-list': wire['estimates'] = []
    elif fault == 'row-list': wire['estimates']['case'] = []
    elif fault == 'empty-row': wire['estimates']['case'] = {}
    elif fault == 'unknown-id': wire['estimates'] = {'unselected': {'sample': 1.25}}
    elif fault == 'unknown-host': wire['estimates']['case'] = {'foreign': 1.25}
    elif fault in ('boolean', 'negative', 'too-large', 'text', 'nan', 'infinity'):
        wire['estimates']['case']['sample'] = {'boolean': True, 'negative': -1,
            'too-large': 259201, 'text': '1', 'nan': float('nan'), 'infinity': float('inf')}[fault]
    elif fault == 'extra-field': wire['ignored'] = True
    elif fault == 'source': wire['source_sha256'] = 'wrong'
    raw = json.dumps(wire)
    if fault == 'duplicate-host': raw = raw.replace('"sample": 1.25', '"sample": 1.25, "sample": 2')
    elif fault == 'duplicate-identity':
        raw = raw.replace('"estimates": {', '"estimates": {"case": {"sample": 2}, ')
    path = tmp_path / 'profile.json'; path.write_text(raw)
    with pytest.raises(ValueError): read_profile(path)


def test_large_expansion_is_rejected_before_publishing_and_when_reading(tmp_path):
    value = many_hosts(16)
    ids = [f'tests/test_subject.py::test_value[{i}-' + 'x' * 6000 + ']' for i in range(400)]
    value['selected'] = {identity: identity for identity in ids}
    value['baseline'] = {}
    value['estimates'] = {identity + '\n' + row['host']: 1.0
        for identity in ids for row in value['workers'].values()}
    assert len(json.dumps(value).encode()) > 2 * MAX_HOST_INPUT_BYTES
    path = tmp_path / 'profile.json'; path.write_bytes(b'previous profile')
    with pytest.raises(ValueError): write_profile(path, value)
    assert path.read_bytes() == b'previous profile'
    raw = json.dumps(grouped_wire(value)).encode()
    assert len(raw) < MAX_HOST_INPUT_BYTES
    path.write_bytes(raw)
    with pytest.raises(ValueError): read_profile(path)


@pytest.mark.parametrize('empty', [False, True])
def test_expansion_limit_counts_the_full_json_including_escaped_keys(tmp_path, monkeypatch, empty):
    from dev.test_hosts import profile_io
    value = small_profile()
    value['estimates'] = {} if empty else {'case\nsample': 1.125}
    expected = len(json.dumps(value, sort_keys=True).encode('utf-8'))
    path = tmp_path / 'profile.json'; path.write_text(json.dumps(grouped_wire(value)))
    monkeypatch.setattr(profile_io, 'MAX_EXPANDED_PROFILE_BYTES', expected)
    assert read_profile(path) == value
    monkeypatch.setattr(profile_io, 'MAX_EXPANDED_PROFILE_BYTES', expected - 1)
    with pytest.raises(ValueError): read_profile(path)
