"""Explicit original-plan reads, external backup and native idempotency admission."""
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..changes.values import ChangePlan
from ..migration.plan_values import require
from ..migration._backup_source import _observe
from ..recovery._inventory import boundary, read_source
from .migration_commands import BOUND_PLAN

def _required(options, *names):
    require(all(name in options for name in names), 'migration_explicit_options_required', exit_code=2)


def _read(options, root_flag, path_flag):
    _required(options, root_flag, path_flag)
    origin = boundary(options[root_flag]); path = options[path_flag]
    raw = read_source(origin, path)
    def current():
        require(read_source(origin, path) == raw, 'migration_external_input_changed', exit_code=6)
    return raw, current


def _read_plan(options):
    _required(options, *BOUND_PLAN)
    raw, current = _read(options, '--plan-root', '--plan')
    data = parsed(raw)
    require(data.get('format_version') == 'migration-planning-v1' and data.get('ready') is True
            and type(data.get('change_plan')) is dict, 'migration_complete_plan_required')
    plan = ChangePlan(jcs(data['change_plan']))
    from ..changes.schema_transition_values import authoring
    authoring(plan)
    require(data.get('inputs_sha256') == plan.data['operations'][0]['inputs_sha256'],
            'migration_report_binding_invalid', exit_code=6)
    require(plan.sha256 == options['--expected-plan-sha256']
        and plan.data['operations'][0]['inputs_sha256'] == options['--expected-inputs-sha256'],
        'migration_execution_binding_changed', exit_code=6)
    if '--expected-report-sha256' in options:
        require(sha256(raw).hexdigest() == options['--expected-report-sha256'],
                'migration_report_hash_mismatch', exit_code=6)
    return data, plan, raw, current


def _backup(root, options, plan):
    from ..bundles.migration_source import prepare_source_backup
    from ..migration.backup import create_source_backup, verify_source_backup_file
    _required(options, '--backup-root', '--backup')
    source_hash = digest(plan.data['operations'][0]['source_files'])
    files, _, current = _observe(root)
    expected = prepare_source_backup(files)
    require(expected.manifest['source_files_sha256'] == source_hash, 'migration_backup_source_changed', exit_code=6)
    external = boundary(options['--backup-root'])
    try:
        raw = read_source(external, options['--backup'])
    except FileNotFoundError:
        return create_source_backup(root, output_root=options['--backup-root'], output=options['--backup'],
                                    expected_source_files_sha256=source_hash)
    require(raw == expected.source_bytes, 'migration_backup_existing_changed', exit_code=6)
    current()
    return verify_source_backup_file(root, output_root=options['--backup-root'], output=options['--backup'],
        expected_sha256=expected.sha256, expected_source_files_sha256=source_hash)


def _already_current(root, plan, target_version):
    from ..changes._lock_files import LockFiles
    from ..changes.schema_transition_recovery import historical_request
    from ..storage.operational_preflight import observe_operational_preflight
    from ..storage.project import ProjectSource
    with LockFiles(root) as access:
        require(observe_operational_preflight(access.boundary)['consistency_state'] == 'consistent',
                'migration_recovery_required', exit_code=5)
        actual = parsed(access.boundary.read_bytes('specroad.json'))
        if plan is not None:
            expected = parsed(__import__('base64').b64decode(plan.data['operations'][0]['inputs']['target_configuration']))
            require(actual.get('project_id') == expected['project_id'], 'transition_project_binding', exit_code=6)
            previous = historical_request(access, plan, actual['project_id'])
            if previous is not None: return previous
        if actual.get('schema_version') != target_version: return None
        ProjectSource(root).check_current()
        require(observe_operational_preflight(access.boundary)['consistency_state'] == 'consistent',
                'migration_recovery_required', exit_code=5)
    return {'format_version':'migration-transaction-v1','status':'not_required','exit_code':0,
        'write_state':'not_committed','no_change':True,'replayed':False,
        'current_target_verified':False,'approval_granted':False,'write_authorized':False}
