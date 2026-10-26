"""Pure Restore coverage policy, shared by observation and passive plan checks."""
from ..model.operational_paths import TRANSACTIONS_ROOT, REQUESTS_ROOT, RECOVERY_ROOT
from ._codec import minimal_roots

OPERATIONAL_ROOTS = (TRANSACTIONS_ROOT, REQUESTS_ROOT, RECOVERY_ROOT)


def inventory_roots(source, current):
    return minimal_roots(['specroad.json', *source.managed_paths, *current.managed_paths, *OPERATIONAL_ROOTS])
