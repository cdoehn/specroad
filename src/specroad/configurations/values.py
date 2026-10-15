"""Stable read-only API for product configuration values."""
from .models import EffectiveConfiguration


def resolve_configuration(records, configuration_id):
    """Resolve the selected parent chain, then fill remaining declared defaults.

Only explicitly selected IDs are resolved. No implicit configuration, file
access, missing-parent fallback, applicability decision or project completeness claim.
    """
    return EffectiveConfiguration(records, configuration_id)
