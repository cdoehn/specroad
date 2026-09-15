"""Restore and report leaked process state; never serialize environment values."""

import os
import random
import sys


def _environment():
    return {key: value for key, value in os.environ.items()
            if key != "PYTEST_CURRENT_TEST"}


class ProcessState:
    """A worker executes tests sequentially, but its process survives each test."""

    def __init__(self):
        self.cwd = os.getcwd()
        self.environment = _environment()
        self.path = list(sys.path)
        self.random = random.getstate()

    def restore(self):
        changed = []
        try:
            current_cwd = os.getcwd()
        except FileNotFoundError:
            current_cwd = None
        if current_cwd != self.cwd:
            changed.append("cwd")
            os.chdir(self.cwd)
        if _environment() != self.environment:
            changed.append("environment")
            current_test = os.environ.get("PYTEST_CURRENT_TEST")
            os.environ.clear()
            os.environ.update(self.environment)
            if current_test is not None:
                os.environ["PYTEST_CURRENT_TEST"] = current_test
        if sys.path != self.path:
            changed.append("sys.path")
            sys.path[:] = self.path
        if random.getstate() != self.random:
            changed.append("random")
            random.setstate(self.random)
        return tuple(changed)
