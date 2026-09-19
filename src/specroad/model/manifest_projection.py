"""Canonical manifest/hash projection shared by supplied and resolved scopes.

Callers validate the descriptor, membership, resource roles and bindings first.
This is a value projection, never a completeness certificate or I/O operation.
"""
from .canonical import canonical_json_sha256


def project_manifest_value(project_id, descriptor, artifacts, resources, attachments,
                           boundaries, configuration_sha256, profile_sha256):
    scope = {
        'project_id': project_id, 'scope_descriptor': descriptor,
        'artifacts': sorted(artifacts, key=lambda r: r['id'].encode('utf-8')),
        'resources': sorted(resources, key=lambda r: (r['id'].encode('utf-8'),
                            r['version'].encode('utf-8'), r['kind'])),
        'attachments': sorted(attachments, key=lambda r: r['path'].encode('utf-8')),
        'boundary_references': sorted(boundaries, key=lambda r: tuple(
            r.get(key, '').encode('utf-8') for key in ('source_id', 'relation_id', 'target_id'))),
        'configuration_sha256': configuration_sha256, 'profile_sha256': profile_sha256,
    }
    return {'model_manifest_version': 'model-manifest-v1', **scope,
            'scope_sha256': canonical_json_sha256(scope)}
