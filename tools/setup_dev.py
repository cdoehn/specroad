"""Prepare the local development environment without running tests."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

DEFAULT_PYTHON = "3.14"
ROOT = Path(__file__).resolve().parents[1]


def setup(root):
    """Install the listed interpreters and reuse or create one Python 3.14 venv."""
    root = Path(root).resolve()
    versions = (root / ".python-versions").read_text(encoding="utf-8").split()
    if (not versions or DEFAULT_PYTHON not in versions
            or len(versions) != len(set(versions))
            or any(re.fullmatch(r"3\.[0-9]+", v) is None for v in versions)):
        raise ValueError(".python-versions must list distinct Python 3.x versions including 3.14")
    if not (root / "pyproject.toml").is_file():
        raise ValueError("The project pyproject.toml is missing")
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git is required; install Git and make it available on PATH")
    uv = shutil.which("uv")
    if uv is None:
        candidate = Path.home() / ".local/bin/uv"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            uv = str(candidate)
    if uv is None:
        raise ValueError("uv is required; install uv and make it available on PATH")
    subprocess.run([git, "--version"], cwd=root, check=True)
    environment = root / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    probe = "import json,sys; print(json.dumps([list(sys.version_info[:2]),sys.prefix,sys.base_prefix]))"
    exists = os.path.lexists(environment)
    if exists:
        if (environment.is_symlink() or not environment.is_dir()
                or (environment / "pyvenv.cfg").is_symlink()
                or not (environment / "pyvenv.cfg").is_file() or not python.is_file()):
            raise ValueError("Existing .venv is incomplete or linked; preserved without replacement")
        result = subprocess.run([str(python), "-I", "-B", "-c", probe], cwd=root,
                                check=True, capture_output=True, text=True)
        version, prefix, base_prefix = json.loads(result.stdout)
        if version != [3, 14] or Path(prefix).resolve() != environment or prefix == base_prefix:
            raise ValueError("Existing .venv must be a Python 3.14 virtual environment; preserved")
    subprocess.run([uv, "python", "install", *versions], cwd=root, check=True)
    if not exists:
        if os.path.lexists(environment):
            raise ValueError(".venv appeared during interpreter installation; preserved")
        subprocess.run([uv, "venv", "--python", DEFAULT_PYTHON,
                        "--no-python-downloads", str(environment)], cwd=root, check=True)
    result = subprocess.run([str(python), "-I", "-B", "-c", probe], cwd=root,
                            check=True, capture_output=True, text=True)
    version, prefix, base_prefix = json.loads(result.stdout)
    if version != [3, 14] or Path(prefix).resolve() != environment or prefix == base_prefix:
        raise ValueError("Setup did not produce a Python 3.14 virtual environment; preserved")
    subprocess.run([uv, "pip", "install", "--python", str(python), "--link-mode", "copy",
                    "--group", "dev", "--editable", "."], cwd=root, check=True)
    print("Development environment ready: " + str(python))
    print("Additional interpreters are available through uv; no tests were started.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        setup(ROOT)
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as error:
        print("Development setup failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
