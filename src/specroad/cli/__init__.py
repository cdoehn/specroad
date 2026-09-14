"""Shared console, module and portable-distribution entry point."""

import sys

from .application import dispatch
from .presentation import render


def main(argv: list[str] | None = None, *, stdout=None, stderr=None) -> int:
    """Adapt process arguments and streams to the application dispatcher."""
    status = dispatch(sys.argv[1:] if argv is None else argv)
    render(status, sys.stdout if stdout is None else stdout,
           sys.stderr if stderr is None else stderr)
    return status
