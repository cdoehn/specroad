"""Stable read-only API for product configuration values."""
from .models import EffectiveConfiguration


def resolve_configuration(records, configuration_id):
    """Materialize every declared root dimension using selection, then default.

Only explicitly selected IDs are resolved. No implicit configuration, file
access, parent fallback, applicability decision or project completeness claim.
    """
    return EffectiveConfiguration(records, configuration_id)
