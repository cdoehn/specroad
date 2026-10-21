"""Private projections over the common authoring model and validated graph.

These helpers do not publish, authorize or repair project data. The public
provider keeps the shared graph validators ahead of every link projection.
"""
from hashlib import sha256

from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact


def _planning_sources(documents):
    """Read stored fields with the shared schemas and retain exact byte bindings."""
    records, values, bindings = [], {}, {}
    kinds = {'release', 'milestone', 'task', 'capability', 'requirement', 'decision'}
    for document in sorted(documents, key=lambda item: item.path):
        source = SourceRelations(document.content, path=document.path)
        records.append(source)
        if source.identity.artifact_type not in kinds:
            continue
        value = DomainArtifact(document.content, path=document.path).data
        values[value['id']] = value
        bindings[value['id']] = {'artifact_id': value['id'], 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': document.path,
            'source_sha256': sha256(document.content).hexdigest(),
            'record_sha256': canonical_json_sha256(value)}
    return records, values, bindings


def _planning_links(references, values, bindings):
    """Project already validated edges; this filter is not a second relation matrix."""
    links = []
    for edge in references.relations:
        kind, source, target = edge.relation.type, edge.source, edge.target
        if not (kind == 'scheduled_for' or
                (kind == 'part_of' and source.artifact_type in ('milestone', 'task')) or
                (kind == 'implemented_by' and target.artifact_type == 'task')):
            continue
        position = next(i for i, relation in enumerate(values[source.id]['relations'])
                        if relation['relation_id'] == edge.relation.identity.id)
        links.append({'relation_id': edge.relation.identity.id, 'type': kind,
            'source_id': source.id, 'source_type': source.artifact_type,
            'target_id': target.id, 'target_type': target.artifact_type,
            'path': bindings[source.id]['path'], 'pointer': '/relations/' + str(position),
            'source_sha256': bindings[source.id]['source_sha256'],
            'relation_sha256': canonical_json_sha256(edge.relation.data)})
    links.sort(key=lambda row: (row['source_id'], row['type'], row['target_id'], row['relation_id']))
    return links


def _planning_artifacts(values, bindings, links):
    """Retain stored facts and the existing missing-Task-link contract."""
    releases, milestones, tasks, missing = [], [], [], []
    for identifier, value in sorted(values.items()):
        bound = bindings[identifier]
        kind = value['artifact_type']
        if kind == 'release':
            releases.append({**bound, **{key: value[key] for key in
                ('name', 'objective', 'maturity', 'readiness_policy')},
                **({'target_date': value['target_date']} if 'target_date' in value else {})})
        elif kind == 'milestone':
            parent, = [row for row in links if row['source_id'] == identifier and row['type'] == 'part_of']
            milestones.append({**bound, **{key: value[key] for key in ('objective', 'owner', 'maturity')},
                'release_id': parent['target_id'], 'release_relation_id': parent['relation_id'],
                **({'done_criteria': value['done_criteria']} if 'done_criteria' in value else {})})
        elif kind == 'task':
            implemented = [row for row in links if row['target_id'] == identifier and
                           row['type'] == 'implemented_by']
            subject_links = [row for row in implemented if row['source_type'] in ('requirement', 'decision')]
            if not subject_links:
                missing.append(identifier)
                if value['maturity'] == 'approved':
                    raise ModelError('planning_task_implementation_required', path=bound['path'], pointer='/relations')
            tasks.append({**bound, **{key: value[key] for key in ('description', 'owner', 'maturity',
                'implementation_status', 'verification_plan_status', 'done_criteria')},
                'implemented_subject_ids': sorted({row['source_id'] for row in implemented}),
                'implementation_relation_ids': sorted(row['relation_id'] for row in implemented)})
    return releases, milestones, tasks, missing
