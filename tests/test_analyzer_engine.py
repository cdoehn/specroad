"""Owned inventory fixtures; actual engines remain in the five-runtime matrix."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json

import pytest

from specroad.analyzers._values import encoded
from specroad.analyzers._reference_backend import ReferenceEngine
from specroad.analyzers._reference_candidates import CANDIDATES, CANDIDATES_SHA256
from specroad.analyzers.engine_identity import engine_identity
from test_analyzer_policy import case, assess
from test_analyzer_comparison import detected


def engine():
    # Explicit synthetic observations, not measurements of this test process.
    return ReferenceEngine('1.0.0', (('numpy', '2.3.5'), ('py3langid', '0.4.0')),
        'a' * 64, CANDIDATES, CANDIDATES_SHA256, 'cpython', '3.12.0', '15.0.0',
        encoded(dict(inventory_version='numeric-runtime-v1', implementation='cpython',
                     python_version='3.12.0', executable_sha256='b' * 64, byteorder='little')),
        encoded(dict(inventory_version='numpy-runtime-v1', version='2.3.5',
                     binaries=[dict(name='example.so', sha256='c' * 64)], cpu_features={'SSE2': True})))


def test_every_engine_fact_is_bound_to_owned_inventory():
    value = engine_identity(engine())
    assert value.reproducible is True
    data = value.data
    assert data['adapter_version'] == '1.0.0'
    assert data['library_versions']['value'] == {'numpy': '2.3.5', 'py3langid': '0.4.0'}
    assert data['model_sha256']['value'] == 'a' * 64
    assert data['candidates']['value'] == list(CANDIDATES)
    assert data['candidates_sha256']['value'] == CANDIDATES_SHA256
    assert data['preprocessing_version']['value'] == 'ascii-edge-codepoints-v1'
    assert data['unicode_version']['value'] == '15.0.0'
    for name in ('runtime', 'numpy'):
        raw = json.dumps(value.inventory[name], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        assert data[name + '_fingerprint'] == dict(value=sha256(raw).hexdigest(), reason=None)
    assert value.sha256 == sha256(encoded(data)).hexdigest()


def test_same_inputs_and_engine_have_same_observation_despite_distinct_runs():
    request, decisions = case([('en', detected('fr'))])
    decisions = replace(decisions, engine=engine())
    first, second = assess(request, decisions).report, assess(request, decisions).report
    assert first.result_sha256 == second.result_sha256
    assert first.observation == second.observation
    assert first.data['run_id'] != second.data['run_id']
    assert first.full_file_sha256 != second.full_file_sha256
    assert first.data['extensions']['specroad.engine_inventory'] == engine_identity(decisions.engine).inventory


def test_inventory_and_engine_properties_are_detached_and_immutable():
    identity = engine_identity(engine())
    before = identity.sha256
    identity.data['library_versions']['value']['numpy'] = 'foreign'
    identity.inventory['numpy']['version'] = 'foreign'
    assert identity.sha256 == before and identity.inventory['numpy']['version'] == '2.3.5'
    with pytest.raises(FrozenInstanceError):
        identity._engine = b'{}'


@pytest.mark.parametrize('field', ['runtime_inventory', 'numpy_inventory'])
def test_unknown_numeric_facts_do_not_claim_reproducibility(field):
    identity = engine_identity(replace(engine(), **{field: None}))
    name = field.removesuffix('_inventory')
    assert identity.reproducible is False
    assert identity.data[name + '_fingerprint'] == dict(value=None, reason='numeric_inventory_unavailable')
    assert identity.inventory[name] is None


def test_no_loaded_engine_is_not_a_known_engine():
    assert not engine_identity(None).reproducible
    assert engine_identity(None).inventory == dict(runtime=None, numpy=None)
