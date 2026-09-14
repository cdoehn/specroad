"""Early bootstrap CLI. Unimplemented commands are deliberately unavailable."""

import os
import sys

from ..runtime import check_runtime


def main(argv: list[str] | None = None, *, stdout=None, stderr=None) -> int:
    """Run the bootstrap command without reading stdin or loading a project."""
    check_runtime()
    raw = sys.argv[1:] if argv is None else argv
    arguments = list(raw) if isinstance(raw, (list, tuple)) and all(isinstance(a, str) for a in raw) else []
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    if arguments in (["--help"], ["-h"]):
        title = "SpecRoad | Core bootstrap"
        if getattr(out, "isatty", lambda: False)() and "NO_COLOR" not in os.environ:
            title = "\033[1;36m" + title + "\033[0m"
        out.write(title + "\n\n")
        out.write("Usage: specroad --help\n")
        out.write("The core can start. Project commands are not implemented yet.\n")
        return 0
    err.write("SpecRoad: missing or unsupported command. Use --help.\n")
    return 2
