"""Structured resource failures, independent of resolver and CLI selection."""
from ..model.errors import ModelError

class ProfileError(ModelError):
    """Profile declarations or bindings do not satisfy their data contract."""
