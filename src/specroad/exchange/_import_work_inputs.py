"""Closed, inert input inventory for explicit-candidate import planning Work.

Original project roots and live callbacks are never serialized. The complete
owned model, source bytes, selected mapping and candidates survive relocation.
This remains the existing explicit_parsed_artifacts profile, not a file parser.
"""
from ..changes.target_model import TargetModel, _default_scope
from ..changes.target_values import TargetPolicy
from ..mappings import ExchangeMapping, select_mapping
from ..model.attachments import AttachmentDescriptor
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.language_package_values import LanguagePackage
from ..model.language_registry import LanguageRegistry
from ..model.model_manifest import ProjectReadBinding
from ..model.paths import classify_path, PathClass
from ..profiles.composition import compose_profiles
from ..profiles.values import ProfileResource
from ..validation import ModelDocument
from ..work._data_contract import _count, _hash, _object, _parse, _path, _text
from ..work.resume import _require
from .planning import _prepare_import_inputs

OPTIONS = ('input_format', 'mapping_key', 'mapping_sha256', 'strategy',
           'change_plan_id', 'request_id', 'actor', 'planned_at',
           'scope_descriptor', 'metadata_policy_version', 'strict')


def capture(model, candidates, *, input_format, input_bytes, mapping_resources,
        mapping_key, mapping_sha256, strategy, change_plan_id, request_id, actor,
        planned_at, scope_descriptor, metadata_policy_version, policy, strict=False):
    _require(type(policy) is TargetPolicy and type(strict) is bool, 'import_work_policy_required')
    model, candidates, selected = _prepare_import_inputs(model, candidates,
        input_format=input_format, input_bytes=input_bytes, mapping_resources=mapping_resources,
        mapping_key=mapping_key, mapping_sha256=mapping_sha256, strategy=strategy)
    options = dict(input_format=input_format, mapping_key=mapping_key,
        mapping_sha256=mapping_sha256, strategy=strategy, change_plan_id=change_plan_id,
        request_id=request_id, actor=actor, planned_at=planned_at,
        scope_descriptor=scope_descriptor, metadata_policy_version=metadata_policy_version,
        strict=strict)
    context = {'format_version': 'import-work-inputs-v1', 'options': options,
        'policy': policy.data(), 'candidate_count': len(candidates),
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
    inputs += [{'root_id': 'candidates', 'path': str(n) + '.json', 'raw': canonical_json_bytes(c)}
               for n, c in enumerate(candidates)]
    inputs += [{'root_id': 'import', 'path': 'source.bin', 'raw': input_bytes},
               {'root_id': 'import', 'path': 'mapping.json', 'raw': selected.resource.source_bytes},
               {'root_id': 'import', 'path': 'context.json', 'raw': canonical_json_bytes(context)}]
    return context, inputs


def saved(current):
    inputs = {(i['root_id'], i['path']): current.objects[i['sha256']] for i in current.entries('inputs')}
    _require(('import', 'context.json') in inputs, 'import_work_context_required')
    raw = inputs['import', 'context.json']; context = _parse(raw)
    _object(context, ('format_version', 'options', 'policy', 'candidate_count',
        'project_id', 'profile_chain', 'documents', 'resources', 'packages',
        'attachments', 'reservations', 'input_sha256', 'model_root_sha256'))
    _require(canonical_json_bytes(context) == raw and context['format_version'] == 'import-work-inputs-v1',
             'invalid_import_work_context')
    _object(context['options'], OPTIONS); _count(context['candidate_count'])
    _require(type(context['options']['strict']) is bool, 'invalid_import_work_context')
    _object(context['policy'], ('command_id', 'version', 'required_gate_ids'))
    policy = context['policy']
    _require(type(policy['required_gate_ids']) is list, 'invalid_import_work_policy')
    TargetPolicy(policy['command_id'], policy['version'], tuple(policy['required_gate_ids']))
    for key in ('documents', 'resources', 'packages', 'profile_chain'):
        values = context[key]
        _require(type(values) is list and all(type(p) is str and bool(p) for p in values)
                 and len(set(values)) == len(values), 'invalid_import_work_inventory')
    _require(bool(context['profile_chain']), 'import_work_profile_required')
    _text(context['project_id']); _hash(context['input_sha256']); _hash(context['model_root_sha256'])
    paths = context['documents'] + context['resources'] + ['specroad.json']
    _require(len(set(paths)) == len(paths), 'overlapping_import_work_inputs')
    for path in paths: _path(path)
    _require(context['packages'] == [str(n) + '.json' for n in range(len(context['packages']))],
             'invalid_import_work_packages')
    _require(type(context['attachments']) is list, 'invalid_import_work_attachments')
    for attachment in context['attachments']: AttachmentDescriptor.from_data(attachment)
    _object(context['reservations'], ('reserved_artifact_ids', 'reserved_relation_ids', 'previously_approved_ids'))
    for values in context['reservations'].values():
        _require(type(values) is list and all(type(v) is str and bool(v) for v in values)
                 and len(values) == len(set(values)), 'invalid_import_work_reservations')
    expected = {('import', p) for p in ('context.json', 'mapping.json', 'source.bin')}
    expected.update(('project', p) for p in paths)
    expected.update(('packages', p) for p in context['packages'])
    expected.update(('candidates', str(n) + '.json') for n in range(context['candidate_count']))
    _require(set(inputs) == expected, 'import_work_input_inventory_changed')
    return context, inputs


def declarations(context):
    return [*({'key': 'candidate-' + str(n), 'phase': 'import_candidates',
               'range': {'candidate_index': n}} for n in range(context['candidate_count'])),
            {'key': 'target', 'phase': 'import_target', 'range': {}}]


def supplied(context, inputs):
    """Reconstruct data, never a trusted policy, gate callback or authority."""
    candidates = [_parse(inputs['candidates', str(n) + '.json']) for n in range(context['candidate_count'])]
    resource = ExchangeMapping(inputs['import', 'mapping.json'])
    options = context['options']
    selected = select_mapping([resource], key=options['mapping_key'], expected_sha256=options['mapping_sha256'])
    _require(resource.data['source_format'] == ('reqif' if options['input_format'] == 'reqifz'
                                               else options['input_format']), 'import_work_mapping_changed')
    return candidates, selected, {**options, 'input_bytes': inputs['import', 'source.bin']}


def restore(context, inputs, location):
    files = {p: b for (root, p), b in inputs.items() if root == 'project'}
    config = ProjectConfiguration(_parse(files['specroad.json']))
    registry = None; declared = config.data.get('language_registry')
    if declared is not None:
        registry = LanguageRegistry(files[declared['path']], expected_sha256=declared['sha256'],
                                    expected_version=declared['registry_version'])
    packages = tuple(LanguagePackage(inputs['packages', p]) for p in context['packages'])
    resources = tuple(ModelDocument(p, files[p]) for p in context['resources'])
    profiles = [ProfileResource(d.content) for d in resources
                if (declared is None or d.path != declared['path'])
                and classify_path(d.path, config) is PathClass.PROFILE]
    chain = context['profile_chain']
    profile = compose_profiles(profiles, core_key=chain[0], cli_profiles=chain[1:],
                               language_registry=registry, language_packages=packages)
    _require(location._allocated_identity is not None, 'verified_work_location_required')
    binding = ProjectReadBinding(context['project_id'], str(location.path), location._allocated_identity)
    model = TargetModel(files['specroad.json'], binding,
        [ModelDocument(p, files[p]) for p in context['documents']], profile=profile,
        resource_files=resources, language_packages=packages,
        attachments=[AttachmentDescriptor.from_data(a) for a in context['attachments']],
        **context['reservations'])
    _require(model._sources_sha256 == context['input_sha256']
             and model.manifest(model.artifacts, _default_scope()).sha256 == context['model_root_sha256'],
             'import_work_saved_model_changed')
    return model
