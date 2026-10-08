"""Test-only observation and process interruption after real native calls.

No production import, configuration or environment switch installs these hooks.
Scenario owners explicitly enter the probe in their isolated test processes.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
from unittest.mock import patch

CRASH_EXIT = 23


class WriterBoundaryProbe:
    """Observe successful native calls, or stop after one phase-local call.

    Paths are descriptor-resolved before a move/removal and reported relative
    to this owned root. Each syscall retains its real return value and effects.
    """
    def __init__(self, root, phase='', ordinal=-1):
        self.root, self.selected_phase, self.ordinal = root, phase, ordinal
        self.phase = None
        self.events = []
        self.counts = {}

    def path(self, name, directory=None):
        if not isinstance(name, int) and re.fullmatch(r'/proc/self/fd/[0-9]+', os.fsdecode(name)):
            name = int(os.fsdecode(name).rsplit('/', 1)[-1])
        if isinstance(name, int):
            value = Path(os.readlink('/proc/self/fd/' + str(name)))
        else:
            parent = Path.cwd() if directory is None else Path(
                os.readlink('/proc/self/fd/' + str(directory)))
            value = parent / os.fsdecode(name)
        relative = value.relative_to(self.root).as_posix()
        # Recovery uses real anonymous inodes and fresh audit identities. Keep
        # their path roles stable across independent processes, not their IDs.
        relative = re.sub(r'#[0-9]+ \(deleted\)$', '<anonymous>', relative)
        relative = re.sub(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', '<uuid>', relative)
        return re.sub(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])', '<sha256>', relative)

    def boundary(self, operation, paths):
        index = self.counts.get(self.phase, 0)
        self.counts[self.phase] = index + 1
        event = dict(phase=self.phase, ordinal=index, operation=operation, paths=paths)
        self.events.append(event)
        if self.phase == self.selected_phase and index == self.ordinal:
            print(json.dumps({'pid': os.getpid(), 'cut': event}), flush=True)
            os._exit(CRASH_EXIT)

    def __enter__(self):
        self.stack = ExitStack()
        for name in ('fsync', 'mkdir', 'replace', 'rename', 'link', 'unlink', 'rmdir'):
            native = getattr(os, name)

            def call(*args, _name=name, _native=native, **kwargs):
                if _name in ('replace', 'rename', 'link'):
                    paths = [self.path(args[0], kwargs.get('src_dir_fd')),
                             self.path(args[1], kwargs.get('dst_dir_fd'))]
                else:
                    paths = [self.path(args[0], kwargs.get('dir_fd'))]
                result = _native(*args, **kwargs)
                self.boundary(_name, paths)
                return result

            self.stack.enter_context(patch.object(os, name, side_effect=call))
        return self

    def __exit__(self, *exception):
        return self.stack.__exit__(*exception)
