"""Source-bound literal Unicode search copies; never canonical storage or I/O."""
from dataclasses import dataclass
from hashlib import sha256

from ..graph.relations import SourceRelations
from ..model.errors import ModelError
from ._full_text_working_copy import _search_copies


@dataclass(frozen=True, init=False)
class SearchText:
    """Owned search observation of one exact source, without a persistent cache.

    Original bytes and their hash remain separate from normalized working copies.
    A decoded mapping, claimed hash or foreign object is not a source record.
    """
    artifact_id: str
    source_sha256: str
    source_bytes: bytes
    _copies: tuple

    def __init__(self, source):
        if type(source) is not SourceRelations:
            raise ModelError('query_search_source_required')
        raw = source.source_bytes
        object.__setattr__(self, 'artifact_id', source.identity.id)
        object.__setattr__(self, 'source_sha256', sha256(raw).hexdigest())
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, '_copies', _search_copies(source.data))

    def matches(self, terms):
        """OR over terms already normalized by the bound NormalizedQuery."""
        return any(term in text for term in terms for text in self._copies)


def full_text_matches(source, terms):
    """Search a fresh observation of the exact input source; never reuse a hint."""
    return SearchText(source).matches(terms)
