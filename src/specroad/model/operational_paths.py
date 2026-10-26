"""Shared recovery-critical namespaces; classification is not write permission.

Even a completed receipt is not disposable cache. Active-namespace exceptions
are exact named directories, not claims contained in unverified JSON files.
"""
TRANSACTIONS_ROOT = '.specroad/transactions'
RECOVERY_ROOT = '.specroad/recovery'
REQUESTS_ROOT = '.specroad/requests'
RECEIPTS_ROOT = TRANSACTIONS_ROOT + '/receipts'
CACHE_ROOT = '.specroad/cache'
PROTECTED_ROOTS = (TRANSACTIONS_ROOT, RECOVERY_ROOT, REQUESTS_ROOT)
EMPTY_OPERATIONAL_DIRECTORIES = frozenset(('tmp', 'merge'))
OPERATIONAL_DIRECTORIES = frozenset(('locks', 'transactions', 'recovery', 'cache', 'requests')) | EMPTY_OPERATIONAL_DIRECTORIES
PASSIVE_ROOTS = frozenset((CACHE_ROOT, REQUESTS_ROOT))
PASSIVE_JOURNAL_DIRECTORIES = frozenset((('transactions', 'receipts'),
    ('recovery', 'lock-audit'), ('recovery', 'transaction-audit'), ('recovery', 'init-bootstrap'), ('recovery', 'bundle-bootstrap'),
    ('recovery', 'archive')))


def passive_journal_directory(folder, name):
    # The caller still has to prove that the entry is an actual directory.
    return (folder, name) in PASSIVE_JOURNAL_DIRECTORIES


def _under(path, root):
    return path == root or path.startswith(root + '/')


def recovery_resource_role(path):
    """Role of an already normalized path; even unknown evidence is retained."""
    if _under(path, REQUESTS_ROOT):
        return 'request_receipt'
    if _under(path, RECEIPTS_ROOT):
        return 'transaction_receipt'
    if _under(path, RECOVERY_ROOT):
        return 'recovery_audit'
    if _under(path, TRANSACTIONS_ROOT):
        if path.endswith('/journal.json'): return 'journal'
        if '/before/' in path: return 'before_image'
        if '/staging/' in path: return 'staging'
        if '/rollback/' in path: return 'rollback_evidence'
        return 'unclassified_transaction_evidence'
    return None

