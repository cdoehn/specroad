"""Compatibility facade for passive profile resources and field-only checks.

Validation, immutable values, exact selection and field observation have their
own modules. No CLI/default selection, composition or write authority is added.
"""
from .errors import ProfileError
from .values import ProfileResource
from .resolver import resolve_profile
from .fields import check_profile_fields
from ._contract import parse_profile_key

__all__ = ("ProfileResource", "ProfileError", "resolve_profile", "check_profile_fields",
           "parse_profile_key")
