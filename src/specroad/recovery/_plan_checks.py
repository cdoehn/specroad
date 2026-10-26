"""Recompute sources, target, required history and backup from owned plan bytes."""
from ..model.configuration import ProjectConfiguration
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.errors import ModelError
from ..model.paths import PathClass, classify_path, artifact_path
from ..model.record_schemas import validate_record_fields
from ..storage.json_syntax import parse_json_object
from ._codec import file_row, file_table, namespace
from ._current_evidence import current_configuration
from ._coverage import inventory_roots, OPERATIONAL_ROOTS
from ._history import preserve_history
from ._sources import reconstruct
from ._validation import validate_project
from .values import require


def assemble_target(source_files, additions):
    target = {**source_files, **{p: raw for p, (raw, _) in additions.items()}}
    preserved = [{**file_row(p, raw), 'reasons': reasons}
                 for p, (raw, reasons) in sorted(additions.items(), key=lambda item: item[0].encode('utf-8'))]
    return target, preserved


def check_history(current, target, current_configuration, target_model):
    """Require protected originals after the explicit supported history fold.

    Unsupported historical kinds and receipt history remain explicit blockers.
    Corrupt readable mutable bytes remain backup bytes, not model inputs.
    """
    for path, raw in current.items():
        if path == 'specroad.json':
            continue
        require(not any(path.startswith(root + '/') or path == root for root in OPERATIONAL_ROOTS),
                'restore_operational_history_provider_required', path=path, exit_code=6)
        old_kind = classify_path(path, current_configuration)
        new_kind = classify_path(path, target_model.configuration)
        registry_paths = {c.data.get('language_registry', {}).get('path')
                          for c in (current_configuration, target_model.configuration)}
        require(old_kind is not PathClass.UNMANAGED or new_kind is not PathClass.UNMANAGED or path in registry_paths,
                'restore_managed_content_unsupported', path=path)
        if old_kind is not PathClass.ARTIFACT and new_kind is not PathClass.ARTIFACT:
            # Unreferenced original archive bytes still cannot disappear on W.
            if old_kind is PathClass.ARCHIVE_OBJECT or new_kind is PathClass.ARCHIVE_OBJECT:
                require(target.get(path) == raw, 'restore_archive_history_provider_required', path=path, exit_code=6)
            continue
        try:
            value = parse_json_object(raw)
            kind = value.get('artifact_type')
            validate = validate_domain_fields if type(kind) is str and kind in DOMAIN_TYPES else validate_record_fields
            validate(value)
        except ModelError:
            # This is a damaged before image, not a validated historical record.
            continue
        require(artifact_path(value['artifact_type'], value['id'], current_configuration.id_prefix) == path,
                'restore_current_identity_conflict', path=path, exit_code=6)
        protected = (value['artifact_type'] in ('baseline', 'evidence', 'relation_review') or
            value['artifact_type'] == 'proposal' and value['proposal_status'] in ('rejected', 'applied', 'stale') or
            value['id_scheme'] != 'random128-v1')
        if protected:
            require(target.get(path) == raw, 'restore_protected_history_conflict', path=path, exit_code=6)
        if value['maturity'] == 'approved' or protected:
            require(path in target, 'restore_published_identity_missing', path=path, exit_code=6)
        if path in target:
            candidate = parse_json_object(target[path])
            require(candidate['revision'] >= value['revision'], 'restore_published_revision_conflict', path=path, exit_code=6)
            require(value['maturity'] != 'approved' or candidate['maturity'] == 'approved',
                    'restore_approved_state_conflict', path=path, exit_code=6)


def check_current(inventory, current, source_model, target, target_model):
    configuration = current_configuration(current, inventory['roots'])
    require(configuration.project_id == source_model.configuration.project_id == target_model.configuration.project_id,
            'restore_project_identity_conflict', exit_code=6)
    require(inventory['roots'] == inventory_roots(source_model.configuration, configuration),
            'restore_inventory_coverage_invalid')
    namespace([*target, *(row['path'] for row in inventory['entries'])])
    kinds = {row['path']: row['kind'] for row in inventory['entries']}
    for path in target:
        require(kinds.get(path) not in ('directory',), 'restore_target_directory_collision', path=path, exit_code=7)
        require(not any(kinds.get('/'.join(path.split('/')[:i])) == 'file'
                        for i in range(1, len(path.split('/')))),
                'restore_target_parent_collision', path=path, exit_code=7)
    check_history(current, target, configuration, target_model)
    return {p: raw for p, raw in current.items() if target.get(p) != raw}


def verify_contents(data, objects):
    source = data['source']
    target = {r['path']: objects[r['sha256']] for r in data['target']['entries']}
    operational = None
    if source['kind'] == 'baseline':
        require('specroad.json' in target, 'restore_target_configuration_missing')
        configuration = ProjectConfiguration(parse_json_object(target['specroad.json']))
        operational = {k: configuration.data[k] for k in ('default_locale', 'generated_path')}
    dependency_bytes = {r['path']: objects[r['sha256']] for r in source['dependencies']}

    def read(path):
        require(path in dependency_bytes, 'restore_baseline_dependency_missing', path=path)
        return dependency_bytes[path]

    files, additions, dependencies, source_root, project_id = reconstruct(source['kind'],
        objects[source['sha256']], read, operational=operational)
    require(dependencies == source['dependencies'], 'restore_dependency_inventory_mismatch')
    source_model, actual_source_root = validate_project(files)
    require(actual_source_root == source_root == data['source_snapshot_root'], 'restore_source_root_mismatch')
    require(project_id == data['project_id'], 'restore_project_identity_conflict', exit_code=6)
    current = {}
    for row in data['inventory']['entries']:
        if row['kind'] != 'file':
            continue
        # Every W-supported managed file is either retained in target or fully
        # backed up. An omitted old file cannot hide behind a metadata hash.
        require(row['sha256'] in objects, 'restore_inventory_bytes_missing', path=row['path'])
        raw = objects[row['sha256']]
        require(len(raw) == row['size'], 'restore_inventory_bytes_mismatch', path=row['path'])
        current[row['path']] = raw
    configuration = current_configuration(current, data['inventory']['roots'])
    require(configuration.project_id == source_model.configuration.project_id,
            'restore_project_identity_conflict', exit_code=6)
    additions = preserve_history(files, additions, current, configuration)
    expected_target, preserved = assemble_target(files, additions)
    require(target == expected_target, 'restore_target_inventory_mismatch')
    require(data['preserved'] == preserved, 'restore_preservation_inventory_mismatch')
    target_model, root = validate_project(target)
    require(root == data['expected_target_root'], 'restore_target_root_mismatch')
    backup = check_current(data['inventory'], current, source_model, target, target_model)
    require(data['backup'] == file_table(backup), 'restore_backup_inventory_mismatch')
