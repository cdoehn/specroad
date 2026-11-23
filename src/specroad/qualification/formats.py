"""Closed normative format boundary, separate from Legacy reading and Restore."""
from ..model.errors import ModelError
from ..model.versions import SCHEMA_VERSION, PROJECT_SCHEMA_VERSIONS, PLAN_TYPES, PLAN_SCHEMA_VERSION
from ..storage.json_syntax import parse_json_object
from .errors import QualificationError


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
        raise QualificationError('restore_legacy_source_contract_required', path=path)
    try:
        value = parse_json_object(raw, path=path)
    except ModelError:
        return
    legacy = (value.get('mapping_id') == 'legacy-preservation' or
              'legacy_manifest_version' in value and (normative or _normative_path(path) or
                                                        'mapping_id' in value))
    if legacy:
        error = QualificationError('restore_legacy_source_contract_required', path=path)
        error.pointer = '/legacy_manifest_version'
        raise error
    # Missing other mandatory fields must not turn an identifiable unsupported
    # original into discardable damage. Full native schema validity is separate.
    recognizable = (normative or _normative_path(path) or
        'artifact_type' in value or 'project_id' in value and
        any(key in value for key in ('managed_paths', 'id_prefix', 'project_name', 'validation_policy')) or
        any(key in value for key in ('profile_id', 'rule_id', 'mapping_id')))
    # Archived semantic project configuration retains the project schema
    # version. Its content address is not an artifact-type declaration.
    # Actual reconstruction and manifest binding remain mandatory.
    project_configuration = (path == 'specroad.json' or
        path.startswith('archive/objects/') and 'artifact_type' not in value
        and {'project_id', 'id_prefix', 'managed_paths'} <= value.keys())
    supported = (PROJECT_SCHEMA_VERSIONS if project_configuration else
                 (PLAN_SCHEMA_VERSION,) if value.get('artifact_type') in PLAN_TYPES else (SCHEMA_VERSION,))
    if recognizable and 'schema_version' in value and value['schema_version'] not in supported:
        error = QualificationError('restore_unsupported_source_schema_version', path=path)
        error.pointer = '/schema_version'
        error.highest_supported = supported[-1]
        raise error


def declared_files(files, *, include_payloads=True):
    """Visit normative paths and, when required, their preserved byte closure."""
    from ..migration.model_inputs import qualified
    from .errors import require
    legacy = None
    if 'mappings/legacy-manifest.json' in files:
        try:
            project_id = parse_json_object(files['specroad.json'])['project_id']
            legacy = qualified(files, project_id)
        except (ModelError, KeyError) as error:
            raise QualificationError('restore_legacy_source_contract_required',
                               path='mappings/legacy-manifest.json') from error
    protected = () if legacy is None else legacy.protected_paths
    for path, raw in sorted(files.items()):
        if path in protected:
            continue
        if _normative_path(path) or include_payloads and path.startswith(('archive/', 'attachments/')):
            declared_resource(raw, path)
