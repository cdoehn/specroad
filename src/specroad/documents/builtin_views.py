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
from ._builtin_providers import (require_view_name, roadmap_fields,
                                verification_fields, traceability_verification_fields)
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


def resolve_builtin_view(model, view_name, *, verification=None, currentness=None,
                         readiness=None, readiness_gates=(), blocker_reviews=(),
                         blocker_verifier=None):
    """Resolve specification, stored traceability or explicitly bound coverage.

    A full project's specification always requires its unique active primary.
    Missing/invalid primary data never implicitly opts into the fallback API.
    Verification requires a computed input for the exact supplied snapshot.
    Roadmap uses the native planning projection. Optional Release readiness
    is recomputed from an exact native context, never from a supplied report.
    """
    from ..changes.target_model import TargetModel, _default_scope
    if type(model) is not TargetModel:
        raise ModelError('document_target_model_required')
    require_view_name(view_name)
    if view_name == 'verification' and verification is None and currentness is None:
        raise BuiltinViewProviderError(view_name)
    if verification is not None and view_name not in ('verification', 'traceability'):
        raise BuiltinViewError('builtin_verification_input_not_applicable', pointer='/view_name')
    readiness_supplied = (readiness is not None or readiness_gates != ()
                          or blocker_reviews != () or blocker_verifier is not None)
    if readiness_supplied and view_name != 'roadmap':
        raise BuiltinViewError('builtin_readiness_input_not_applicable', pointer='/view_name')
    if readiness_supplied and readiness is None:
        raise BuiltinViewError('builtin_readiness_context_required', pointer='/readiness')
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
    if view_name == 'roadmap':
        data.update(roadmap_fields(model, readiness, readiness_gates,
                                   blocker_reviews, blocker_verifier))
    elif view_name == 'verification':
        data.update(verification_fields(model, verification, currentness))
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
        if observed is not None or verification is not None:
            data.update(traceability_verification_fields(model, verification, observed, rows))
    if observed is not None:
        data['currentness'] = observed
    return _result(data, model.source_files)


def render_builtin_view(model, view_name, *, output_format='markdown', verification=None,
                        currentness=None, readiness=None, readiness_gates=(),
                        blocker_reviews=(), blocker_verifier=None):
    """Return bytes through the existing safe document/table renderers."""
    from .rendering import _snapshot, render_document
    from ._render_formats import Emitter
    from .requirement_presentation import resolve_requirement_presentation
    from ..model.content_language import ContentLanguage
    model = _snapshot(model, output_format)
    resolved = resolve_builtin_view(model, view_name, verification=verification,
        currentness=currentness, readiness=readiness, readiness_gates=readiness_gates,
        blocker_reviews=blocker_reviews, blocker_verifier=blocker_verifier)
    data = resolved.data
    if view_name == 'specification':
        return render_document(model, data['primary_document']['artifact_id'], output_format=output_format)
    if view_name in ('roadmap', 'verification'):
        def table(identifier, rows, fields):
            return {'type': 'table', 'id': identifier, 'data': {
                'columns': [{'heading': field} for field in fields],
                'rows': [{'cells': [{'type': 'object', 'value': row[field]} for field in fields]}
                         for row in rows]}}
        if view_name == 'verification':
            nodes = [table('verification', data['rows'],
                ('requirement_id', 'verification_plan_status', 'verification_result', 'checks', 'reasons'))]
        else:
            nodes = [table('roadmap', data['rows'],
                ('artifact_id', 'artifact_type', 'stored', 'scheduled_for_ids', 'parent_ids', 'dependency_ids')),
                table('risks', data['roadmap']['risks'], ('artifact_id', 'stored', 'mitigated_by_ids')),
                table('schedule', data['roadmap']['schedule_groups'],
                    ('planning_id', 'scheduled_artifact_ids', 'milestone_ids'))]
            if data['readiness'] is not None:
                nodes.append(table('readiness', data['readiness']['gates'],
                    ('gate_id', 'status', 'subject_ids', 'findings')))
        metadata = {key: data[key] for key in ('tool_version', 'schema_version', 'profiles',
            'project_id', 'model_root_sha256', 'input_sha256', 'verification_evaluated',
            'release_readiness_evaluated', 'computed_reports')}
        metadata['projection_sha256'] = resolved.sha256
        metadata.update({key: data[key] for key in ('summary', 'readiness', 'readiness_sha256') if key in data})
        return Emitter(output_format).output(metadata, view_name, nodes)
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
