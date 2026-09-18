"""Fresh current-project inputs for artifact-only seed selectors.

Release and document selectors read the complete current artifact membership,
not just displayed targets. Full-resource scopes need their separate inventory
providers; query/configuration engines and closure are deliberately not faked.
"""
from dataclasses import dataclass

from ..graph.scope_descriptors import ScopeDescriptor
from ..graph.scope_inputs import ScopeSeedInputs
from ..graph.scope_seeds import ScopeSeeds, resolve_scope_seeds
from ..model.errors import ModelError
from ._relation_snapshot import RelationSourceBinding, _capture_sources, _check_snapshot_current


@dataclass(frozen=True)
class ProjectScopeSeeds:
    selection: ScopeSeeds
    binding: RelationSourceBinding
    source_count: int

    @property
    def atomic_snapshot(self):
        return False

    @property
    def coverage_scope(self):
        return 'current_project_artifact_seed_selection'


def read_artifact_scope_seeds(source, descriptor):
    """Recheck all observed source bytes/membership after the seed selection.

    This read-only path supports document, release and artifact-only explicit
    scopes. Other selectors require providers for resources/query/configuration.
    No persistent cache is written and no old successful result is substituted.
    """
    if type(descriptor) is not ScopeDescriptor:
        raise ModelError('scope_descriptor_required')
    data = descriptor.data
    if data['scope_kind'] not in ('document', 'release', 'explicit') or data['configuration_id'] is not None:
        raise ModelError('specialized_scope_provider_required')
    if data['scope_kind'] == 'explicit' and data['selector']['resource_ids']:
        raise ModelError('scope_resource_inventory_provider_required')
    snapshot = _capture_sources(source)
    inventory = ScopeSeedInputs(source.configuration, snapshot.records)
    selection = resolve_scope_seeds(descriptor, inventory)
    result = ProjectScopeSeeds(selection, snapshot.binding, len(snapshot.records))
    _check_snapshot_current(source, snapshot)
    return result
