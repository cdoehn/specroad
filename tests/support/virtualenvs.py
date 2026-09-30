"""Fresh, no-pip test environments using the platform's normal venv strategy."""

import os
from pathlib import Path
import venv


def create_no_pip_venv(directory):
    """Return the unactivated interpreter, retaining its base-runtime location.

    EnvBuilder defaults to copies, unlike the POSIX venv CLI. A copied nested
    3.10 interpreter can retain the outer venv's bin directory as its home and
    fall back to a non-existent compiled toolcache prefix. POSIX links retain
    the route to the actual base executable. Windows keeps its redirectors.
    The subprocess helper's -I/-S/-B and environment allowlist stay unchanged.
    """
    directory = Path(directory)
    venv.EnvBuilder(with_pip=False, symlinks=os.name != 'nt').create(directory)
    return directory / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
