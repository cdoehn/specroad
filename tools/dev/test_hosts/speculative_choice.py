"""Deterministic copy reservation; forecasts deliberately do not enter this rule."""


def choose(host, eligible, attempts, *, waiting=False, identities=None):
    """Rows include in-flight reservations, so simultaneous free slots cannot race."""
    if waiting or host not in eligible:
        return None
    groups = {}
    for row in attempts:
        groups.setdefault(row['nodeid'], []).append(row['host'])
    candidates = [(len(hosts), (identities or {}).get(node, node), node) for node, hosts in groups.items()
                  if host not in hosts or set(eligible) <= set(hosts)]
    return min(candidates)[2] if candidates else None
