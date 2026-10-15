"""Shared projections of resolved, owned configuration values; no defaults."""
from ..model.canonical import canonical_json_sha256


def srx_configuration_root(identifier, effective_values):
    return {'configuration_id': identifier, 'effective_values': effective_values}


def configuration_scope_hash(project_sha256, selected_sha256):
    return canonical_json_sha256({'project_configuration_sha256': project_sha256,
                                  'selected_configuration_sha256': selected_sha256})
