"""Type/ID ordered fallback from explicitly supplied partial or legacy bytes.

This is a read-only presentation adapter for future bundle/legacy readers, not
one of those readers. It authenticates neither an origin root nor a bundle and
does not transform legacy records into current-schema artifacts.
"""
from .._metadata import MODEL_SCHEMA_VERSION
from ..graph.boundary_validation import validate_boundary_references
from ..graph.relations import SourceRelations
from ..graph.scope_descriptors import ScopeDescriptor
from ..graph._symmetry import canonical_relation
from ..model.canonical import canonical_json_sha256
from ..model.identity_values import ArtifactIdentity, LEGACY_SCHEME
from ..model.paths import project_path
from ..storage.json_syntax import parse_json_object
from ..validation import ModelDocument
from .builtin_views import BuiltinViewError, _bound_record, _result, _typed_records


def resolve_type_fallback(documents, *, source_kind, scope_descriptor=None, boundary_references=()):
    """Project original records only when no active primary is supplied.

    Partial input uses native current-schema fields and exact weak-boundary
    checks. Legacy input checks only the 0.1 identity/title/revision envelope;
    original fields and bytes stay unchanged and its semantics remain unchecked.
    The declared source kind grants no write permission or validation success.
    """
    if type(source_kind) is not str or source_kind not in ('partial', 'legacy'):
        raise BuiltinViewError('builtin_fallback_source_kind_required', pointer='/source_kind', exit_code=2)
    if type(documents) not in (list, tuple) or any(type(d) is not ModelDocument for d in documents):
        raise BuiltinViewError('builtin_fallback_documents_required')
    if type(boundary_references) not in (list, tuple):
        raise BuiltinViewError('builtin_fallback_boundaries_required')
    documents = tuple(sorted(documents, key=lambda d: d.path))
    paths = [project_path(d.path) for d in documents]
    if len({p.casefold() for p in paths}) != len(paths):
        raise BuiltinViewError('builtin_fallback_duplicate_path')
    records = {}; prefixes = set()
    for document in documents:
        value = parse_json_object(document.content, path=document.path)
        if source_kind == 'legacy':
            if value.get('schema_version') != '0.1.0':
                raise BuiltinViewError('builtin_fallback_legacy_version_required', path=document.path, pointer='/schema_version')
            identifier = value.get('id')
            if type(identifier) is not str:
                raise BuiltinViewError('builtin_fallback_identity_required', path=document.path, pointer='/id')
            identity = ArtifactIdentity(identifier, value.get('id_scheme', LEGACY_SCHEME),
                                        value.get('artifact_type'), identifier.split('-')[0])
            if identity.id_scheme != LEGACY_SCHEME:
                raise BuiltinViewError('builtin_fallback_legacy_identity_required', path=document.path, pointer='/id_scheme')
            if type(value.get('title')) is not str or not value['title'].strip():
                raise BuiltinViewError('builtin_fallback_title_required', path=document.path, pointer='/title')
            if type(value.get('revision')) is not int or value['revision'] < 1:
                raise BuiltinViewError('builtin_fallback_revision_required', path=document.path, pointer='/revision')
        else:
            identity = SourceRelations(document.content, path=document.path).identity
            if document.path != identity.path:
                raise BuiltinViewError('builtin_fallback_artifact_path_mismatch', path=document.path)
        if identity.id in records:
            raise BuiltinViewError('builtin_fallback_duplicate_identity', path=document.path)
        prefixes.add(identity.id_prefix)
        records[identity.id] = _bound_record(document, value)
    if len(prefixes) > 1:
        raise BuiltinViewError('builtin_fallback_mixed_project_prefix')
    boundaries = []; descriptor = None
    if source_kind == 'partial':
        descriptor = ScopeDescriptor(scope_descriptor)
        if descriptor.data['boundary_policy'] != 'partial' or descriptor.data['scope_kind'] not in ('document', 'release'):
            raise BuiltinViewError('builtin_fallback_partial_scope_required', pointer='/scope_descriptor')
        selector = descriptor.data['selector']
        if selector[descriptor.data['scope_kind'] + '_id'] not in records:
            raise BuiltinViewError('builtin_fallback_scope_root_missing', pointer='/scope_descriptor/selector')
        records = _typed_records(documents)
        checked = validate_boundary_references(
            [SourceRelations(d.content, path=d.path) for d in documents],
            boundary_references, descriptor=descriptor)
        if any(canonical_relation(edge) != edge for edge in checked.local_relations):
            raise BuiltinViewError('noncanonical_symmetric_relation', pointer='/relations')
        boundaries = [value.data for value in checked.boundary_references]
        descriptor = descriptor.data
    elif scope_descriptor is not None or boundary_references:
        raise BuiltinViewError('builtin_fallback_legacy_scope_not_supported')
    primary = [bound['artifact_id'] for bound in records.values()
        if bound['artifact_type'] == 'document'
        and bound['record'].get('document_role') == 'primary_specification'
        and bound['record'].get('maturity') != 'retired']
    if primary:
        raise BuiltinViewError('builtin_fallback_primary_present', pointer='/document_role')
    ordered = sorted(records, key=lambda key: (records[key]['artifact_type'], key))
    groups = []
    for identifier in ordered:
        kind = records[identifier]['artifact_type']
        if not groups or groups[-1]['artifact_type'] != kind:
            groups.append({'artifact_type': kind, 'artifact_ids': []})
        groups[-1]['artifact_ids'].append(identifier)
    inventory = [{'path': d.path, 'sha256': records[parse_json_object(d.content)['id']]['source_sha256']} for d in documents]
    data = {'view_name': 'specification', 'mode': 'type_fallback', 'fallback': True,
        'source_kind': source_kind, 'schema_version': '0.1.0' if source_kind == 'legacy' else MODEL_SCHEMA_VERSION,
        'scope_descriptor': descriptor, 'boundary_references': boundaries,
        'primary_document': None, 'records': records, 'groups': groups, 'artifact_ids': ordered,
        'input_sha256': canonical_json_sha256({'source_kind': source_kind, 'sources': inventory,
            'scope_descriptor': descriptor, 'boundary_references': boundaries}),
        'model_root_sha256': None, 'source_context_verified': False, 'origin_hashes_verified': False,
        'legacy_semantics_verified': False,
        'validation_scope': ('supplied_partial_record_fields_and_boundary_bindings' if source_kind == 'partial'
                             else 'supplied_legacy_identity_title_revision_envelopes')}
    return _result(data, {d.path: d.content for d in documents})


def render_type_fallback(documents, *, source_kind, scope_descriptor=None,
                         boundary_references=(), output_format='markdown'):
    """Escape passive original fields, without migration or source discovery."""
    from ._render_formats import Emitter
    if type(output_format) is not str or output_format not in ('markdown', 'html'):
        raise BuiltinViewError('render_format_not_supported', pointer='/output_format')
    result = resolve_type_fallback(documents, source_kind=source_kind,
        scope_descriptor=scope_descriptor, boundary_references=boundary_references)
    data = result.data
    nodes = [{'type': 'record', 'record': data['records'][identifier]['record'], 'mode': 'full', 'level': 2}
             for identifier in data['artifact_ids']]
    metadata = {key: data[key] for key in ('tool_version', 'schema_version', 'source_kind',
        'input_sha256', 'model_root_sha256', 'source_context_verified', 'legacy_semantics_verified')}
    metadata['projection_sha256'] = result.sha256
    return Emitter(output_format).output(metadata, 'specification', nodes)
