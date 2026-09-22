"""Import-free setup for tests forbidding imports and builtins.open.

This is a scoped test guard, not a general I/O or operating-system sandbox.
Resolve the module and construct replacements before entering the guard.
"""
import builtins
from contextlib import contextmanager
from unittest.mock import Mock, patch


@contextmanager
def block_imports_and_open():
    """Resolve targets and replacements before blocking imports themselves."""
    imports = Mock(side_effect=AssertionError("Unexpected import"))
    files = Mock(side_effect=AssertionError("Unexpected file access"))
    with patch.object(builtins, "open", files), patch.object(builtins, "__import__", imports):
        yield

