"""Pure Show data projection from an already checked project observation.

No discovery, file access, preflight or rendering. The query orchestrator keeps
the complete source/freshness checks and the result envelope/error contract.
"""


def show_payload(observed):
    incoming, outgoing = [], []
    for view in observed.views:
        row = {'relation_id': view.relation_id, 'type': view.type,
               'source': view.source.id, 'target': view.target.id, 'inverse': view.inverse,
               'stored_source': view.stored.source.id, 'stored_relation': view.stored.relation.data}
        (incoming if view.inverse else outgoing).append(row)
    payload = {'format_version': '1.0.0', 'artifact': observed.artifact.data,
        'incoming': incoming, 'outgoing': outgoing,
        'coverage': {'scope': observed.coverage_scope, 'source_count': observed.source_count,
            'relation_count': observed.relation_count, 'observation_sha256': observed.binding.sha256,
            'validation_scope': observed.validation_scope, 'atomic_snapshot': observed.atomic_snapshot}}
    return payload
