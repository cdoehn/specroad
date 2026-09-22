"""Stable native/legacy identities shared by collection and execution."""
import unittest


def test_identity(item):
    """Preserve existing unittest IDs; use native nodeids for new pytest tests."""
    cls = getattr(item, "cls", None)
    if isinstance(cls, type) and issubclass(cls, unittest.TestCase):
        return cls.__module__ + "." + cls.__qualname__ + "." + item.name
    return item.nodeid

