"""Source-bound literal Unicode search copies; never canonical storage or I/O."""
from dataclasses import dataclass
from hashlib import sha256
import unicodedata

from ..graph.relations import SourceRelations
from ..model.errors import ModelError


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


def _search_copies(artifact):
    primary = {'goal': 'statement', 'need': 'statement', 'requirement': 'statement',
        'assumption': 'statement', 'decision': 'decision', 'scenario': 'main_flow',
        'component': 'responsibility', 'release': 'objective', 'milestone': 'objective',
        'term': 'definition', 'document': 'purpose', 'proposal': 'rationale'}
    fields = ['title', 'description', 'term']
    if artifact['artifact_type'] in primary:
        fields.append(primary[artifact['artifact_type']])
    texts = []
    for name in fields:
        if name not in artifact:
            continue
        value = artifact[name]
        if name == 'main_flow':
            if type(value) is not list or any(type(item) is not str for item in value):
                raise ModelError('query_search_text_invalid', pointer='/' + name)
            texts.extend(value)
        else:
            if type(value) is not str:
                raise ModelError('query_search_text_invalid', pointer='/' + name)
            texts.append(value)
    if artifact['artifact_type'] == 'content_block' and artifact.get('block_kind') in ('prose', 'admonition'):
        payload = artifact.get('payload')
        if type(payload) is not dict or type(payload.get('markdown')) is not str:
            raise ModelError('query_search_text_invalid', pointer='/payload/markdown')
        texts.append(payload['markdown'])
    return tuple(unicodedata.normalize('NFC', text).casefold() for text in texts)
