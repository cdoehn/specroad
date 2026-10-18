"""Built-in read projections over the same stored document and graph records.

The supplied snapshot is authoritative for content, not proof of completeness
on disk, current evidence, code availability or release readiness.
"""
from dataclasses import dataclass
from hashlib import sha256

from .._metadata import __version__, MODEL_SCHEMA_VERSION
from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..graph.relation_views import RelationViews
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.domain_schemas import DOMAIN_TYPES
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact
from ..storage.json_syntax import parse_json_object
from .includes import compose_document
from .roles import assess_document_roles


class BuiltinViewError(ModelError):
    def __init__(self, reason, *, path=None, pointer='', exit_code=3):
        super().__init__(reason, path=path, pointer=pointer)
        self.exit_code = exit_code


def _computed_reports():
    """Explicit absence, never a result derived from stored success strings."""
    return {name: {'status': 'unavailable', 'reason': 'provider_required',
                   'required_milestone': milestone, 'result': None}
            for name, milestone in (('verification', 'M12'), ('roadmap', 'M13'))}


class BuiltinViewProviderError(BuiltinViewError):
    """Machine-readable provider refusal without a fabricated result payload."""
    def __init__(self, view_name):
        super().__init__('builtin_view_provider_required', pointer='/view_name')
        self._availability = canonical_json_bytes({
            'view_name': view_name, 'calculation': _computed_reports()[view_name]})

    def diagnostic(self):
        return {**super().diagnostic(), **parse_json_object(self._availability)}


@dataclass(frozen=True, init=False)
class BuiltinViewData:
    """Detached source-bound records, not a stored View or a validation pass."""
    _encoded: bytes
    _sources: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_builtin_view or resolve_type_fallback')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def source_files(self):
        return dict(self._sources)

    def __bool__(self):
        raise TypeError('Built-in projections are not validation or approval')


def _bound_record(document, value):
    return {'artifact_id': value['id'], 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': document.path,
            'source_sha256': sha256(document.content).hexdigest(),
            'record_sha256': canonical_json_sha256(value), 'record': value}


def _result(data, sources):
    result = object.__new__(BuiltinViewData)
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


def _traceability(records, references):
    """Stored edges/subject fields only; no inference from titles or statuses."""
    outgoing = {}
    edges = {}
    pointers = {relation['relation_id']: '/relations/' + str(number)
                for bound in records.values()
                for number, relation in enumerate(bound['record']['relations'])}
    for edge in references.stored_relations:
        source, target = edge.source.id, edge.target.id
        identifier = edge.relation.identity.id
        edges[identifier] = {'source_id': source, 'target_id': target,
            'relation_id': identifier, 'stored_relation': edge.relation.data,
            'relation_sha256': canonical_json_sha256(edge.relation.data),
            'source_binding': {key: records[source][key]
                               for key in ('path', 'source_sha256', 'record_sha256')},
            'pointer': pointers[identifier]}
        outgoing.setdefault(source, []).append((edge.relation.type, target, identifier))

    def follow(seeds, kinds):
        visited = set(seeds); pending = sorted(seeds); selected = set(); used = set()
        while pending:
            current = pending.pop()
            for kind, target, identifier in outgoing.get(current, ()):
                if kind not in kinds:
                    continue
                selected.add(target); used.add(identifier)
                if target not in visited:
                    visited.add(target); pending.append(target)
        return {'artifact_ids': sorted(selected - set(seeds)), 'relation_ids': sorted(used)}

    rows = []
    for identifier in sorted(records):
        if records[identifier]['artifact_type'] != 'requirement':
            continue
        origin = follow([identifier], {'addresses', 'refines', 'derived_from'})
        implementation = follow([identifier], {'allocated_to', 'implemented_by'})
        verification = follow([identifier], {'verified_by'})
        evidence = follow(verification['artifact_ids'], {'produces'})
        # Subject references are original fields, not invented graph relations.
        subject_bindings = []
        for bound in records.values():
            value = bound['record']
            if value['artifact_type'] != 'evidence':
                continue
            for number, subject in enumerate(value['subjects']):
                if subject['artifact_id'] == identifier:
                    evidence['artifact_ids'].append(value['id'])
                    subject_bindings.append({'artifact_id': value['id'],
                        'pointer': '/subjects/' + str(number), 'subject': subject})
        evidence['artifact_ids'] = sorted(set(evidence['artifact_ids']))
        evidence['subject_bindings'] = sorted(subject_bindings,
            key=lambda item: (item['artifact_id'], item['pointer']))
        release = follow([identifier, *implementation['artifact_ids']], {'scheduled_for', 'part_of'})
        # part_of also admits component/capability membership; only actual
        # release/milestone targets constitute a release assignment.
        release['artifact_ids'] = [item for item in release['artifact_ids']
            if records[item]['artifact_type'] in ('release', 'milestone')]
        release['relation_ids'] = [item for item in release['relation_ids']
            if records[edges[item]['target_id']]['artifact_type'] in ('release', 'milestone')]
        rows.append({'requirement_id': identifier, 'origin': origin,
            'implementation': implementation, 'verification': verification,
            'evidence': evidence, 'release': release,
            'verification_result': None, 'release_readiness': None})
    return rows, {key: edges[key] for key in sorted(edges)}


