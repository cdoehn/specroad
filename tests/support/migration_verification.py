"""Synthetic source data, real native backup/plan/writer and observed files."""
from hashlib import sha256
from pathlib import Path

from specroad.migration.planning import plan_migration
from specroad.migration.transaction_target import materialized_files
from .migration_transaction import setup


def case(tmp_path, **options):
    root, source, plan, execution = setup(tmp_path, **options)
    value = plan.data; op = value['operations'][0]
    report = plan_migration(source, inputs=op['inputs'], **{name: value[name] for name in
        ('actor', 'planned_at', 'change_plan_id', 'request_id')}, target_version='0.2.0')
    backup = Path(execution['backup_path']).read_bytes()
    bindings = {name: execution[name] for name in
        ('expected_plan_sha256', 'expected_inputs_sha256', 'expected_target_version')}
    bindings.update(expected_backup_sha256=execution['backup_sha256'],
        expected_source_files_sha256=execution['backup_source_files_sha256'],
        expected_report_sha256=sha256(report.canonical_bytes).hexdigest())
    return root, source, plan, execution, backup, report, materialized_files(plan, source), bindings


def verify(data, *, gates=()):
    from specroad.migration.verification import verify_migration
    _, _, plan, _, backup, report, target, bindings = data
    return verify_migration(backup, plan.source_bytes, report.canonical_bytes, target, gates=gates, **bindings)
