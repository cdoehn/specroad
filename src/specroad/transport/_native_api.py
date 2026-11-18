"""Shared public-API invocation; direction-specific protocols remain separate."""
from .snapshots import TransportFailure, api_failure


def _api_call(api, call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except TransportFailure:
        raise
    except (api.PatchHarborError, OSError, TypeError, ValueError) as error:
        raise api_failure(api, error) from error