def resolve_builtin_view(model, view_name):
    """Resolve specification composition or stored requirement traceability.

    A full project's specification always requires its unique active primary.
    Missing/invalid primary data never implicitly opts into the fallback API.
    Verification and roadmap providers are deliberately unavailable until their
    actual calculations exist; stored status strings cannot stand in for them.
    """
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    if type(view_name) is not str or view_name not in ('specification', 'traceability', 'verification', 'roadmap'):
        raise BuiltinViewError('builtin_view_not_supported', pointer='/view_name', exit_code=2)
    if view_name in ('verification', 'roadmap'):
        raise BuiltinViewProviderError(view_name)
    model = model.snapshot()
    data = {'view_name': view_name, 'source_kind': 'supplied_project',
        'schema_version': MODEL_SCHEMA_VERSION, 'profiles': list(model.profile.profile_chain),
        'project_id': model.binding.project_id, 'scope_descriptor': _default_scope(),
        'model_root_sha256': model.manifest(model.artifacts, _default_scope()).sha256,
        'input_sha256': model._sources_sha256, 'fallback': False}
    if view_name == 'specification':
        roles = assess_document_roles(model)
        primary = roles.require_primary_document()
        composed = compose_document(model, primary['artifact_id'])
        data.update(mode='primary_document', primary_document=primary,
            roles_sha256=roles.sha256, composition=composed.data,
            composition_sha256=composed.sha256,
            validation_scope='supplied_primary_document_composition')
    else:
        records = _typed_records(model.documents)
        references = RelationViews(RelationReferences(
            [SourceRelations(d.content, path=d.path) for d in model.documents]))
        rows, relations = _traceability(records, references)
        data.update(mode='stored_traceability', records=records, relations=relations,
            rows=rows, row_count=len(rows),
            validation_scope='supplied_record_fields_and_stored_traceability')
    return _result(data, model.source_files)


def render_builtin_view(model, view_name, *, output_format='markdown'):
    """Return bytes through the existing safe document/table renderers."""
    from .rendering import _snapshot, render_document
    from ._render_formats import Emitter
    from .requirement_presentation import resolve_requirement_presentation
    from ..model.content_language import ContentLanguage
    model = _snapshot(model, output_format)
    resolved = resolve_builtin_view(model, view_name)
    data = resolved.data
    if view_name == 'specification':
        return render_document(model, data['primary_document']['artifact_id'], output_format=output_format)
    categories = ('origin', 'implementation', 'verification', 'evidence', 'release')
    nodes = []
    for row in data['rows']:
        identifier = row['requirement_id']; value = data['records'][identifier]['record']
        nodes.append({'type': 'record', 'record': value, 'mode': 'full', 'level': 2,
            'content_language': ContentLanguage(value.get('language'), value.get('text_direction', 'auto')).as_dict(),
            'presentation': resolve_requirement_presentation(model, identifier).data})
        nodes.append({'type': 'table', 'id': identifier, 'data': {
            'columns': [{'heading': name} for name in categories],
            'rows': [{'cells': [{'type': 'array', 'value': row[name]['artifact_ids']} for name in categories]}]}})
    metadata = {key: data[key] for key in ('tool_version', 'schema_version', 'profiles',
        'project_id', 'model_root_sha256', 'input_sha256', 'verification_evaluated',
        'release_readiness_evaluated', 'computed_reports')}
    metadata['projection_sha256'] = resolved.sha256
    return Emitter(output_format).output(metadata, view_name, nodes)
