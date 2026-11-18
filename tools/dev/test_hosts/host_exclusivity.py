"""Pure per-test host ownership and native lease interval invariants."""


def host_available(host, index, current, reserved, active_nodes, *, exclude=None):
    """Reservations and unfinished attempts own the host until acknowledged."""
    for name, row in current.items():
        if name != exclude and row['host'] == host and row['index'] == index:
            return False
    for name, row in reserved.items():
        if name == exclude or ('node' in row and row['node'] not in active_nodes):
            continue
        target = row.get('host', row.get('target'))
        item = row.get('index', row.get('source', {}).get('index'))
        if target == host and item == index:
            return False
    return True



def verify_host_test_intervals(host_tests):
    """Input intervals have already passed the strict native lease validator."""
    for intervals in host_tests.values():
        ordered = sorted(intervals)
        if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Same test overlaps on one host')
