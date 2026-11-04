"""Fixed reference-source path; no project-installed provider or historical guess."""
from importlib import resources
from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from .contracts import DataContract, MigrationStep, Transformation, TestVector
from .plan_values import STEP, SOURCE_CONTRACT, b64, unb64, require
from .plan_inputs import target_contract


def _source(value):
    require(type(value) is dict and set(value) == {'files', 'planning'},
            'migration_native_request_required')
    files = {p: unb64(raw) for p, raw in value['files'].items()}
    from .reference01 import inventory_bytes
    inventory_bytes({p: raw for p, raw in files.items() if not p.startswith('.specroad/')})
    return files


def _before(value):
    _source(value)
    return True


def _transform(value):
    from .planning import plan_migration
    from .transaction_target import materialized_files
    files = _source(value)
    report = plan_migration(files, **value['planning'])
    require(report.ready, 'migration_plan_incomplete')
    return {'files': {p: b64(raw) for p, raw in materialized_files(report.change_plan, files).items()}}


def _after(before, after):
    # Recompute the same full native plan and byte equality. No schema-only flag.
    from .legacy_manifest import validate_legacy_manifest
    files = {p: unb64(raw) for p, raw in after['files'].items()}
    validate_legacy_manifest(files, project_id=parsed(files['specroad.json'])['project_id'])
    return after == _transform(before)


def _vector():
    # Literal independently authored source/target bytes. Only the current
    # distribution's resource bytes and contract binding are late-bound.
    value = parsed(resources.files('specroad.reference01_data').joinpath('migration-vector.json').read_bytes())
    core = resources.files('specroad.profile_data').joinpath('core.json').read_bytes()
    inputs = {'format_version': 'migration-inputs-v1',
        'target_configuration': value['target_configuration'],
        'target_resources': [{'path': 'profiles/core.json', 'bytes_base64': b64(core)}],
        'requirement_mappings': [], 'proposal_mappings': []}
    expected = value['expected_files']
    expected['profiles/core.json'] = b64(core)
    manifest = value['expected_legacy_manifest']
    manifest['target'].update(target_contract())
    expected['mappings/legacy-manifest.json'] = b64(jcs(manifest) + b'\n')
    return TestVector('synthetic-full-project',
        {'files': value['source_files'], 'planning': {**value['planning'], 'inputs': inputs}},
        {'files': expected})


def registered_step():
    return MigrationStep(STEP, DataContract(**SOURCE_CONTRACT), DataContract(**target_contract()),
        Transformation(_before, _transform, _after, (_vector(),), True), False)


def require_path(target_version):
    from .registry import builtin_registry
    graph = builtin_registry()
    source = DataContract(**SOURCE_CONTRACT)
    target = DataContract(target_version, target_contract()['contract_sha256'])
    edges = graph.resolve(source, target)
    require(len(edges) == 1 and edges[0].step.step_id == STEP and not edges[0].reverse,
            'migration_supported_path_required')
    return edges
