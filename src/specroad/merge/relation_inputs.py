"""Native original source observations and explicit relation removal inputs."""
from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..snapshots.inventory import source_resource_rows
from .sources import MergeSources
from .identity_checks import ROLES


def _same(left, right):
    return jcs(left) == jcs(right)


def _sources(sources):
    if type(sources) is not MergeSources:
        raise ModelError('merge_sources_required')
    observed, relations, owners = {}, {}, {}
    for role in ROLES:
        source = getattr(sources, role)
        source.verify_current()
        observed[role], _ = source_resource_rows(source)
        relations[role], owners[role] = {}, {}
        # Use qualified navigation for legacy originals, not their raw arrays.
        from ..bundles._payload_model import owned_payload_model
        from ..migration.model_inputs import records
        keys = tuple(source.binding['baseline']['profile_keys']) if source.kind == 'baseline' else None
        model = owned_payload_model(source.files, source_label='merge-relations:' + source.source_root,
                                    profile_keys=keys)
        for record in records(model):
            owners[role][record.identity.id] = record.identity
            for relation in record.relations:
                relations[role][relation.identity.id] = {'owner_id': record.identity.id,
                                                        'relation': relation.data}
    return observed, relations, owners


def _removals(values, base, side):
    if type(values) not in (list, tuple):
        raise ModelError('invalid_relation_removal')
    seen = set()
    for value in values:
        if type(value) is not str or value in seen or value not in base or value in side:
            raise ModelError('invalid_relation_removal')
        seen.add(value)
    return seen
