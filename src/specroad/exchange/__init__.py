"""Passive import identities and comparisons; parsing and writes are separate."""
from .identities import ExternalIdentity, ImportIdentityError, NativeIdentityIndex
from .comparison import ImportComparison

__all__ = ["ExternalIdentity", "ImportIdentityError", "NativeIdentityIndex", "ImportComparison"]
