"""Shared console, module and portable-distribution entry point."""

import sys

from .application import _error_options, execute
from .presentation import PrettyRenderer
from .results import FailureKind, OperationFailure, ResultContractError, failed_result, serialize_result


def main(argv: list[str] | None = None, *, stdout=None, stderr=None) -> int:
    """Keep machine documents separate from a replaceable human presenter."""
    arguments = sys.argv[1:] if argv is None else argv
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    display_options = _error_options(arguments)
    output_format = display_options.get("--format", "pretty")
    try:
        presenter = PrettyRenderer(out, err, no_color=display_options.get("--no-color", False),
                                   quiet=display_options.get("--quiet", False)) if output_format == "pretty" else None
        if presenter is not None:
            presenter.phase("Run command")
        response = execute(arguments)
        outcome = response.result
        output_format = response.options.get("--format", "pretty")
        try:
            code = outcome.exit_code
            machine = serialize_result(outcome, output_format) if output_format in ("json", "sarif") else None
        except (OperationFailure, ResultContractError) as error:
            kind = error.kind if isinstance(error, OperationFailure) else FailureKind.INTERNAL
            outcome = failed_result(outcome.command, kind, "Result delivery could not be confirmed.")
            code = outcome.exit_code
            machine = serialize_result(outcome, output_format) if output_format in ("json", "sarif") else None
        if output_format in ("json", "sarif"):
            out.write(machine + "\n")
            out.flush()
        else:
            if presenter is None:
                presenter = PrettyRenderer(out, err, no_color=response.options.get("--no-color", False),
                                           quiet=response.options.get("--quiet", False))
            presenter.finish(outcome)
    except (OSError, UnicodeError, ValueError):
        return 5
    return code
