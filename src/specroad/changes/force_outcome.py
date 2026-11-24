"""Detached Force result contracts; no filesystem effects or authority."""
from ..force import operations_hash


def _outcome(plan, report, force, *, dry_run=False, completion=None, replayed=False):
    data = plan.data
    state = 'not_committed' if completion is None else 'committed'
    return {'format_version': 'force-authoring-execution-v1', 'command_id': 'change.apply',
        'status': 'forced' if force['used'] else 'success', 'exit_code': 0,
        'dry_run': dry_run, 'write_state': state, 'replayed': replayed, 'complete': True,
        'plan_sha256': plan.sha256, 'operations_sha256': operations_hash(data),
        'target_model_root_sha256': report['model_root_sha256'], 'validation_status': report['validation_status'],
        'force': force, 'report': report, 'diagnostics': report['diagnostics'],
        'completion': None if completion is None else completion.data, 'approval_granted': False,
        'audit': {'format_version': 'force-authoring-audit-v1', 'plan': data,
            'force': force, 'operations_sha256': operations_hash(data), 'write_state': state,
            'dry_run': dry_run, 'replayed': replayed, 'validation_status': report['validation_status'],
            'target_inventory': report['inventory'], 'approval_granted': False}}
