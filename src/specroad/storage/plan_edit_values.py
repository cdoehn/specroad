"""Immutable explicit byte replacements, never a write capability."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceEdit:
    start: int
    end: int
    before: bytes
    after: bytes
