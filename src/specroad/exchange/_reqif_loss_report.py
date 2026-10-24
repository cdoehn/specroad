"""Stable machine identities and dispositions for already assessed source units.

Callers supply locations, machine reason codes and verified target proofs.
Human messages, report presentation and export policy are outside this layer.
"""
from ..model.canonical import canonical_json_sha256


def _assessed_items(units, *, direction, source_sha256, source_context):
    items = {}
    for location, reason, preservation in units:
        identity = {'direction': direction, 'source_sha256': source_sha256,
                    'source_context': source_context, 'location': location, 'reason': reason}
        item_id = 'reqif-item-' + canonical_json_sha256(identity)
        item = {**identity, 'item_id': item_id, 'disposition': 'preserved' if preservation is not None else 'lost'}
        if preservation is None:
            item['loss_id'] = item_id
        else:
            item['preservation_ref'] = preservation
        items[item_id] = item
    return items
