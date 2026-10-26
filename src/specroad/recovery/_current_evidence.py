"""Independently retained current configuration evidence, never source fill.

An intact configuration is authoritative for its own declarations. Otherwise
only native, byte-verified retained project Baselines supply identity/coverage.
The archive verifier's inert operational projection is used for classification
only; none of those placeholder values enters the restore target.
"""
from ..archive.verification import _configuration
from ..changes.target_model import _default_scope
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..model.record_schemas import validate_record_fields
from ..storage.json_syntax import parse_json_object
from ._inventory import observe, read_source
from ._sources import baseline_objects
from .values import require

BASELINES = 'spec/baselines'


def _intact(raw):
    if raw is None:
        return None
    try:
        return ProjectConfiguration(parse_json_object(raw))
    except ModelError as error:
        # Invalid model bytes can be recovered; a security declaration cannot
        # be concealed by falling back to another piece of evidence.
        if error.reason in ('unsafe_path', 'reserved_path', 'unsafe_project_declaration'):
            raise
        return None


def _retained(baselines, read):
    configurations = []
    for path, raw in sorted(baselines.items()):
        try:
            record = parse_json_object(raw)
            validate_record_fields(record, expected_type='baseline')
        except ModelError:
            continue  # Damaged bytes are not independent semantic evidence.
        if record['baseline_state'] != 'sealed' or record['scope_descriptor'] != _default_scope():
            continue
        objects = baseline_objects(raw, read)
        semantic = next(row for row in record['manifest'] if row['role'] == 'semantic_configuration')
        configuration = _configuration(parse_json_object(objects[semantic['object_path']]))
        require(path == artifact_path('baseline', record['id'], configuration.id_prefix),
                'restore_current_identity_conflict', path=path, exit_code=6)
        configurations.append(configuration)
    require(configurations, 'restore_current_configuration_evidence_required')
    chosen = configurations[0]
    require(all((c.project_id, c.id_prefix) == (chosen.project_id, chosen.id_prefix)
                for c in configurations), 'restore_project_identity_conflict', exit_code=6)
    # No timestamps or list order choose a purported latest configuration.
    # Differing declarations require a stronger history/recovery provider.
    def declarations(c):
        return canonical_json_bytes({'managed_paths': sorted(c.managed_paths),
            'language_registry': c.data.get('language_registry')})
    require(all(declarations(c) == declarations(chosen) for c in configurations),
            'restore_current_coverage_evidence_conflict')
    return chosen


def _baseline_files(files):
    return {p: raw for p, raw in files.items() if p.startswith(BASELINES + '/')}


def current_configuration(files, roots):
    """Recompute solely from bound current bytes, not target/source objects."""
    configuration = _intact(files.get('specroad.json'))
    if configuration is not None:
        return configuration
    require(any(BASELINES == p or BASELINES.startswith(p + '/') for p in roots),
            'restore_current_evidence_coverage_incomplete')

    def read(path):
        require(path in files, 'restore_current_evidence_object_missing', path=path)
        return files[path]

    return _retained(_baseline_files(files), read)


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
