"""Observe foreign execution attempts without replacing native Proposal checks."""
from contextlib import contextmanager, ExitStack
import os
import socket
import subprocess
from unittest.mock import patch


@contextmanager
def no_foreign_execution():
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError('Proposal operation attempted foreign execution')

    with ExitStack() as stack:
        stack.enter_context(patch.object(subprocess, 'Popen', forbidden))
        stack.enter_context(patch.object(os, 'system', forbidden))
        stack.enter_context(patch.object(socket, 'socket', forbidden))
        yield calls
    assert not calls, 'A foreign execution attempt was caught and hidden'
