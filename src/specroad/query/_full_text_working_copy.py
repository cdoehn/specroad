"""Pure search text derivation; no source identity, canonical writer or cache."""
import unicodedata

from ..model.errors import ModelError


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
