"""Reconstruct qualified source bytes without filling gaps from a live model."""
from ..qualification.archives import baseline_objects

from ..archive._snapshot_values import SNAPSHOT_VALUES
from ..bundles import verify_bundle
from ..bundles.container import BundleContainer
from ..changes.target_model import _default_scope
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.paths import artifact_path
from ..model.record_schemas import validate_record_fields
from ..model.semantic_configuration import semantic_configuration
from ..storage.json_syntax import parse_json_object
from ._codec import file_row, safe_path, namespace
from ._schema_boundary import declared_files, declared_resource
from .values import require




def reconstruct(kind, raw, read_dependency, *, operational=None):
    """Return source files, explicit source additions and the declared root.

    Model/primary/history qualification is separate and still mandatory. The
    operational values are explicit only for Baselines; bundle config is exact.
    """
    if kind == 'project_bundle':
        require(operational is None, 'restore_bundle_operational_override', exit_code=2)
        container = BundleContainer(raw)
        manifest = container.manifest
        require(manifest['bundle_kind'] == 'project' and manifest['read_only'] is False
                and manifest['scope_descriptor'] == _default_scope()
                and not manifest['boundary_references'], 'restore_full_project_source_required')
        declared_files(container.files)
        verify_bundle(raw)
        require(not any(r['reason'] == 'operational_receipts_excluded'
                        for r in manifest['excluded_contents']),
                'restore_receipt_history_provider_required')
        return container.files, {}, [], manifest['bundle_model_root_sha256'], manifest['project_id']
    require(kind == 'baseline', 'restore_source_kind_invalid', exit_code=2)
    require(type(operational) is dict and set(operational) == {'default_locale', 'generated_path'}
            and all(type(v) is str for v in operational.values()),
            'restore_explicit_operational_configuration_required', exit_code=2)
    declared_resource(raw, 'source:baseline', normative=True)
    record = parse_json_object(raw)
    validate_record_fields(record, expected_type='baseline')
    require(record['baseline_state'] == 'sealed' and record['scope_descriptor'] == _default_scope(),
            'restore_full_project_source_required')
    objects = baseline_objects(raw, read_dependency)
    files, semantic = {}, None
    for row in record['manifest']:
        content = objects[row['object_path']]
        if row['role'] == 'semantic_configuration':
            semantic = content
        elif row['role'] not in SNAPSHOT_VALUES:
            path = safe_path(row['source_path'])
            require(path not in files, 'restore_baseline_path_collision')
            files[path] = content
    require(semantic is not None, 'restore_semantic_configuration_missing')
    configuration = ProjectConfiguration({**parse_json_object(semantic), **operational})
    require(canonical_json_bytes(semantic_configuration(configuration)) == semantic,
            'restore_semantic_configuration_changed')
    files['specroad.json'] = canonical_json_bytes(configuration.data)
    preserved = {}
    baseline_path = artifact_path('baseline', record['id'], configuration.id_prefix)
    for path, content, reason in [(baseline_path, raw, 'source_baseline'),
                                  *((p, b, 'source_archive') for p, b in objects.items())]:
        if path in files:
            require(files[path] == content, 'restore_source_history_conflict', path=path, exit_code=6)
        else:
            preserved[path] = (content, [reason])
    namespace([*files, *preserved])
    dependencies = [file_row(p, objects[p]) for p in sorted(objects, key=lambda p: p.encode('utf-8'))]
    return files, preserved, dependencies, record['model_root_sha256'], configuration.project_id
