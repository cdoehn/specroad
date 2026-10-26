"""Read-only Restore observations, separate from passive byte qualification.

This adapter binds native roots and current evidence without normal import or
write preflight. It neither acquires recovery authority nor creates state.
"""
from ._codec import file_row
from ._current_evidence import BASELINES, _intact, _retained
from ._inventory import observe, read_source
from .values import RestoreError, require


def observe_configuration(bound):
    """Discover the old roots without write preflight, holding exact evidence.

    The subsequent full inventory must contain every observed evidence byte
    and the complete Baseline namespace; the passive reader repeats the proof.
    """
    try:
        raw = read_source(bound, 'specroad.json')
    except FileNotFoundError:
        raw = None
    evidence = {'specroad.json': raw}
    configuration = _intact(raw)
    if configuration is not None:
        return configuration, evidence, None
    inventory, baselines = observe(bound, [BASELINES])
    evidence.update(baselines)

    def read(path):
        content = read_source(bound, path)
        require(path not in evidence or evidence[path] == content,
                'restore_inventory_changed', path=path, exit_code=6)
        evidence[path] = content
        return content

    configuration = _retained(baselines, read)
    return configuration, evidence, inventory


def verify_live(plan, project, origin):
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
