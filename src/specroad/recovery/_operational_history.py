"""Qualify retained operational receipts without treating them as model data."""
from ..bundles._receipts import completed_receipts, receipt_path
from ..model.operational_paths import passive_journal_directory
from ._codec import file_row
from .values import require


def check_operational_history(current, target, project_id):
    from ._receipt_history import receipt_history, check_receipt_targets
    merged = {**current, **target}
    receipts, journals = receipt_history(merged, project_id)
    check_receipt_targets(journals, target)
    retained = retained_operational(current, project_id)
    for path in current:
        if not path.startswith(('.specroad/transactions/', '.specroad/recovery/', '.specroad/requests/')):
            continue
        if path in retained:
            require(path not in target or target[path] == current[path],
                    'restore_receipt_history_conflict', path=path, exit_code=6)
            continue
        parts = path.split('/')
        # Independent recovery/audit histories require their own native proof.
        # Active journal bytes need no successful JSON interpretation; the
        # executor must separately authorize their complete inventory selection.
        require(len(parts) >= 3 and parts[1] in ('transactions', 'recovery')
                and parts[2] != 'archive'
                and not passive_journal_directory(parts[1], parts[2]),
                'restore_operational_history_provider_required', path=path, exit_code=6)


def operational_path(path):
    return path.startswith(('.specroad/transactions/', '.specroad/recovery/', '.specroad/requests/'))


def retained_operational(current, project_id):
    from ._receipt_history import receipt_history
    from ._restore_history import restore_audits
    receipts, _ = receipt_history(current, project_id)
    restored = restore_audits(current, project_id)
    # These namespaces are already passive in native preflight. Retention is
    # byte preservation, not a claim that an old lock/recovery/bootstrap event
    # succeeded or that its authority still applies. Consumers must recheck
    # their own original evidence before using it. Restore completions and
    # successful write receipts above have additional native proof contracts.
    passive = {}
    for path, raw in current.items():
        parts = path.split('/')
        if (len(parts) > 3 and parts[:2] == ['.specroad', 'recovery']
                and parts[2] in ('lock-audit', 'transaction-audit', 'init-bootstrap', 'bundle-bootstrap')
                and not (parts[2] == 'transaction-audit' and parts[3].startswith('restore-'))):
            passive[path] = raw
    return {**receipts, **restored, **passive}
