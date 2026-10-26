"""One native read-only preparation pass; no recovery execution or publication."""
from base64 import b64encode
from pathlib import Path

from ..changes.target_model import _default_scope
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..storage.json_syntax import parse_json_object
from ._codec import file_row, file_table
from ._inventory import boundary, observe, read_source, inventory_roots
from ._plan_checks import assemble_target, check_current
from ._sources import reconstruct
from ._validation import validate_project
from .values import RestoreError, RestorePlan, require, guarded


def _current_configuration(bound):
    try:
        return ProjectConfiguration(parse_json_object(read_source(bound, 'specroad.json')))
    except (RestoreError, FileNotFoundError):
        raise
    except Exception as error:
        from ..model.errors import ModelError
        if not isinstance(error, ModelError):
            raise
        raise RestoreError('restore_current_configuration_evidence_required') from error


@guarded
def prepare_restore_plan(project_root, *, source_root, source_path, source_kind,
                         default_locale=None, generated_path=None):
    """Return exact passive plan bytes after complete supported native checks.

    Both roots and the source kind/path are explicit. The project is never
    opened through normal write preflight and no lock, journal, cache, staging
    or output is created. Only Baselines accept explicit operational config.
    The W history provider refuses additional history requiring 15.k, damaged
    configuration without an independent evidence adapter, and unavailable
    model specialists. These are failures, not qualified partial plans.
    """
    require(isinstance(project_root, (str, Path)) and isinstance(source_root, (str, Path)),
            'restore_roots_required', exit_code=2)
    require(source_kind in ('baseline', 'project_bundle') and type(source_path) is str and source_path,
            'restore_explicit_source_required', exit_code=2)
    project, origin = boundary(project_root), boundary(source_root)
    raw = read_source(origin, source_path)
    operational = None
    if source_kind == 'baseline' or default_locale is not None or generated_path is not None:
        operational = {'default_locale': default_locale, 'generated_path': generated_path}
    owned = {}

    def read(path):
        content = read_source(origin, path)
        require(path not in owned or owned[path] == content, 'restore_source_changed', path=path, exit_code=6)
        owned[path] = content
        return content

    files, additions, dependencies, source_model_root, project_id = reconstruct(
        source_kind, raw, read, operational=operational)
    source_model, actual_source_root = validate_project(files)
    require(source_model_root == actual_source_root, 'restore_source_root_mismatch')
    target, preserved = assemble_target(files, additions)
    target_model, target_root = validate_project(target)
    configuration = _current_configuration(project)
    roots = inventory_roots(source_model.configuration, configuration)
    inventory, current = observe(project, roots)
    backup = check_current(inventory, current, source_model, target, target_model)
    require(configuration.data == ProjectConfiguration(parse_json_object(current['specroad.json'])).data,
            'restore_inventory_changed', exit_code=6)
    objects = {}
    for content in [raw, *owned.values(), *target.values(), *backup.values()]:
        row = file_row('', content)
        token = row['sha256']
        require(token not in objects or objects[token]['data_base64'] == b64encode(content).decode('ascii'),
                'restore_object_collision')
        objects[token] = {'sha256': token, 'size': len(content), 'data_base64': b64encode(content).decode('ascii')}
    data = {'format_version': 'restore-plan-v1', 'policy_version': 'restore-preserve-v1',
        'project_id': project_id, 'project_root': str(project.root),
        'source': {'kind': source_kind, 'root': str(origin.root), **file_row(source_path, raw),
                   'dependencies': dependencies},
        'source_snapshot_root': source_model_root, 'source_descriptor': _default_scope(),
        'inventory': inventory, 'preserved': preserved, 'target': file_table(target),
        'expected_target_root': target_root, 'backup': file_table(backup),
        'objects': [objects[token] for token in sorted(objects)]}
    data['restore_plan_sha256'] = canonical_json_sha256(data)
    plan = RestorePlan(canonical_json_bytes(data))
    _verify_live(plan, project, origin)
    return plan


def _verify_live(plan, project, origin):
    data = plan.data
    source = data['source']
    require(str(project.root) == data['project_root'] and str(origin.root) == source['root'],
            'restore_root_binding_changed', exit_code=6)
    try:
        for row in [source, *source['dependencies']]:
            raw = read_source(origin, row['path'])
            require(file_row(row['path'], raw) == {k: row[k] for k in ('path', 'size', 'sha256')},
                    'restore_source_changed', path=row['path'], exit_code=6)
        inventory, _ = observe(project, data['inventory']['roots'])
        require(inventory == data['inventory'], 'restore_inventory_changed', exit_code=6)
    except FileNotFoundError as error:
        raise RestoreError('restore_input_disappeared', exit_code=6) from error
    project._check_root(); origin._check_root()


@guarded
def verify_restore_plan(raw):
    """Recompute embedded contracts and reread the bound native origin/inventory.

    Read-only preflight, not a lock-held execution check or write capability.
    The later recovery executor must repeat it under its own specialized lock.
    """
    plan = RestorePlan(raw)
    data = plan.data
    try:
        project, origin = boundary(data['project_root']), boundary(data['source']['root'])
    except FileNotFoundError as error:
        raise RestoreError('restore_input_disappeared', exit_code=6) from error
    _verify_live(plan, project, origin)
    return plan
