"""Complete selected values, using native scope and fresh read observations."""
from ..bundles._partial_read import partial_read_snapshot
from ..changes._patch_pointer import _pointer
from ..model.errors import ModelError
from ..query.selection import NormalizedQuery, select_query
from ..query.show import _preflight, _verify_current
from ..srx import MISSING
from ..srx.pointers import resolve_tokens
from ..storage.project import ProjectSource
from ..storage._relation_snapshot import _capture_sources
from ._request_values import SUBJECT_BINDING
from ._values import AnalyzerError, decode, digest, encoded, require
from .identities import prepare_analysis_id
from .requests import create_request


def _observe(root):
    partial = partial_read_snapshot(root)
    if partial is not None:
        return partial, partial, partial.records
    source = ProjectSource(root)
    _preflight(source)
    snapshot = _capture_sources(source)
    return source, snapshot, snapshot.records


def _finish(source, snapshot):
    if source is snapshot:
        source.verify_current()
    else:
        _preflight(source)
        _verify_current(source, snapshot.binding)


def _selected(source, snapshot, records, subject_ids, configuration_id):
    selected = select_query(records, NormalizedQuery(
        filters={'type':['requirement']} if subject_ids is None else {}),
        project=source.configuration.data, configuration_id=configuration_id,
        partial=source if source is snapshot else None)
    wanted = set(selected.artifact_ids) if subject_ids is None else set(subject_ids)
    require(wanted <= set(selected.artifact_ids), 'analyzer_subject_outside_scope')
    require(bool(wanted), 'analyzer_empty_selection')
    return sorted((r for r in records if r.identity.id in wanted), key=lambda r:r.identity.id)


def _read_subjects(root, subject_ids, pointers, configuration_id):
    source, snapshot, records = _observe(root)
    subjects = []
    for record in _selected(source, snapshot, records, subject_ids, configuration_id):
        artifact = record.data
        for pointer, tokens in pointers:
            value = resolve_tokens(artifact, tokens, rule_id='analyzer-subject', at=pointer)
            require(value is not MISSING, 'analyzer_subject_pointer_missing', pointer)
            subject = dict(artifact_id=artifact['id'], artifact_revision=artifact['revision'],
                artifact_sha256=digest(artifact), field_pointer=pointer, value=value,
                value_sha256=digest(value), declared_language=artifact.get('language'))
            subject['subject_key'] = digest({k:subject[k] for k in SUBJECT_BINDING})
            if 'normative_force' in artifact:
                subject['normative_force'] = artifact['normative_force']
            subjects.append(subject)
    _finish(source, snapshot)
    return subjects


def request_from_project(root, *, analyzers, settings, subject_ids=None,
                         field_pointers=('/statement',), configuration_id=None,
                         context=(), extensions=None, analysis_id=None):
    """Select full values, never a page/sample. Context is supplied JSON, not paths.

    Default membership is every requirement in the native selected scope. A
    verified partial remains bounded by its manifest; it is not a whole project.
    This reader grants no worker execution, write, evidence or approval rights.
    """
    identity = prepare_analysis_id(analysis_id)
    require(type(field_pointers) in (list, tuple) and bool(field_pointers),
            'analyzer_pointer_selection_required', exit_code=2)
    require(all(type(p) is str for p in field_pointers), 'analyzer_invalid_pointer', exit_code=2)
    require(len(set(field_pointers)) == len(field_pointers), 'analyzer_duplicate_pointer', exit_code=2)
    try:
        pointers = [(p, _pointer(p, '/field_pointers')) for p in sorted(field_pointers)]
    except ModelError as error:
        raise AnalyzerError(error.reason, pointer=error.pointer, exit_code=2) from error
    if subject_ids is not None:
        require(type(subject_ids) in (list, tuple) and bool(subject_ids)
                and all(type(i) is str for i in subject_ids), 'analyzer_invalid_selection', exit_code=2)
        require(len(set(subject_ids)) == len(subject_ids), 'analyzer_duplicate_selection', exit_code=2)
        subject_ids = tuple(subject_ids)
    subjects = _read_subjects(root, subject_ids, pointers, configuration_id)
    # Own caller data before hashing or returning any nested value.
    supplied = decode(encoded(dict(analyzers=analyzers, settings=settings,
        resources=list(context), extensions={} if extensions is None else extensions)))
    return create_request(analyzers=supplied['analyzers'], subjects=subjects,
        context=dict(resources=supplied['resources'], subject_keys=sorted(s['subject_key'] for s in subjects)),
        settings=supplied['settings'], extensions=supplied['extensions'], analysis_id=identity)
