"""Pure direct grouping and owned review/fact projections for graph consumers."""
from ..model.errors import ModelError
from .review_status import RelationReviewStatuses


def _group_connections(groups):
    rows = []
    for kind in sorted(groups):
        connections = sorted(groups[kind], key=lambda c: (c['related_id'], c['direction'], c['relation_id']))
        rows.append({'relation_type': kind, 'artifact_ids': sorted({c['related_id'] for c in connections}),
                     'connections': connections})
    return rows


def _impact_rows(records, artifact_id):
    statuses = RelationReviewStatuses(records)
    identities = {record.identity.id for record in records}
    if type(artifact_id) is not str or artifact_id not in identities:
        raise ModelError('unknown_impact_artifact')
    observed = {value.relation_id: value for value in statuses.statuses}
    groups, selected = {}, {}
    for source in records:
        for relation in source.relations:
            status = observed[relation.identity.id]
            for direction, start, related in (
                ('outgoing', source.identity.id, relation.target),
                ('incoming', relation.target, source.identity.id),
            ):
                if start != artifact_id:
                    continue
                selected[status.relation_id] = status
                connection = {'relation_id': status.relation_id,
                    'source_id': status.source_id, 'target_id': status.target_id,
                    'related_id': related, 'direction': direction, 'related_present': related in identities,
                    'review_status': status.status, 'review_reason': status.reason,
                    'selected_review_id': status.selected_review_id,
                    'matching_review_ids': list(status.matching_review_ids),
                    'historical_review_ids': list(status.historical_review_ids)}
                groups.setdefault(relation.type, []).append(connection)
    rows = _group_connections(groups)
    review_groups = {}
    for state in ('unreviewed', 'current', 'suspect', 'invalid'):
        values = [value for value in selected.values() if value.status == state]
        review_groups[state] = {'relation_ids': sorted(value.relation_id for value in values),
                               'affected_ids': sorted({name for value in values
                                                       for name in (value.source_id, value.target_id)})}
    findings = tuple(finding for finding in statuses.diagnostics
                     if any(name in selected for name in finding.related_ids))
    return rows, review_groups, findings


def _artifact_observations(records, artifact_id, groups):
    """Project only declared facts; missing fields never become assessments."""
    values = {record.identity.id: record.data for record in records}
    names = {artifact_id} | {name for group in groups for name in group['artifact_ids']}
    observations = []
    for name in sorted(names):
        value = values.get(name)
        fields = {}
        for field in ('priority', 'verification_plan_status'):
            if value is None:
                fields[field] = {'state': 'unavailable'}
            elif field not in value:
                fields[field] = {'state': 'missing'}
            else:
                fields[field] = {'state': 'present', 'value': value[field]}
        observations.append({'artifact_id': name, 'present': value is not None,
            'artifact_type': None if value is None else value['artifact_type'],
            'fields': fields, 'verification_assessment': {'state': 'not_performed'}})
    return observations
