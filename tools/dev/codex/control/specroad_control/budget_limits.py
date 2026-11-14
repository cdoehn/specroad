"""Supported budget bounds; persisted limits are never changed on read."""

CLARIFICATION_LIMITS = (3, 5, 20)
DEFAULT_CORRECTION_LIMIT = 20
MAX_CORRECTION_LIMIT = (1 << 63) - 1  # SQLite integer storage bound, not a project quota.
DEFAULT_CLARIFICATION_LIMIT = 20

def valid_limit(value):
    return type(value) is int and 1 <= value <= MAX_CORRECTION_LIMIT
