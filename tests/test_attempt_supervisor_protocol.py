"""Bounded wire messages preserve identities and reject incomplete evidence."""
from io import BytesIO
import json

import pytest

from dev.test_hosts.attempt_supervisor import MAX_MESSAGE_BYTES, _encode_message, _read_message


def test_large_identity_and_receipt_survive_encoded_wire_roundtrip():
    attempt = dict(token='a'*32, nodeid='tests/test_native.py::test_bytes[' + '\0'*70000 + ']')
    receipt = dict(cancelled=True, attempt=attempt, completed=[attempt], children_remaining=0)
    data = _encode_message(receipt)
    assert len(data) > 65536
    assert _read_message(BytesIO(data)) == receipt


@pytest.mark.parametrize('kind', ['truncated', 'oversized', 'array', 'malformed'])
def test_invalid_wire_frame_cannot_supply_a_supervisor_receipt(kind):
    valid = json.dumps(dict(cancelled=True, children_remaining=0)).encode()
    if kind == 'oversized':
        data = b' ' * MAX_MESSAGE_BYTES + valid + b'\n'
    else:
        data = {'truncated': valid, 'array': b'[]\n', 'malformed': b'{broken}\n'}[kind]
    with pytest.raises(ValueError):
        _read_message(BytesIO(data))


def test_outgoing_limit_counts_encoded_bytes_and_complete_frame():
    # JSON escaping costs more bytes than the decoded identity; no truncation.
    value = dict(nodeid='\0' * (MAX_MESSAGE_BYTES // 6))
    assert len(value['nodeid']) < MAX_MESSAGE_BYTES
    with pytest.raises(ValueError):
        _encode_message(value)


def test_complete_frame_at_byte_limit_remains_accepted():
    overhead = len(_encode_message(dict(nodeid='')))
    value = dict(nodeid='q' * (MAX_MESSAGE_BYTES - overhead))
    data = _encode_message(value)
    assert len(data) == MAX_MESSAGE_BYTES
    assert _read_message(BytesIO(data)) == value
