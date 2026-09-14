"""Bootstrap command semantics, independent of terminals and presentation."""

from ..runtime import check_runtime


def dispatch(arguments: object) -> int:
    """Return a behavior status; never read stdin or load a project."""
    check_runtime()
    if not isinstance(arguments, (list, tuple)):
        return 2
    if not all(isinstance(item, str) for item in arguments):
        return 2
    return 0 if list(arguments) in (["--help"], ["-h"]) else 2
