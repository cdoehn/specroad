"""Inert, relocatable inputs for the closed document Work adapter."""
from ..changes.target_model import TargetModel, _default_scope
from ..graph.relations import SourceRelations
from ..model.attachments import AttachmentDescriptor
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.language_package_values import LanguagePackage
from ..model.language_registry import LanguageRegistry
from ..model.model_manifest import ProjectReadBinding
from ..profiles.composition import compose_profiles
from ..profiles.values import ProfileResource
from ..validation import ModelDocument
from ..work._data_contract import _hash, _object, _parse, _path, _text
from ..work.resume import _require


def capture(model, document_id):
    _require(type(model) is TargetModel, 'document_target_model_required')
    _require(type(document_id) is str and bool(document_id), 'document_id_required')
    model = model.snapshot()
    context = {'format_version': 'document-work-inputs-v1', 'document_id': document_id,
        'project_id': model.binding.project_id, 'profile_chain': list(model.profile.profile_chain),
        'documents': [d.path for d in model.documents],
        'resources': [d.path for d in model.resource_files],
        'packages': [str(n) + '.json' for n in range(len(model.language_packages))],
        'attachments': [a.data for a in model.attachment_descriptors],
        'reservations': model.reservations, 'input_sha256': model._sources_sha256,
        'model_root_sha256': model.manifest(model.artifacts, _default_scope()).sha256}
    inputs = [{'root_id': 'project', 'path': p, 'raw': b} for p, b in sorted(model.source_files.items())]
    inputs += [{'root_id': 'packages', 'path': p, 'raw': v.source_bytes}
               for p, v in zip(context['packages'], model.language_packages)]
    inputs.append({'root_id': 'context', 'path': 'document.json', 'raw': canonical_json_bytes(context)})
    return model, context, inputs


def saved(current):
    inputs = {(i['root_id'], i['path']): current.objects[i['sha256']]
              for i in current.entries('inputs')}
    _require(('context', 'document.json') in inputs, 'document_context_required')
    raw = inputs['context', 'document.json']; context = _parse(raw)
    _object(context, ('format_version', 'document_id', 'project_id', 'profile_chain',
        'documents', 'resources', 'packages', 'attachments', 'reservations',
        'input_sha256', 'model_root_sha256'))
    _require(canonical_json_bytes(context) == raw
             and context['format_version'] == 'document-work-inputs-v1'
             and type(context['document_id']) is str and bool(context['document_id']),
             'invalid_document_context')
    for key in ('documents', 'resources', 'packages', 'profile_chain'):
        values = context[key]
        _require(type(values) is list and all(type(p) is str and bool(p) for p in values)
                 and len(set(values)) == len(values), 'invalid_document_context')
    _require(bool(context['profile_chain']), 'document_profile_required')
    _text(context['project_id']); _hash(context['input_sha256']); _hash(context['model_root_sha256'])
    paths = context['documents'] + context['resources'] + ['specroad.json']
    _require(len(set(paths)) == len(paths), 'overlapping_document_inputs')
    for path in paths: _path(path)
    _require(context['packages'] == [str(n) + '.json' for n in range(len(context['packages']))],
             'invalid_document_package_inventory')
    _require(type(context['attachments']) is list, 'invalid_document_attachments')
    for attachment in context['attachments']: AttachmentDescriptor.from_data(attachment)
    _object(context['reservations'], ('reserved_artifact_ids', 'reserved_relation_ids', 'previously_approved_ids'))
    for values in context['reservations'].values():
        _require(type(values) is list and all(type(v) is str and bool(v) for v in values)
                 and len(values) == len(set(values)), 'invalid_document_reservations')
    expected = {('context', 'document.json'), ('project', 'specroad.json')}
    expected.update(('project', p) for p in context['documents'] + context['resources'])
    expected.update(('packages', p) for p in context['packages'])
    _require(set(inputs) == expected, 'document_input_inventory_changed')
    for path in context['documents']: SourceRelations(inputs['project', path], path=path)
    return context, inputs


def declarations(context, artifacts):
    # All source blocks are accounted for. Selection is decided only by the
    # completed native composition, never by a planner's partial traversal.
    return [{'key': 'compose', 'phase': 'document_composition',
             'range': {'kind': 'compose', 'artifact_id': context['document_id']}},
        *({'key': a['id'], 'phase': 'document_blocks',
           'range': {'kind': 'block', 'artifact_id': a['id']}}
          for a in sorted(artifacts, key=lambda a: a['id']) if a['artifact_type'] == 'content_block')]


def restore(current, location):
    context, inputs = saved(current)
    files = {p: b for (root, p), b in inputs.items() if root == 'project'}
    config = ProjectConfiguration(_parse(files['specroad.json']))
    registry = None; declared = config.data.get('language_registry')
    if declared is not None:
        registry = LanguageRegistry(files[declared['path']], expected_sha256=declared['sha256'],
                                    expected_version=declared['registry_version'])
    packages = tuple(LanguagePackage(inputs['packages', p]) for p in context['packages'])
    from ..model.paths import classify_path, PathClass
    resources = tuple(ModelDocument(p, files[p]) for p in context['resources'])
    profiles = [ProfileResource(d.content) for d in resources
                if (declared is None or d.path != declared['path'])
                and classify_path(d.path, config) is PathClass.PROFILE]
    chain = context['profile_chain']
    profile = compose_profiles(profiles, core_key=chain[0], cli_profiles=chain[1:],
                               language_registry=registry, language_packages=packages)
    _require(location._allocated_identity is not None, 'verified_work_location_required')
    # This is the observed Work source, not the old project's physical identity
    # and not a current-project/write authorization. Physical roots are not saved.
    binding = ProjectReadBinding(context['project_id'], str(location.path), location._allocated_identity)
    model = TargetModel(files['specroad.json'], binding,
        [ModelDocument(p, files[p]) for p in context['documents']], profile=profile,
        resource_files=resources, language_packages=packages,
        attachments=[AttachmentDescriptor.from_data(a) for a in context['attachments']],
        **context['reservations'])
    _require(model._sources_sha256 == context['input_sha256']
             and model.manifest(model.artifacts, _default_scope()).sha256 == context['model_root_sha256'],
             'document_saved_model_changed')
    return model
