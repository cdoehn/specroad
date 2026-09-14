"""Replaceable bootstrap presentation; not a behavior-test oracle."""

import os


def render(status: int, out, err) -> None:
    if status == 0:
        title = "SpecRoad | Core bootstrap"
        if getattr(out, "isatty", lambda: False)() and "NO_COLOR" not in os.environ:
            title = "\033[1;36m" + title + "\033[0m"
        out.write(title + "\n\n")
        out.write("Usage: specroad --help\n")
        out.write("The core can start. Project commands are not implemented yet.\n")
    else:
        err.write("SpecRoad: missing or unsupported command. Use --help.\n")
