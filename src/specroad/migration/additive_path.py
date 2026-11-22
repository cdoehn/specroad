"""Compiled additive edge with an independently specified byte-preservation vector."""
from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from .contracts import DataContract, MigrationStep, Transformation, TestVector
from .plan_values import b64, unb64, require
from .additive import STEP, VERSION, source_contract, target_contract


def _source(value):
    from .current_source import inventory_bytes
    require(type(value) is dict and set(value) == {'files', 'planning'}, 'migration_native_request_required')
    files = {p: unb64(raw) for p, raw in value['files'].items()}
    inventory_bytes(files)
    return files


def _before(value):
    _source(value)
    return True


def _transform(value):
    from .planning import plan_migration
    from .transaction_target import materialized_files
    files = _source(value)
    require(value['planning'].get('target_version') == VERSION, 'migration_target_version_mismatch')
    report = plan_migration(files, **value['planning'])
    require(report.ready, 'migration_plan_incomplete')
    return {'files': {p: b64(raw) for p, raw in materialized_files(report.change_plan, files).items()}}


def _after(before, after):
    return after == _transform(before)


def _vector():
    from .builtin_path import _vector as reference_vector
    # The independently authored reference target becomes the old-format source.
    # No migration transformation is invoked to manufacture the expected target.
    vector = reference_vector()
    source = vector.after['files']
    configuration = parsed(unb64(source['specroad.json']))
    target = b64(jcs({**configuration, 'schema_version': VERSION}) + b'\n')
    fields = {**vector.before['planning'], 'target_version': VERSION,
              'inputs': {'format_version': 'migration-inputs-v1', 'target_configuration': target,
                'target_resources': [], 'requirement_mappings': [], 'proposal_mappings': []}}
    return TestVector('preserve-every-source-byte', {'files': source, 'planning': fields},
                      {'files': {**source, 'specroad.json': target}})


def registered_step():
    return MigrationStep(STEP, DataContract(**source_contract()), DataContract(**target_contract()),
        Transformation(_before, _transform, _after, (_vector(),), True), False)
