"""Native original source observations and explicit relation removal inputs."""
from ..model.canonical import canonical_json_bytes as jcs
from ..model.errors import ModelError
from ..snapshots.inventory import _source_resource_details
from .sources import MergeSources
from .identity_checks import ROLES


def _same(left, right):
    return jcs(left) == jcs(right)


def _sources(sources):
    if not sources_type(sources):
        raise ModelError('merge_sources_required')
    observed, relations, owners = {}, {}, {}
    for role in ROLES:
        source = getattr(sources, role)
        verify_observation(source)
        observed[role], _, records = _source_resource_details(source)
        relations[role], owners[role] = {}, {}
        # Use qualified navigation for legacy originals, not their raw arrays.
        for record in records:
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

from ._recorded import sources_type

from ._recorded import verify_observation
