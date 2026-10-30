"""Reconstruct a complete plan from owned source and inventory snapshots.

No captured label proves current files. The caller must check live origin and
inventory before publishing the external plan, and again before execution.
"""
from base64 import b64encode

from ..changes.target_model import _default_scope
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ._codec import file_row, file_table
from ._coverage import inventory_roots
from ._current_evidence import current_configuration
from ._history import history_target
from ._plan_checks import check_current
from ._sources import reconstruct
from ._validation import validate_project, project_bytes
from .values import RestorePlan, guarded, require


@guarded
def captured_plan(project_root, *, source_root, source_path, source_kind,
                  source_bytes, dependencies, inventory, current, operational=None,
                  qualify=True, services=None):
    """Pure full qualification; inputs carry actual bytes, not cached verdicts."""
    model_check = (lambda files: validate_project(files, services=services)) if qualify else project_bytes
    used = {}

    def read(path):
        require(path in dependencies, 'restore_baseline_dependency_missing', path=path)
        used[path] = dependencies[path]
        return used[path]

    files, additions, rows, root, project_id = reconstruct(
        source_kind, source_bytes, read, operational=operational)
    require(used == dependencies, 'restore_dependency_inventory_mismatch')
    source_model, source_root_hash = model_check(files)
    require(source_root_hash == root, 'restore_source_root_mismatch')
    configuration = current_configuration(current, inventory['roots'])
    require(inventory['roots'] == inventory_roots(source_model.configuration, configuration),
            'restore_inventory_coverage_invalid')
    expected = [row for row in inventory['entries'] if row['kind'] == 'file']
    require(expected == [{**file_row(path, raw), 'kind': 'file'}
                         for path, raw in sorted(current.items(), key=lambda item: item[0].encode())],
            'restore_inventory_bytes_mismatch')
    require(configuration.project_id == project_id, 'restore_project_identity_conflict', exit_code=6)
    target, preserved = history_target(files, additions, current, configuration)
    target_model, target_root = model_check(target)
    backup = check_current(inventory, current, source_model, target, target_model)
    objects = {}
    for content in [source_bytes, *dependencies.values(), *target.values(), *backup.values()]:
        row = file_row('', content)
        value = {'sha256': row['sha256'], 'size': row['size'],
                 'data_base64': b64encode(content).decode('ascii')}
        require(row['sha256'] not in objects or objects[row['sha256']] == value,
                'restore_object_collision')
        objects[row['sha256']] = value
    data = {'format_version': 'restore-plan-v1', 'policy_version': 'restore-preserve-v1',
        'project_id': project_id, 'project_root': project_root,
        'source': {'kind': source_kind, 'root': source_root,
                   **file_row(source_path, source_bytes), 'dependencies': rows},
        'source_snapshot_root': root, 'source_descriptor': _default_scope(),
        'inventory': inventory, 'preserved': preserved, 'target': file_table(target),
        'expected_target_root': target_root, 'backup': file_table(backup),
        'objects': [objects[key] for key in sorted(objects)]}
    data['restore_plan_sha256'] = canonical_json_sha256(data)
    return RestorePlan(canonical_json_bytes(data))
