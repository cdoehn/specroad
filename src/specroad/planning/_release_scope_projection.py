"""Project native Release closure members and their stored dependency edges."""
from hashlib import sha256

from ..configurations import evaluate_applicability
from ..model.canonical import canonical_json_sha256
from ..model.domain_schemas import DOMAIN_TYPES
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact


def release_members(records, artifact_ids, configuration):
    """Validate reached members and retain source bindings and applicability."""
    included = set(artifact_ids)
    applicability = []
    values, bindings = {}, {}
    for record in records:
        if record.identity.id not in included:
            continue
        artifact = DomainArtifact if record.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
        value = artifact(record.source_bytes, path=record.path).data
        applicability.append(evaluate_applicability(record, configuration).data)
        key = value['id']
        values[key] = value
        bindings[key] = {'artifact_id': key, 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': record.path,
            'source_sha256': sha256(record.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(value)}
    return values, bindings, applicability


def release_dependencies(values, bindings, artifact_ids, seeds):
    """Describe stored edges; external membership is relative to Release seeds."""
    required = []
    for key in artifact_ids:
        for position, relation in enumerate(values[key]['relations']):
            if relation['type'] != 'depends_on':
                continue
            target = relation['target']
            required.append({'relation_id': relation['relation_id'], 'type': 'depends_on',
                'source_id': key, 'target_id': target,
                'path': bindings[key]['path'], 'pointer': '/relations/' + str(position),
                'source_sha256': bindings[key]['source_sha256'],
                'relation_sha256': canonical_json_sha256(relation),
                'target_record_sha256': bindings[target]['record_sha256'],
                'source_is_release_seed': key in seeds, 'target_is_release_seed': target in seeds,
                'external': target not in seeds})
    required.sort(key=lambda row: (row['source_id'], row['target_id'], row['relation_id']))
    return required
