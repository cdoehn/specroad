"""Closed-stdin, no-timeout test processes with an isolated environment."""

from pathlib import Path
import os
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[2] / "src"


def run_python(arguments, cwd, *, python=None, capture=False):
    """Run trusted Python with closed stdin and no shell or harness timeout."""
    environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR")
                   if key in os.environ}
    environment["PATH"] = ""
    return subprocess.run(
        [str(python or sys.executable), *arguments], cwd=cwd, env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def run_core(body, cwd, *, python=None, expose_cwd=False, capture=False):
    prefix = "import sys;sys.path.insert(0," + repr(str(SOURCE)) + ");\n"
    if expose_cwd:
        prefix += "sys.path.append(" + repr(str(cwd)) + ");\n"
    return run_python(["-I", "-S", "-B", "-c", prefix + body], cwd,
                      python=python, capture=capture)


def run_cli(arguments, cwd, *, capture=False):
    body = "from specroad.cli import main;sys.exit(main(" + repr(list(arguments)) + "))"
    return run_core(body, cwd, capture=capture)
