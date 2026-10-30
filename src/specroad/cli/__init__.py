"""Shared console, module and portable-distribution entry point."""

import sys

def execute(*args, **kwargs):
    """Load execution only when requested; importing the CLI is inert."""
    from .application import execute as run
    return run(*args, **kwargs)


def PrettyRenderer(*args, **kwargs):
    """Presentation is a replaceable dependency, not part of machine execution."""
    from .presentation import PrettyRenderer as renderer
    return renderer(*args, **kwargs)


def main(argv: list[str] | None = None, *, stdout=None, stderr=None, context_builder=None) -> int:
    """Keep machine documents separate from a replaceable human presenter."""
    from .application import _error_options
    from .results import FailureKind, OperationFailure, ResultContractError, failed_result, serialize_result

    arguments = sys.argv[1:] if argv is None else argv
    if isinstance(arguments, (list, tuple)):
        arguments = tuple(arguments)
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    display_options = _error_options(arguments)
    output_format = display_options.get("--format", "pretty")
    try:
        presenter = PrettyRenderer(out, err, no_color=display_options.get("--no-color", False),
                                   quiet=display_options.get("--quiet", False)) if output_format == "pretty" else None
        if presenter is not None:
            presenter.phase("Run command")
        response = (execute(arguments) if context_builder is None else
                    execute(arguments, context_builder=context_builder))
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
            from ._machine_delivery import write_machine_document
            write_machine_document(out, machine)
        else:
            if presenter is None:
                presenter = PrettyRenderer(out, err, no_color=response.options.get("--no-color", False),
                                           quiet=response.options.get("--quiet", False))
            presenter.finish(outcome)
    except (OSError, UnicodeError, ValueError):
        return 5
    return code
