"""Read current per-process limits without changing them or probing a project.

resource.getrlimit/RLIM_INFINITY follow the CPython standard-library contract.
These observations are not host/cgroup capacity, available RAM, an enforced
SpecRoad budget, or a guarantee that an allocation or later operation succeeds.
"""


def _resource_api():
    try:
        import resource
    except ImportError:
        return None
    return resource


def _bound(value, infinity):
    if type(value) is not int:
        return {"state": "unknown", "value": None}
    if value == infinity:
        return {"state": "unlimited", "value": None}
    if value >= 0:
        return {"state": "known", "value": value}
    return {"state": "unknown", "value": None}


def _process_limit(api, name, unit):
    unknown = {"scope": "process", "unit": unit, "source": "unavailable",
               "soft": {"state": "unknown", "value": None},
               "hard": {"state": "unknown", "value": None}}
    if api is None:
        return unknown
    try:
        soft, hard = api.getrlimit(getattr(api, name))
        infinity = api.RLIM_INFINITY
    except (AttributeError, ImportError, OSError, ValueError, TypeError, OverflowError):
        return unknown
    if type(infinity) is not int:
        return unknown
    soft_bound, hard_bound = _bound(soft, infinity), _bound(hard, infinity)
    if (soft_bound["state"] == "unknown" or hard_bound["state"] == "unknown"
            or (hard_bound["state"] == "known" and (soft_bound["state"] == "unlimited"
                or soft_bound["value"] > hard_bound["value"]))):
        return unknown
    return {"scope": "process", "unit": unit, "source": "getrlimit",
            "soft": soft_bound, "hard": hard_bound}


def current_limits():
    """Fresh observation each call. Never use setrlimit or read cgroup files."""
    api = _resource_api()
    return {"process_address_space_bytes": _process_limit(api, "RLIMIT_AS", "bytes"),
            "process_cpu_seconds": _process_limit(api, "RLIMIT_CPU", "seconds"),
            "host_memory_bytes": None, "host_cpu_quota": None,
            "host_limits_status": "unknown", "scope": "process_limits_not_host_capacity"}
