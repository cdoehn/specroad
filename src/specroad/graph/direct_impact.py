"""One-hop relation analysis, independent of later query/CLI/report adapters."""
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from .comparison_values import ComparisonResult
from .references import RelationReferences
from .indices import RelationIndex


def direct_impact(artifact_id, references):
    """All directly connected artifacts, both directions, grouped by stored type."""
    if type(references) is not RelationReferences:
        raise ModelError('resolved_relations_required')
    index = RelationIndex(references)
    views = index.for_artifact(artifact_id, direction='both')
    groups = {}
    for view in views:
        edge = view.stored
        kind = edge.relation.type
        entry = {'relation_id': edge.relation.identity.id,
            'related_id': view.target.id, 'direction': 'incoming' if view.inverse else 'outgoing'}
        groups.setdefault(kind, []).append(entry)
    result = []
    for kind in sorted(groups):
        connections = sorted(groups[kind], key=lambda c: (c['related_id'], c['direction'], c['relation_id']))
        result.append({'relation_type': kind,
            'artifact_ids': sorted({c['related_id'] for c in connections}), 'connections': connections})
    return ComparisonResult({'impact_version': 'direct-impact-v1', 'artifact_id': artifact_id,
        'groups': result, 'depth': 1, 'transitive': False,
        'input_relations_sha256': canonical_json_sha256({
            'sources': [source.id for source in references.sources],
            'relations': [{'source_id': edge.source.id, 'value': edge.relation.data}
                          for edge in references.relations]}),
        'validation_scope': 'supplied_relation_set_only', 'write_authorized': False})


