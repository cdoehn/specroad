"""Explicit guarded migration intentions for the ordinary Change Plan writer.

Reading never calls these helpers. They choose no status, invent no review and
publish no files. Pass the returned operation to the existing update writer,
with its normal authority, lifecycle checks, target validation and transaction.
"""
from ..changes.update_inputs import normalize_artifact_update_input
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact
from ._readiness_policy import readiness_policy


def _operation(value, field, selected):
    return normalize_artifact_update_input(value,
        patch=[{'op': 'replace', 'path': '/' + field, 'value': selected}],
        expected_revision=value['revision'], expected_sha256=canonical_json_sha256(value))


def prepare_readiness_policy_update(release, policy):
    if type(release) is not DomainArtifact:
        raise ModelError('typed_release_required')
    value = DomainArtifact(release.source_bytes, expected_type='release').data
    selected, reason = readiness_policy(policy)
    if reason is not None:
        raise ModelError('versioned_readiness_policy_required')
    return _operation(value, 'readiness_policy', selected)


def prepare_readiness_status_update(subject, status):
    if type(subject) not in (DomainArtifact, RecordArtifact):
        raise ModelError('typed_release_blocker_subject_required')
    value = type(subject)(subject.source_bytes).data
    kind = value['artifact_type']
    choices = {'risk': ('open', 'in_progress', 'mitigated', 'closed', 'accepted'),
               'issue': ('open', 'in_progress', 'resolved', 'closed')}
    if kind not in choices or type(status) is not str or status not in choices[kind]:
        raise ModelError('release_blocker_status_required')
    type(subject)(canonical_json_bytes({**value, kind + '_status': status}))
    return _operation(value, kind + '_status', status)
