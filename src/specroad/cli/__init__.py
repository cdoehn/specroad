"""Shared console, module and portable-distribution entry point."""

import sys

from .application import execute
from .presentation import render
from .results import FailureKind, OperationFailure, ResultContractError, failed_result, serialize_result


def main(argv: list[str] | None = None, *, stdout=None, stderr=None) -> int:
    """Emit exactly one machine document, or delegate human presentation."""
    response = execute(sys.argv[1:] if argv is None else argv)
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    try:
        output_format = response.options.get("--format", "pretty")
        try:
            code = response.result.exit_code
            machine = serialize_result(response.result, output_format) if output_format in ("json", "sarif") else None
        except (OperationFailure, ResultContractError) as error:
            kind = error.kind if isinstance(error, OperationFailure) else FailureKind.INTERNAL
            outcome = failed_result(response.result.command, kind, "Result delivery could not be confirmed.")
            code = outcome.exit_code
            machine = serialize_result(outcome, output_format) if output_format in ("json", "sarif") else None
        if output_format in ("json", "sarif"):
            out.write(machine + "\n")
            out.flush()
        else:
            render(code, out, err)
    except (OSError, UnicodeError):
        return 5
    return code
