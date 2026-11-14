"""Invocation-local reuse of pure checks over exact owned byte images.

Never cache live filesystem observations, authorizations or journal decisions.
The bounded cache disappears at the end of the outer public call. Keys retain
complete bytes: an equal hash alone cannot skip a different input's checks.
"""
from contextvars import ContextVar
from functools import wraps

_ACTIVE = ContextVar('specroad_restore_owned_checks', default=None)


def owned_checks(function):
    @wraps(function)
    def call(*args, **kwargs):
        if _ACTIVE.get() is not None:
            return function(*args, **kwargs)
        token = _ACTIVE.set({})
        try:
            return function(*args, **kwargs)
        finally:
            _ACTIVE.reset(token)
    return call


def checked_bytes(domain, key, check):
    cache = _ACTIVE.get()
    if cache is None:
        return check()
    identity = (domain, key)
    if identity not in cache:
        result = check()  # No failed or partially checked result is retained.
        if len(cache) >= 8:
            cache.pop(next(iter(cache)))
        cache[identity] = result
    return cache[identity]
