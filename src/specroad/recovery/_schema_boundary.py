"""Reject unsupported declared normative formats without interpreting old data.

This is a format boundary, not a Legacy reader or a general attachment parser.
Broken current bytes remain eligible for the existing backup/recovery rules.
Opaque payloads and already defined operational formats keep their contracts.
"""
from ..model.errors import ModelError
from ..model.versions import SCHEMA_VERSION
from ..storage.json_syntax import parse_json_object
from .values import RestoreError


def _normative_path(path):
    return (path == 'specroad.json' or path.endswith('.json') and
            path.split('/', 1)[0] in ('spec', 'profiles', 'rules', 'mappings'))


def declared_resource(raw, path, *, normative=False):
    """Check an explicit version/registration; do not infer missing old schemas.

    The original native reader still performs the full schema and content
    validation. In payload closures only an identifiable SpecRoad resource is
    inspected; a third-party JSON attachment's schema label is not our format.
    """
    if path == 'mappings/legacy-manifest.json':
        raise RestoreError('restore_legacy_source_contract_required', path=path)
    try:
        value = parse_json_object(raw, path=path)
    except ModelError:
        return
    legacy = (value.get('mapping_id') == 'legacy-preservation' or
              'legacy_manifest_version' in value and (normative or _normative_path(path) or
                                                        'mapping_id' in value))
    if legacy:
        error = RestoreError('restore_legacy_source_contract_required', path=path)
        error.pointer = '/legacy_manifest_version'
        raise error
    # Missing other mandatory fields must not turn an identifiable unsupported
    # original into discardable damage. Full native schema validity is separate.
    recognizable = (normative or _normative_path(path) or
        'artifact_type' in value or 'project_id' in value and
        any(key in value for key in ('managed_paths', 'id_prefix', 'project_name', 'validation_policy')) or
        any(key in value for key in ('profile_id', 'rule_id', 'mapping_id')))
    if recognizable and 'schema_version' in value and value['schema_version'] != SCHEMA_VERSION:
        error = RestoreError('restore_unsupported_source_schema_version', path=path)
        error.pointer = '/schema_version'
        error.highest_supported = SCHEMA_VERSION
        raise error


def declared_files(files, *, include_payloads=True):
    """Visit normative paths and, when required, their preserved byte closure."""
    for path, raw in sorted(files.items()):
        if _normative_path(path) or include_payloads and path.startswith(('archive/', 'attachments/')):
            declared_resource(raw, path)
