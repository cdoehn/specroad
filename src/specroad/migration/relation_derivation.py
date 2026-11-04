"""Q.3 source-bound derivations, separate from regular random identity allocation."""
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs
from ..model.identity_tokens import encode128
from ..storage.json_syntax import parse_json_object as parsed
from .reference01.values import SourceInventory, SourceOriginal
from .plan_values import require


def _relation(project, identity, index, relation, seen):
    encoded = jcs(['specroad-relation-migration-0.1-to-0.2-v1', project, identity, index, relation])
    rid = 'REL-' + encode128(sha256(encoded).digest()[:16])
    require(rid not in seen or seen[rid] == encoded, 'migration_relation_id_collision')
    seen[rid] = encoded
    return {'relation_id': rid, 'id_scheme': 'derived128-v1', **relation}


class _SourceRelations:
    """Owned Q.3 projections of exact qualified source originals only.

    The source key includes original bytes, snapshot, role and classification.
    A navigation projection cannot be relabelled as a writable legacy record.
    This internal inventory neither registers a migration nor grants a write.
    """

    def __init__(self, inventory):
        require(type(inventory) is SourceInventory, 'migration_source_inventory_required')
        self._rows = {}
        seen = {}
        project = inventory.data['project_id']
        for original in inventory.originals:
            if original.role != 'artifact':
                continue
            value = original.data
            rows = []
            for index, relation in enumerate(value['relations']):
                projected = _relation(project, value['id'], index, relation, seen)
                rows.append({'index': index, 'relation_id': projected['relation_id'],
                    'id_scheme': projected['id_scheme'], 'original': relation})
            self._rows[original] = jcs({'rows': rows})

    def projections(self, original):
        require(type(original) is SourceOriginal and original in self._rows,
                'migration_relation_source_unbound')
        return parsed(self._rows[original])['rows']

    def materialize(self, original):
        rows = self.projections(original)
        require(original.classification == 'mutable', 'migration_immutable_relations')
        return [{**row['original'], 'relation_id': row['relation_id'],
                 'id_scheme': row['id_scheme']} for row in rows]
