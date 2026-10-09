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


def allocate_transfer_buffer(block_size=65536, *, attempts=None):
    """Reserve one conservative payload buffer before consuming any input.

    Only a failed buffer allocation is retried. An exception after a read may
    have advanced the source and must never cause an implicit read retry.
    Actual allocation success is not a promise of future host availability.
    """
    validate_block_size(block_size)
    capacity = min(block_size, 65536)
    while True:
        if attempts is not None:
            attempts.append(capacity)
        try:
            return bytearray(capacity)
        except MemoryError:
            if capacity == 1:
                raise
            capacity = max(1, capacity // 2)


def fingerprint_into_steps(readinto, expected_size, buffer):
    """Hash a trusted synchronous reader using the same caller-owned buffer.

    The reader fills only its provided view and returns the actual byte count.
    It must not retain or mutate that view after returning. This is a transfer
    primitive; the caller still owns path/descriptor and host-error handling.
    """
    if type(buffer) is not bytearray or not 1 <= len(buffer) <= 65536:
        raise ValueError('A bounded writable byte buffer is required')
    controls = ControlIntervals()
    yield PhaseBoundary('payload_hash', 'start')
    digest = sha256()
    count = 0
    with memoryview(buffer) as view:
        while True:
            requested = min(len(view), controls.remaining('payload_bytes'))
            with view[:requested] as transfer:
                received = readinto(transfer)
                if type(received) is not int or not 0 <= received <= requested:
                    raise SafetyViolation('Reader did not honor the bounded byte request')
                if received == 0:
                    break
                count += received
                if count > expected_size:
                    raise SafetyViolation('Resource grew during inspection')
                with transfer[:received] as filled:
                    digest.update(filled)
            point = controls.advance('payload_bytes', received)
            if point is not None:
                yield point
    if count != expected_size:
        raise SafetyViolation('Resource byte count changed during inspection')
    result = ByteFingerprint(count, digest.hexdigest())
    yield PhaseBoundary('payload_hash', 'end')
    return result
