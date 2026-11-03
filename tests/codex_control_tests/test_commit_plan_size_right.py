"""Caller bounds and compression completeness cannot bypass the 64-MiB ceiling."""
from unittest.mock import patch
import zlib
import pytest
from specroad_control import apply_reconcile_proof as proof
from specroad_control.errors import ControlError
from codex_control_tests.plan_size_support import sized_plan, sized_package, write_stream


@pytest.mark.parametrize('limit',[None,True,False,0,-1,1.5,'67108864',64*1024*1024+1])
def test_invalid_or_larger_internal_limit_fails_before_opening_any_proof(limit):
    with patch.object(proof,'member',side_effect=AssertionError('must not open evidence')):
        with pytest.raises(ControlError,match='positive integer no greater than 64 MiB'):
            proof.plan({},data_limit=limit)


def test_smaller_explicit_limit_is_inclusive_and_not_silently_raised(tmp_path):
    fact, expected = sized_package(tmp_path/'small.zip',4096)
    assert proof.plan(fact,data_limit=4096)[0]['stages'][0]['after'] == expected
    with pytest.raises(ControlError,match='Incomplete or oversized compressed plan'):
        proof.plan(fact,data_limit=4095)


@pytest.mark.parametrize('fault',['truncated','trailing','second_stream'])
def test_incomplete_or_concatenated_compression_never_counts_as_a_complete_plan(tmp_path,fault):
    raw, _ = sized_plan(4096); stream = zlib.compress(raw)
    if fault == 'truncated': stream = stream[:-1]
    elif fault == 'trailing': stream += b'foreign'
    else: stream += zlib.compress(b'{}')
    fact = write_stream(tmp_path/(fault+'.zip'),stream)
    with pytest.raises(ControlError,match='Incomplete or oversized compressed plan'):
        proof.plan(fact)


def test_larger_json_budget_does_not_disable_payload_hash_verification(tmp_path):
    import json
    raw, _ = sized_plan(4096); value = json.loads(raw)
    value['stages'][0]['after']['src/a.bin'] = '0'*64
    stream = zlib.compress(json.dumps(value,separators=(',',':')).encode())
    fact = write_stream(tmp_path/'changed-payload.zip',stream)
    with pytest.raises(ControlError,match='Payload differs'):
        proof.plan(fact)
