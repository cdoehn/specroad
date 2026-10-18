"""Bound diagram projections and source bytes over an owned native graph.

No project discovery, file publication, renderer, browser or template execution.
Labels are either validated identities or escaped text from original titles.
The machine-readable projection always retains the original title bytes' value.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ._diagram_graph import diagram_graph_data
from ._diagram_sources import diagram_source_bytes


class DiagramError(ModelError):
    def __init__(self, reason, *, path=None, pointer='', exit_code=3):
        super().__init__(reason, path=path, pointer=pointer)
        self.exit_code = exit_code


@dataclass(frozen=True, init=False)
class DiagramData:
    """Detached selected identities and original source bindings, not approval."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_diagram with an owned TargetModel')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Diagram data is not project or release approval')


def resolve_diagram(model, diagram_kind, *, start_id, direction, max_depth,
                    max_nodes, max_edges, artifact_ids=None, relation_types=None):
    """Project traversed stored edges within an explicitly bounded native scope.

    Trace admits the supplied project graph. Architecture admits components and
    interfaces only. Release admits the native release seed set. Nodes at the
    requested depth are included without expansion. Count overflow is an error,
    never truncation. Traversal direction does not reverse normative edges.
    Optional artifact IDs narrow the family scope; stored relation types filter
    traversal in either direction. Neither option bypasses full graph validation.
    """
    data = diagram_graph_data(model, diagram_kind, start_id=start_id, direction=direction,
        max_depth=max_depth, max_nodes=max_nodes, max_edges=max_edges,
        artifact_ids=artifact_ids, relation_types=relation_types, error_type=DiagramError)
    result = object.__new__(DiagramData)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result


def render_diagram(model, diagram_kind, *, start_id, direction, max_depth,
                   max_nodes, max_edges, output_format='mermaid', label_mode='id',
                   artifact_ids=None, relation_types=None):
    """Return deterministic UTF-8 source; never invoke a graphical renderer.

    Identity labels retain the original ids-v1 profiles. Title labels use the
    text-v1 profiles: quoted text, no HTML, markdown or executable directives.
    """
    if type(output_format) is not str or output_format not in ('mermaid', 'dot'):
        raise DiagramError('diagram_format_not_supported', pointer='/output_format', exit_code=2)
    if type(label_mode) is not str or label_mode not in ('id', 'title'):
        raise DiagramError('diagram_label_mode_not_supported', pointer='/label_mode', exit_code=2)
    resolved = resolve_diagram(model, diagram_kind, start_id=start_id, direction=direction,
        max_depth=max_depth, max_nodes=max_nodes, max_edges=max_edges,
        artifact_ids=artifact_ids, relation_types=relation_types)
    return diagram_source_bytes(resolved, output_format=output_format, label_mode=label_mode)
