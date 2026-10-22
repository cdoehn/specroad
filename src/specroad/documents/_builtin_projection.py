"""Shared source binding and passive result construction for built-in views.

View adapters own scope admission and domain calculations. This boundary only
binds their data and original source bytes; it performs no discovery or IO.
The caller supplies the existing public result class so its identity stays
independent of this private implementation module.
"""
from hashlib import sha256

from .._metadata import __version__
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_schemas import DOMAIN_TYPES
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact


def _computed_reports(*, verification=None, roadmap=None):
    """Project checked coverage or explicit absence; stored statuses do not count."""
    reports = {name: {'status': 'unavailable', 'reason': 'provider_required',
                   'required_milestone': milestone, 'result': None}
            for name, milestone in (('verification', 'M12'), ('roadmap', 'M13'))}
    if verification is not None:
        reports['verification'] = {'status': 'computed', 'reason': None,
                                   'required_milestone': 'M12', 'result': verification}
    if roadmap is not None:
        reports['roadmap'] = {'status': 'computed', 'reason': None,
                             'required_milestone': 'M13', 'result': roadmap}
    return reports


def _bound_record(document, value):
    return {'artifact_id': value['id'], 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': document.path,
            'source_sha256': sha256(document.content).hexdigest(),
            'record_sha256': canonical_json_sha256(value), 'record': value}


def _project(result_type, data, sources):
    result = object.__new__(result_type)
    object.__setattr__(result, '_encoded', canonical_json_bytes({
        'format_version': 1, 'kind': 'builtin-view-data-v1', 'tool_version': __version__,
        'generated': True, 'normative': False, 'project_files_verified': False,
        'full_validation_passed': False, 'rendering_performed': False,
        'write_authorized': False, 'approval_granted': False,
        'verification_evaluated': False, 'release_readiness_evaluated': False,
        'computed_reports': _computed_reports(), **data}))
    object.__setattr__(result, '_sources', tuple(sorted(sources.items())))
    return result


def _typed_records(documents):
    records = {}
    for document in documents:
        source = SourceRelations(document.content, path=document.path)
        reader = DomainArtifact if source.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
        value = reader(document.content, path=document.path).data
        records[value['id']] = _bound_record(document, value)
    return records
