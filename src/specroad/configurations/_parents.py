"""Resolve the selected parent component with the shared graph cycle primitive."""
from ..graph._graph_traversal import _cycle_witness
from ..model.errors import ModelError


def resolve_parent_chain(configurations, selected):
    chain, edges, visited = [], [], set()
    current = selected
    # Collect each reachable record once, including a closing edge. Unselected
    # components are outside this API's declared resolution scope.
    while current is not None and current.id not in visited:
        visited.add(current.id)
        chain.append(current)
        parent_id = current.data.get('parent')
        if parent_id is None:
            current = None
            break
        if parent_id not in configurations:
            raise ModelError('configuration_parent_missing', path=current.path, pointer='/parent')
        parent = configurations[parent_id]
        if parent.id.split('-', 1)[0] != current.id.split('-', 1)[0]:
            raise ModelError('configuration_parent_project_mismatch', path=current.path, pointer='/parent')
        edges.append((current, parent))
        current = parent
    cycle = _cycle_witness(edges, source_id=lambda edge: edge[0].id,
                           target_id=lambda edge: edge[1].id,
                           edge_id=lambda edge: edge[0].id)
    if cycle is not None:
        # Keep the public diagnostic at the first repeated ancestor reached
        # from the selected configuration, independent of witness rotation.
        raise ModelError('configuration_parent_cycle', path=current.path, pointer='/parent')
    chain.reverse()
    return chain
