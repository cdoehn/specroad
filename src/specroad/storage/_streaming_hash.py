"""Shared byte-count and completion contracts for trusted streaming adapters."""
from ..security.errors import SafetyViolation


def checked_byte_count(count, received, expected_size):
    count += received
    if count > expected_size:
        raise SafetyViolation('Resource grew during inspection')
    return count


def finished_digest(count, expected_size, digest):
    if count != expected_size:
        raise SafetyViolation('Resource byte count changed during inspection')
    return digest.hexdigest()
