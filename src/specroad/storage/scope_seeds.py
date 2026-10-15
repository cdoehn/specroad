"""Fresh current-project inputs for artifact-only seed selectors.

Artifact and query selectors read complete current membership, then apply the
explicit configuration before pagination. Full-resource scopes and closure
still require their separate inventory providers.
"""
from dataclasses import dataclass

from ..graph.scope_descriptors import ScopeDescriptor
from ..graph.scope_inputs import ScopeSeedInputs
from ..graph.scope_query_page import QuerySeedPage
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

    This path supports document, release, query and artifact-only explicit
    scopes, including their configuration wrappers. Full resource inventories
    remain separate providers.
    No persistent cache is written and no old successful result is substituted.
    """
    if type(descriptor) is not ScopeDescriptor:
        raise ModelError('scope_descriptor_required')
    data = descriptor.data
    base = data['selector']['base_scope_descriptor'] if data['scope_kind'] == 'configuration' else data
    if base['scope_kind'] not in ('document', 'release', 'explicit', 'query'):
        raise ModelError('specialized_scope_provider_required')
    if base['scope_kind'] == 'explicit' and base['selector']['resource_ids']:
        raise ModelError('scope_resource_inventory_provider_required')
    snapshot = _capture_sources(source)
    inventory = ScopeSeedInputs(source.configuration, snapshot.records)
    page = None
    if base['scope_kind'] == 'query':
        from ..query.selection import NormalizedQuery
        from ..query.paging import query_records
        result = query_records(snapshot.records, NormalizedQuery.from_data(base['selector']['query']),
            project=source.configuration.data, configuration_id=data['configuration_id'])
        page = QuerySeedPage(descriptor, inventory, [item['id'] for item in result.data['items']],
                             total=result.data['total'])
    selection = resolve_scope_seeds(descriptor, inventory, query_page=page)
    result = ProjectScopeSeeds(selection, snapshot.binding, len(snapshot.records))
    _check_snapshot_current(source, snapshot)
    return result
