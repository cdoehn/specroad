"""Synthetic presentation models. No renderer or language detector observations."""
from .artifacts import artifact_bytes
from .domain import domain_value, relation
from .records import record_value, block_value
from specroad.languages.containers import ContainerModel

ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

def token(n):
    result = ''
    while n:
        result = ALPHABET[n % 32] + result; n //= 32
    return result.rjust(26, '0')

def node(kind, number=1, **values):
    value = domain_value(kind) if kind in ('requirement', 'goal', 'need', 'component') else record_value(kind)
    value['id'] = value['id'][:-26] + token(number)
    value.update(values)
    return value

def edge(kind, target, number, **values):
    value = relation(kind, target['id'] if isinstance(target, dict) else target)
    value['relation_id'] = 'REL-' + token(number)
    if kind == 'contains': value['position'] = number
    value.update(values)
    return value

def ref_block(target, number=1):
    value = block_value('artifact_ref'); value['id'] = value['id'][:-26] + token(number)
    value['relations'] = [edge('references', target, 1000000 + number)]
    return value

def model(*values):
    return ContainerModel([artifact_bytes(v) for v in values])

def presentation(*requirements, **doc_options):
    doc, section = node('document', **doc_options), node('section')
    doc['relations'] = [edge('contains', section, 1)]
    blocks = [ref_block(r, i+1) for i,r in enumerate(requirements)]
    section['relations'] = [edge('contains', b, i+2) for i,b in enumerate(blocks)]
    return model(doc, section, *blocks, *requirements), doc['id'], section['id']
