"""Public facade for owned import values and passive native-owner lookup.

History construction and identity lookup retain independent implementations.
Neither service selects conflict policies or authorizes project publication.
"""
from ._identity_errors import ImportIdentityError
from ._import_identity import ExternalIdentity
from ._native_identity_index import NativeIdentityIndex

__all__ = ["ExternalIdentity", "ImportIdentityError", "NativeIdentityIndex"]
