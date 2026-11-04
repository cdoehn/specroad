"""One public adapter over native migration planning, backup, writer and verify."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..bundles.errors import BundleError
from ..changes.values import ChangePlan
from ..changes.publication_values import PublicationAuthority
from ..changes.schema_transition_values import SchemaTransitionError
from ..migration.contracts import MigrationError
from ..migration.plan_values import require
from ..migration.planning import plan_migration
from ..migration.builtin_path import require_path
from ..migration._backup_source import _observe
from ..recovery._inventory import boundary, read_source
from .migration_commands import PLANNING
from .migration_inputs import _required, _read, _read_plan, _backup, _already_current
from .migration_result import document
from .results import CommandResult, FailureKind, OperationFailure
from .result_schemas import validate_result_document






def _planning(options):
    _required(options, *(key for key in PLANNING if key != '--request-id'))
    raw, current = _read(options, '--inputs-root', '--inputs')
    value = {'inputs': parsed(raw), 'actor': {'actor_type': options['--actor-type'],
        'actor_id': options['--actor-id']}, 'planned_at': options['--planned-at'],
        'change_plan_id': options['--plan-id'], 'request_id': options.get('--request-id'),
        'target_version': options.get('--to', '0.2.0')}
    return value, current




def _publish_report(root, data, options, current):
    from ..bundles.publication import _publish
    _required(options, '--output-root', '--output')
    raw = jcs(data)
    container = SimpleNamespace(source_bytes=raw, sha256=sha256(raw).hexdigest(), manifest={})
    result = _publish(container, SimpleNamespace(boundary=boundary(str(root))), current,
                      options['--output'], options['--output-root'])
    result['file']['path'] = str(Path(options['--output-root']) / result['file']['path'])
    return result['file']


def _plan(invocation, root, options):
    planning, input_current = _planning(options)
    files, source, current = _observe(root)
    def unchanged():
        input_current(); current()
    if _work_requested(options):
        from .migration_work import start_planning
        return start_planning(invocation, root, options, files, planning, unchanged)
    report = plan_migration(files, **planning)
    unchanged()
    publication = _publish_report(root, report.data, options, unchanged)
    return document('plan', planning=report.data, plan_file=publication)


def _work_requested(options):
    return ('--work-dir' in options or any(key in options for key in
        ('--step-cpu-ms', '--step-wall-ms', '--cpu-budget-ms', '--wall-budget-ms'))
        or options.get('--resource-profile') == 'constrained')






def _apply(invocation, root, options):
    from ..migration.transaction import apply_migration_plan
    _required(options, '--to')
    require(type(invocation.publication_authority) is PublicationAuthority,
            'migration_authority_required', exit_code=2)
    require(not ('--plan' in options and '--work-dir' in options), 'migration_input_modes_conflict', exit_code=2)
    report = plan = None
    current = lambda: None
    if '--plan' in options:
        require(not set(PLANNING).intersection(options), 'migration_input_modes_conflict', exit_code=2)
        report, plan, _, current = _read_plan(options)
    elif '--work-dir' in options:
        require(not set(PLANNING).intersection(options), 'migration_input_modes_conflict', exit_code=2)
        from .migration_work import completed_plan
        report, plan, current = completed_plan(invocation, options)
    prior = _already_current(root, plan, options['--to'])
    if prior is not None:
        current()
        return document('apply', planning=report, execution=prior, backup=prior.get('backup'))
    _required(options, '--transaction-id', '--backup-root', '--backup')
    if plan is None:
        planning, current = _planning(options)
        source, _, fresh = _observe(root)
        planned = plan_migration(source, **planning)
        require(planned.ready, 'migration_plan_incomplete')
        report, plan = planned.data, planned.change_plan
        fresh(); current()
    source, _, fresh = _observe(root)
    value = plan.data
    rebuilt = plan_migration(source, inputs=value['operations'][0]['inputs'],
        **{key: value[key] for key in ('actor','planned_at','change_plan_id','request_id')},
        target_version=options['--to'])
    require(rebuilt.ready and rebuilt.data == report, 'migration_report_recomputation_mismatch', exit_code=6)
    fresh(); current()
    backup = _backup(root, options, plan)
    current()
    outcome = apply_migration_plan(root, plan.source_bytes, expected_plan_sha256=plan.sha256,
        expected_inputs_sha256=report['inputs_sha256'], expected_target_version=options['--to'],
        transaction_id=options['--transaction-id'], backup_path=backup['file']['path'],
        backup_root=options['--backup-root'], backup_sha256=backup['file']['sha256'],
        backup_size=backup['file']['size'], backup_source_files_sha256=backup['source_files_sha256'],
        authority=invocation.publication_authority, gates=invocation.migration_gates)
    return document('apply', planning=report, execution=outcome, backup=backup)


def _verify(invocation, root, options):
    from ..migration.verification import verify_migration_project
    _required(options, '--transaction-id', '--expected-report-sha256', '--expected-backup-sha256')
    report, plan, report_raw, current = _read_plan(options)
    raw, backup_current = _read(options, '--backup-root', '--backup')
    bindings = {'expected_backup_sha256': options['--expected-backup-sha256'],
        'expected_source_files_sha256': digest(plan.data['operations'][0]['source_files']),
        'expected_plan_sha256': plan.sha256, 'expected_inputs_sha256': report['inputs_sha256'],
        'expected_report_sha256': options['--expected-report-sha256'], 'expected_target_version': options.get('--to','0.2.0')}
    result = verify_migration_project(root, raw, plan.source_bytes, report_raw,
        transaction_id=options['--transaction-id'], gates=invocation.migration_gates, **bindings)
    current(); backup_current()
    if _work_requested(options):
        from .migration_work import start_verification
        return start_verification(invocation, root, options, raw, plan, report_raw, result, bindings)
    return document('verify', planning=report, verification=result.data)


def migration_command(invocation):
    try:
        options = dict(invocation.options)
        require_path(options.get('--to', '0.2.0'))
        root = invocation.resolved.project_root
        _required(options, '--project')
        require(str(root) == options['--project'], 'migration_canonical_root_required', exit_code=7)
        mode = invocation.command.command_id.split('.')[1]
        result = {'plan': _plan, 'apply': _apply, 'verify': _verify}[mode](invocation, root, options)
        if type(result) is CommandResult: return result
        validate_result_document('migration-command-v1', result)
        return CommandResult(invocation.command.command_id, result=result)
    except (ModelError, BundleError, MigrationError, SchemaTransitionError, SafetyViolation, OSError) as error:
        code = 7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError) else getattr(error,'exit_code',3)
        reason = getattr(error,'reason','migration_io_failure')
        facts = {'reason': reason}
        if hasattr(error,'write_state'): facts['write_state'] = error.write_state
        raise OperationFailure(FailureKind(code), reason, details=facts) from error
