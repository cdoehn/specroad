"""Exact waiver-content-hash-v1 projection, separate from full artifact hashes."""
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.waiver_fields import CONTENT_HASH_ALGORITHM
from ..storage.domain_artifact import DomainArtifact

COMMON_FIELDS = ('schema_version', 'id', 'id_scheme', 'artifact_type', 'title',
    'language', 'text_direction', 'owner', 'tags', 'applicability', 'relations',
    'extensions', 'provenance', 'external_identities', 'display_id')
TYPE_FIELDS = {
    'capability': ('description', 'outcome', 'priority'),
    'requirement': ('requirement_kind', 'normative_force', 'statement', 'priority',
        'criticality', 'rationale', 'deviation_conditions', 'deviation_authority',
        'scope', 'actor', 'trigger', 'preconditions', 'response', 'object', 'timing',
        'thresholds', 'exceptions'),
    'task': ('description', 'done_criteria'),
}
EXCLUDED_FIELDS = ('verification_waiver', 'maturity', 'implementation_status',
    'verification_plan_status', 'revision', 'created_at', 'created_by', 'updated_at', 'updated_by')
PROVENANCE_FIELDS = ('source_id', 'locator', 'excerpt', 'content_sha256', 'extensions')


def waiver_subject(subject):
    if type(subject) is not DomainArtifact:
        raise ModelError('typed_waiver_subject_required')
    owned = DomainArtifact(subject.source_bytes, path=subject.path)
    data = owned.data
    if owned.artifact_type not in TYPE_FIELDS:
        raise ModelError('waiver_subject_type_unsupported', path=subject.path)
    fields = (*COMMON_FIELDS, *TYPE_FIELDS[owned.artifact_type])
    if set(data) - set(fields) - set(EXCLUDED_FIELDS):
        raise ModelError('waiver_content_fields_unsupported', path=subject.path)
    return owned


def waiver_content_projection(subject):
    value = waiver_subject(subject).data
    fields = (*COMMON_FIELDS, *TYPE_FIELDS[value['artifact_type']])
    projected = {key: value[key] for key in fields if key in value}
    if 'provenance' in value:
        projected['provenance'] = [{key: item[key] for key in PROVENANCE_FIELDS if key in item}
                                   for item in value['provenance']]
    return {'hash_algorithm': CONTENT_HASH_ALGORITHM, 'artifact': projected}


def waiver_content_sha256(subject):
    return canonical_json_sha256(waiver_content_projection(subject))
