"""Owned project inputs and write-attempt traps; no UI or documentation oracle."""
import builtins
from contextlib import contextmanager, ExitStack
import io
import os
from pathlib import Path
import stat
from unittest.mock import patch

from specroad.model.paths import artifact_path
from specroad.profiles.values import ProfileResource
from specroad.lint import LiteralPolicy
from .artifacts import artifact_bytes
from .model import configuration_file, put
from .model_validation import artifact
from .profiles import profile_data


def make_project(root, *values, **config):
    configuration_file(root, **config)
    for value in values:
        put(root, artifact_path(value["artifact_type"], value["id"], "SR"), artifact_bytes(value))
    return root


def profile_resources(**changes):
    return (ProfileResource(artifact_bytes(profile_data(profile_id="core", **changes))),)


def literal_policy(**changes):
    data = {"format_version": 1, "policy_id": "test-literal", "version": "1.0.0",
            "language": "en", "fields": ["/statement"], "term_ids": [],
            "placeholders": [], "references": []}
    data.update(changes)
    return LiteralPolicy.from_value(data)


def inventory(root):
    paths = [root, *sorted(root.rglob("*"))]
    return tuple((str(p.relative_to(root)), stat.S_IMODE(p.lstat().st_mode),
                  p.read_bytes() if p.is_file() and not p.is_symlink() else None,
                  os.readlink(p) if p.is_symlink() else None) for p in paths)


@contextmanager
def no_write_attempts():
    """Fail on writes even if the test runner has permission to bypass chmod."""
    calls = []
    open_builtin, open_io, open_os = builtins.open, io.open, os.open
    def forbid(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Unexpected write or process/network operation")
    def checked(original):
        def opening(file, mode="r", *args, **kwargs):
            if any(c in mode for c in "wax+"):
                return forbid(file, mode)
            return original(file, mode, *args, **kwargs)
        return opening
    def os_open(file, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            return forbid(file, flags)
        return open_os(file, flags, *args, **kwargs)
    with ExitStack() as stack:
        stack.enter_context(patch.object(builtins, "open", checked(open_builtin)))
        stack.enter_context(patch.object(io, "open", checked(open_io)))
        stack.enter_context(patch.object(os, "open", os_open))
        for name in ("mkdir", "makedirs", "unlink", "remove", "rename", "replace", "rmdir", "chmod", "truncate", "utime", "symlink", "link", "system"):
            stack.enter_context(patch.object(os, name, forbid))
        import subprocess, socket
        stack.enter_context(patch.object(subprocess, "Popen", forbid))
        stack.enter_context(patch.object(socket, "socket", forbid))
        yield calls
    if calls:
        raise AssertionError("A blocked write was attempted and swallowed")
