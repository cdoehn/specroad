"""Canonical model API, lazily loaded to keep project-free bootstrap isolated."""

__all__ = ["ProjectConfiguration", "PathClass", "artifact_path", "classify_path", "ModelError"]


def __getattr__(name):
    if name == "ModelError":
        from .errors import ModelError
        return ModelError
    if name in __all__:
        from . import configuration
        return getattr(configuration, name)
    raise AttributeError(name)
