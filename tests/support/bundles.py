"""Owned bundle inputs with real scope hashes, not fully validated projects."""
from specroad import __version__
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_seeds import resolve_scope_seeds
from specroad.graph.scope_closure import resolve_scope_closure
from specroad.graph.scope_hash import fingerprint_scope
from specroad.model.canonical import canonical_json_bytes
from specroad.model.configuration import ProjectConfiguration
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from .closure import observe
from .model import configuration_value
from .relations import artifact, aid, edge
from .scopes import descriptor, inputs


def bundle_inputs(kind='project'):
    configuration = ProjectConfiguration(configuration_value())
    values = [artifact('document', relations=[edge('contains', aid('section'))]),
              artifact('section', relations=[edge('contains', aid('content_block'), number=2)]),
              artifact('content_block', relations=[edge('references', aid(), number=3)]),
              artifact(relations=[edge('duplicates', aid(number=2), number=4)]),
              artifact(number=2), artifact('release')]
    inventory = inputs(*values)
    dependencies = observe(inventory)
    binding = ProjectReadBinding('sample', '/owned/bundle-fixture', (1, 2))

    def model(scope):
        seeds = resolve_scope_seeds(ScopeDescriptor(scope), inventory)
        closure = resolve_scope_closure(seeds, dependencies)
        return fingerprint_scope(configuration, binding, closure, dependencies,
                                 effective_profile={}), closure

    origin, _ = model(descriptor('project'))
    scope = (descriptor('project') if kind == 'project' else
             descriptor(kind, {kind + '_id': aid(kind)}, boundary_policy='partial'))
    selected, closure = model(scope)
    data = selected.data
    metadata = {
        'bundle_format_version': '1.0.0', 'bundle_kind': 'project' if kind == 'project' else 'partial',
        'read_only': kind != 'project', 'project_id': 'sample', 'tool_version': __version__,
        'schema_version': '0.2.0', 'scope_descriptor': scope,
        'origin_model_root_sha256': origin.sha256, 'bundle_model_root_sha256': selected.sha256,
        'profile_sha256': data['profile_sha256'], 'configuration_sha256': data['configuration_sha256'],
        'boundary_references': data['boundary_references'], 'excluded_contents': [],
        'idempotency_scope': 'portable' if kind == 'project' else 'local_only',
    }
    payloads = {'specroad.json': canonical_json_bytes(configuration.data)}
    for value in values:
        path = artifact_path(value['artifact_type'], value['id'], 'SR')
        if value['id'] in closure.artifact_ids:
            payloads[path] = canonical_json_bytes(value)
        else:
            metadata['excluded_contents'].append({'path': path, 'reason': 'outside_scope'})
    metadata['excluded_contents'].sort(key=lambda r: r['path'].encode('utf-8'))
    return metadata, payloads
