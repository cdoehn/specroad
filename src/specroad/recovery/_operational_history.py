"""Qualify retained operational receipts without treating them as model data."""
from ..bundles._receipts import completed_receipts, receipt_path
from ..model.operational_paths import passive_journal_directory
from ._codec import file_row
from .values import require


def check_operational_history(current, target, project_id):
    receipts = {p: b for p, b in current.items() if receipt_path(p)}
    journals = completed_receipts(receipts, project_id)
    for journal in journals:
        # An old receipt proves its original result, not an arbitrary revision
        # selected by this restore. Unknown publication history stays blocked.
        for row in journal.data['target_inventory']:
            path = row['path']
            require(path in target and file_row(path, target[path]) == row,
                    'restore_receipt_history_conflict', path=path, exit_code=6)
    for path in current:
        if not path.startswith(('.specroad/transactions/', '.specroad/recovery/', '.specroad/requests/')):
            continue
        if receipt_path(path):
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
