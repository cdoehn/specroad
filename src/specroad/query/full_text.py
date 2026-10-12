"""Literal Unicode search copies of declared artifact text fields; never I/O."""
import unicodedata

from ..model.errors import ModelError


def full_text_matches(artifact, terms):
    """OR over normalized terms and the artifact's own searchable text fields.

    Data stays in its stored form. No markup execution, include traversal,
    attachment loading or stringification of arbitrary metadata occurs here.
    Callers provide the normalized terms from NormalizedQuery.
    """
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
    copies = tuple(unicodedata.normalize('NFC', text).casefold() for text in texts)
    return any(term in text for term in terms for text in copies)
