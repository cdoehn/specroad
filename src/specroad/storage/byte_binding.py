"""Bounded-memory byte hashing for inventory, future snapshots and Work units.

A trusted caller supplies the read operation and validates its descriptor/path
before and after this operation. This helper alone is not a filesystem guard.
"""

from dataclasses import dataclass
from hashlib import sha256

from ..security.errors import SafetyViolation
from ..runtime.control_points import ControlIntervals, PhaseBoundary, complete_steps


@dataclass(frozen=True)
class ByteFingerprint:
    size: int
    sha256: str


def validate_block_size(block_size):
    if type(block_size) is not int or not 1 <= block_size <= 1048576:
        raise ValueError("Block size must be between 1 and 1048576 bytes")


def fingerprint_reader(read, expected_size, *, block_size=65536):
    return complete_steps(fingerprint_steps(read, expected_size, block_size=block_size, controlled=False))


def fingerprint_steps(read, expected_size, *, block_size=65536, controlled=True):
    validate_block_size(block_size)
    controls = ControlIntervals() if controlled else None
    if controls is not None:
        yield PhaseBoundary('payload_hash', 'start')
    digest = sha256()
    count = 0
    while True:
        requested = block_size if controls is None else min(block_size, controls.remaining('payload_bytes'))
        block = read(requested)
        if controls is not None and (type(block) is not bytes or len(block) > requested):
            raise SafetyViolation('Reader did not honor the bounded byte request')
        if not block:
            break
        digest.update(block)
        count += len(block)
        if count > expected_size:
            raise SafetyViolation("Resource grew during inspection")
        if controls is not None:
            point = controls.advance('payload_bytes', len(block))
            if point is not None:
                yield point
    if count != expected_size:
        raise SafetyViolation("Resource byte count changed during inspection")
    result = ByteFingerprint(count, digest.hexdigest())
    if controls is not None:
        yield PhaseBoundary('payload_hash', 'end')
    return result
