"""Exact selection from explicitly supplied profiles; no default composition."""
from .values import ProfileResource
from ._contract import _fail, parse_profile_key

def resolve_profile(key, resources):
    """Exact selection from explicit already parsed resources; no CLI/defaults/I/O."""
    name, version = parse_profile_key(key)
    if type(resources) not in (list, tuple) or any(type(r) is not ProfileResource for r in resources):
        _fail("profile_resources_required")
    if len({r.key for r in resources}) != len(resources):
        _fail("profile_duplicate_resource")
    for resource in resources:
        if (resource.profile_id, resource.version) == (name, version):
            return resource
    _fail("profile_not_available")
