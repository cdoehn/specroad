"""Canonical 128-bit Crockford encoding. No entropy or project state access."""

from .errors import ModelError

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

def encode128(value):
    """Encode exactly sixteen octets, preserving all 128 bits and leading zeros."""
    if type(value) is not bytes or len(value) != 16:
        raise ModelError("entropy_bytes_required")
    number = int.from_bytes(value, "big")
    output = []
    for _ in range(26):
        output.append(ALPHABET[number & 31])
        number >>= 5
    return "".join(reversed(output))


def decode128(token):
    """Only canonical uppercase tokens; no Crockford input aliases or padding."""
    if (type(token) is not str or len(token) != 26 or token[0] not in "01234567"
            or any(character not in ALPHABET for character in token)):
        raise ModelError("invalid_identity_token")
    number = 0
    for character in token:
        number = (number << 5) | ALPHABET.index(character)
    return number.to_bytes(16, "big")


