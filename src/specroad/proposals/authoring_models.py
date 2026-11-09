"""Separate owned content and operational projections of a checked original.

Only ProposalOriginal establishes the whole record contract. These internal
projections cannot be assembled into a publication ticket or a human review.
"""
from dataclasses import dataclass

from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from .content import CONTENT_EXCLUSIONS, content_projection


@dataclass(frozen=True, init=False)
class ProposalContent:
    _encoded: bytes

    def __init__(self, original):
        object.__setattr__(self, '_encoded', content_projection(original.data))

    @property
    def data(self):
        return parse_json_object(self._encoded)


@dataclass(frozen=True, init=False)
class ProposalControl:
    _encoded: bytes

    def __init__(self, original):
        data = {key: value for key, value in original.data.items()
                if key in CONTENT_EXCLUSIONS}
        object.__setattr__(self, '_encoded', canonical_json_bytes(data))

    @property
    def data(self):
        return parse_json_object(self._encoded)
