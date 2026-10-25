"""Native read consumers over a verified, explicitly bounded observation."""
from ..model.errors import ModelError
from ..bundles._partial_graph import PartialGraph
from ..bundles._read_context import PartialReadContext


def query_steps(snapshot, query, *, options, cwd, configuration_id, details):
    context = PartialReadContext(snapshot)
    from .project_query import _normalized
    from .paging import query_records
    bindings = []
    if query is None:
        query, bindings = _normalized(snapshot, {} if options is None else options, cwd)
    yield 'loaded'
    page = query_records(snapshot.records, query, project=snapshot.configuration.data,
                         configuration_id=configuration_id, partial=snapshot)
    details.update(query_sha256=page.query_sha256, inputs_sha256=page.inputs_sha256,
        source_count=len(snapshot.records), observation_sha256=snapshot.observation_sha256,
        validation_scope='partial_payload_model', profile_defaults_applied=False)
    if page.configuration_binding is not None:
        details['selected_configuration'] = page.configuration_binding
        details['configuration_scope_sha256'] = snapshot.configuration_selection(
            configuration_id).scope_sha256(snapshot.configuration)
    yield 'evaluated'
    snapshot.verify_current()
    for boundary, name, raw in bindings:
        if boundary.read_bytes(name) != raw:
            raise ModelError('query_input_changed', path=name)
    return context.finish('query', 'artifact-query-v1', page.data, details)


def trace_steps(snapshot, artifact_id, *, direction, depth, currentness, configuration_id, details):
    context = PartialReadContext(snapshot)
    from .trace import _trace_rows
    graph = PartialGraph(snapshot)
    yield 'loaded'
    nodes, edges = _trace_rows(graph.local, artifact_id, direction, depth)
    payload = dict(format_version='1.0.0', start=artifact_id, direction=direction,
                   depth=depth, nodes=nodes, edges=edges, coverage=context.coverage())
    if currentness is not None:
        from ..verification.currentness_input import checked_currentness_records
        payload['currentness'] = checked_currentness_records(currentness, snapshot.records,
            snapshot.configuration, configuration_id)
    yield 'evaluated'
    return context.finish('trace', 'artifact-trace-v1', payload, details)


def why_steps(snapshot, artifact_id, *, details):
    context = PartialReadContext(snapshot)
    from .why import _why_paths
    limits = snapshot.configuration.data.get('resource_limits', {})
    if 'trace_depth' not in limits:
        raise ModelError('why_depth_not_configured', path='specroad.json', pointer='/resource_limits/trace_depth')
    graph = PartialGraph(snapshot)
    yield 'loaded'
    targets, paths = _why_paths(graph.local, artifact_id, limits['trace_depth'])
    payload = dict(format_version='1.0.0', start=artifact_id, depth=limits['trace_depth'],
        traversal='stored_direction_with_symmetric_inverses', targets=targets, paths=paths,
        path_count=len(paths), coverage=context.coverage())
    yield 'evaluated'
    return context.finish('why', 'artifact-why-v1', payload, details)


def impact_steps(snapshot, artifact_id, *, currentness, configuration_id, details):
    context = PartialReadContext(snapshot)
    from ..graph._impact_projection import _impact_rows, _artifact_observations
    yield 'loaded'
    groups, reviews, findings = _impact_rows(snapshot.records, artifact_id, partial=snapshot)
    payload = dict(format_version='1.1.0', artifact_id=artifact_id, depth=1, transitive=False,
        groups=groups, review_groups=reviews,
        artifact_observations=_artifact_observations(snapshot.records, artifact_id, groups),
        coverage=context.coverage(review_record_count=sum(
            r.identity.artifact_type == 'relation_review' for r in snapshot.records)))
    if currentness is not None:
        from ..verification.currentness_input import checked_currentness_records
        payload['currentness'] = checked_currentness_records(currentness, snapshot.records,
            snapshot.configuration, configuration_id)
    yield 'evaluated'
    return context.finish('impact', 'artifact-impact-v1', payload, details, findings)
