"""Bounded-memory byte hashing for inventory, future snapshots and Work units.

A trusted caller supplies the read operation and validates its descriptor/path
before and after this operation. This helper alone is not a filesystem guard.
"""

from dataclasses import dataclass
from hashlib import sha256

from ..security.errors import SafetyViolation


@dataclass(frozen=True)
class ByteFingerprint:
    size: int
    sha256: str


def validate_block_size(block_size):
    if type(block_size) is not int or not 1 <= block_size <= 1048576:
        raise ValueError("Block size must be between 1 and 1048576 bytes")


def fingerprint_reader(read, expected_size, *, block_size=65536):
    validate_block_size(block_size)
    digest = sha256()
    count = 0
    while True:
        block = read(block_size)
        if not block:
            break
        digest.update(block)
        count += len(block)
        if count > expected_size:
            raise SafetyViolation("Resource grew during inspection")
    if count != expected_size:
        raise SafetyViolation("Resource byte count changed during inspection")
    return ByteFingerprint(count, digest.hexdigest())
