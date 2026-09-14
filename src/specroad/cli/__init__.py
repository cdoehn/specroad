"""Shared console, module and portable-distribution entry point."""

import sys

from .application import execute
from .presentation import render
from .results import serialize_result


def main(argv: list[str] | None = None, *, stdout=None, stderr=None) -> int:
    """Emit exactly one machine document, or delegate human presentation."""
    response = execute(sys.argv[1:] if argv is None else argv)
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    try:
        output_format = response.options.get("--format", "pretty")
        if output_format in ("json", "sarif"):
            out.write(serialize_result(response.result, output_format) + "\n")
            out.flush()
        else:
            render(response.result.exit_code, out, err)
    except (OSError, UnicodeError):
        return 5
    return response.result.exit_code
