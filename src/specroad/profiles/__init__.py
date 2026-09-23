"""Declarative profile resources; no automatic project/CLI selection or writes."""
from .core import ProfileResource, ProfileError, resolve_profile, check_profile_fields

__all__ = ("ProfileResource", "ProfileError", "resolve_profile", "check_profile_fields")

from .composition import (EffectiveProfile, ProfileCompositionError, compose_profiles, check_composed_fields)

__all__ += ("EffectiveProfile", "ProfileCompositionError", "compose_profiles", "check_composed_fields")
