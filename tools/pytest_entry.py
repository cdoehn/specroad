"""Trusted bootstrap for pytest and its worker processes; not a test scheduler."""

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    sys.dont_write_bytecode = True
    # xdist captures sys.path at import time and gives this to its workers.
    for directory in (ROOT / "src", ROOT / "tests", ROOT / "tools"):
        value = str(directory)
        if value not in sys.path:
            sys.path.insert(0, value)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        import pytest
    except ImportError:
        print("Missing development dependencies: install the dev group first.", file=sys.stderr)
        return 4
    return int(pytest.main(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
