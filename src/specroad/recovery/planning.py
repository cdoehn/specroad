"""One native read-only preparation pass; no recovery execution or publication."""
from base64 import b64encode
from pathlib import Path

from ..changes.target_model import _default_scope
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ._codec import file_row, file_table
from ._coverage import inventory_roots
from ._current_evidence import BASELINES, current_configuration
from ._inventory import boundary, observe, read_source
from ._history import history_target
from ._observations import observe_configuration, verify_live as _verify_live
from ._plan_checks import check_current
from ._sources import reconstruct
from ._validation import validate_project
from .values import RestoreError, RestorePlan, require, guarded


@guarded
def prepare_restore_plan(project_root, *, source_root, source_path, source_kind,
                         default_locale=None, generated_path=None):
    """Return exact passive plan bytes after complete supported native checks.

    Both roots and the source kind/path are explicit. The project is never
    opened through normal write preflight and no lock, journal, cache, staging
    or output is created. Only Baselines accept explicit operational config.
    Unsupported history and unavailable model specialists fail closed.
    Damaged configuration requires independent retained evidence;
    neither source files nor caller assertions can substitute for that proof.
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
    configuration, evidence, baseline_inventory = observe_configuration(project)
    roots = inventory_roots(source_model.configuration, configuration)
    inventory, current = observe(project, roots)
    require(all(current.get(path) == content for path, content in evidence.items()),
            'restore_inventory_changed', exit_code=6)
    if baseline_inventory is not None:
        entries = [row for row in inventory['entries']
                   if row['path'] == BASELINES or row['path'].startswith(BASELINES + '/')]
        # An absent descendant is implicit when an ancestor inventory root is
        # missing. A useful retained Baseline necessarily has a real namespace.
        require(entries == baseline_inventory['entries'], 'restore_inventory_changed', exit_code=6)
    require(configuration.project_id == source_model.configuration.project_id,
            'restore_project_identity_conflict', exit_code=6)
    target, preserved = history_target(files, additions, current, configuration)
    target_model, target_root = validate_project(target)
    backup = check_current(inventory, current, source_model, target, target_model)
    require(configuration.data == current_configuration(current, roots).data,
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
