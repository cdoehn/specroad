"""Built-in read projections over the same stored document and graph records.

The supplied snapshot is authoritative for content, not proof of completeness
on disk, current evidence, code availability or release readiness.
"""
from dataclasses import dataclass
from hashlib import sha256

from .._metadata import MODEL_SCHEMA_VERSION
from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..graph.relation_views import RelationViews
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ._builtin_projection import _bound_record, _computed_reports, _project, _typed_records
from .includes import compose_document
from .roles import assess_document_roles


class BuiltinViewError(ModelError):
    def __init__(self, reason, *, path=None, pointer='', exit_code=3):
        super().__init__(reason, path=path, pointer=pointer)
        self.exit_code = exit_code


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


def _result(data, sources):
    return _project(BuiltinViewData, data, sources)


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


def resolve_builtin_view(model, view_name, *, verification=None, currentness=None):
    """Resolve specification, stored traceability or explicitly bound coverage.

    A full project's specification always requires its unique active primary.
    Missing/invalid primary data never implicitly opts into the fallback API.
    Verification requires a computed input for the exact supplied snapshot.
    Roadmap remains unavailable; stored statuses cannot stand in for results.
    """
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    if type(view_name) is not str or view_name not in ('specification', 'traceability', 'verification', 'roadmap'):
        raise BuiltinViewError('builtin_view_not_supported', pointer='/view_name', exit_code=2)
    if view_name == 'roadmap' or (view_name == 'verification' and verification is None and currentness is None):
        raise BuiltinViewProviderError(view_name)
    if verification is not None and view_name != 'verification':
        raise BuiltinViewError('builtin_verification_input_not_applicable', pointer='/view_name')
    observed = None
    if currentness is not None:
        from ..verification.currentness_input import checked_currentness_model
        if view_name not in ('traceability', 'verification'):
            raise BuiltinViewError('builtin_currentness_input_not_applicable', pointer='/view_name')
        model, observed = checked_currentness_model(model, currentness, verification=verification)
        if view_name == 'verification':
            verification = currentness.verification
    model = model.snapshot()
    data = {'view_name': view_name, 'source_kind': 'supplied_project',
        'schema_version': MODEL_SCHEMA_VERSION, 'profiles': list(model.profile.profile_chain),
        'project_id': model.binding.project_id, 'scope_descriptor': _default_scope(),
        'model_root_sha256': model.manifest(model.artifacts, _default_scope()).sha256,
        'input_sha256': model._sources_sha256, 'fallback': False}
    if view_name == 'verification':
        from ..verification.coverage import assess_verification_coverage
        coverage = assess_verification_coverage(model, verification, currentness=currentness)
        coverage_data = coverage.data
        data.update(mode='evaluated_requirement_coverage',
            selection_scope_descriptor=verification.data['scope_descriptor'],
            summary=verification.summary, coverage=coverage_data, coverage_sha256=coverage.sha256,
            rows=coverage_data['requirements'], row_count=coverage_data['totals']['requirements'],
            verification_evaluated=True, computed_reports=_computed_reports(verification=coverage_data),
            validation_scope=coverage_data['validation_scope'])
    elif view_name == 'specification':
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
        if observed is not None:
            from ..verification._read_evaluation import computed_results
            coverage_data = observed['observation']['coverage']
            subjects = computed_results(coverage_data)
            for row in rows:
                row['verification_result'] = subjects.get(row['requirement_id'])
            data.update(mode='evaluated_traceability', verification_evaluated=True,
                computed_reports=_computed_reports(verification=coverage_data))
    if observed is not None:
        data['currentness'] = observed
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
