"""Native scope/configuration/query binding for a supplied view snapshot."""
from ..graph.scope_descriptors import ScopeDescriptor
from ..query import NormalizedQuery, query_records
from ..srx import LoadedGraph


def select_view(records, project, index, descriptor, query, configuration_id, fail):
    selected_scope = descriptor.data
    if configuration_id is not None:
        if selected_scope['configuration_id'] not in (None, configuration_id):
            fail('view_configuration_conflict', '/scope_descriptor/configuration_id')
        selected_scope['configuration_id'] = configuration_id
    selected_scope = ScopeDescriptor(selected_scope)
    selected_id = selected_scope.data['configuration_id']
    if selected_id is not None and selected_id not in index:
        fail('view_configuration_provider_required', '/scope_descriptor/configuration_id')
    page = query_records(records, query, project=project, configuration_id=selected_id)
    eligible_ids = None
    if selected_id is not None:
        # Resolve the same native configuration over all snapshot records.
        # The row filter must not discard applicable intermediate graph nodes.
        eligible = query_records(records, NormalizedQuery(limit=len(records)),
            project=project, configuration_id=selected_id)
        eligible_ids = [item['id'] for item in eligible.data['items']]
    graph = LoadedGraph(records, rule_id='document-view', artifact_ids=eligible_ids)

    return selected_scope, page, graph
