"""Show only verified closure members and their explicitly bounded relations."""
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, ResultStatus
from ..graph._boundary_contract import require_boundary_match
from ..graph.relation_views import RelationView
from ..model.errors import ModelError
from ._show_projection import show_payload


def partial_show_steps(snapshot, artifact_id, *, index, strategy, details):
    from ..storage.relation_index import ProjectRelationIndex
    from ..graph.indices import RelationIndex
    if type(strategy) is not str or strategy not in ('indexed', 'scan'):
        raise ModelError('invalid_relation_index_strategy')
    if index is not None and type(index) not in (ProjectRelationIndex, RelationIndex):
        raise ModelError('invalid_relation_index_hint')
    records = {r.identity.id: r for r in snapshot.records}
    if type(artifact_id) is not str or artifact_id not in records:
        raise ModelError('unknown_relation_view_artifact')
    # Local edges and boundary endpoints share the canonical view projection.
    # A boundary identity is not a loaded target artifact or an incoming source.
    edges = list(snapshot.references.local_relations)
    relations = {r.identity.id: r for record in snapshot.records for r in record.relations}
    for boundary in snapshot.references.boundary_references:
        edges.append(require_boundary_match(boundary.data, relations[boundary.data['relation_id']]))
    views = []
    for edge in edges:
        view = RelationView(edge)  # Also reject noncanonical stored orientation.
        if edge.source.id == artifact_id:
            views.append(view)
        if edge.target.id == artifact_id:
            views.append(RelationView(edge, inverse=True))
    views.sort(key=lambda v: (v.type, v.target.id, v.relation_id, v.inverse))
    yield 'loaded'
    from types import SimpleNamespace
    payload = show_payload(SimpleNamespace(artifact=records[artifact_id], views=views,
        coverage_scope='partial_bundle_artifacts', source_count=len(records), relation_count=len(edges),
        binding=SimpleNamespace(sha256=snapshot.observation_sha256),
        validation_scope='partial_payload_model', atomic_snapshot=False))
    manifest = snapshot.manifest
    details.update(bundle_kind='partial', read_only=True, project_complete=False,
        scope_descriptor=manifest['scope_descriptor'], boundary_references=manifest['boundary_references'],
        bundle_model_root_sha256=manifest['bundle_model_root_sha256'],
        origin_model_root_sha256=manifest['origin_model_root_sha256'], origin_root_verified=False)
    yield 'evaluated'
    snapshot.verify_current()
    validate_result_document('artifact-show-v1', payload)
    return CommandResult('artifact.show', status=ResultStatus.PARTIAL, partial_scope='partial_bundle_artifacts',
        result=payload, project={'project_root': str(snapshot.boundary.root),
                                'project_id': snapshot.configuration.project_id}, details=details)
