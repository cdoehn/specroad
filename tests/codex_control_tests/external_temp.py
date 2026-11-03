"""Private Linux test homes independent of Apply's repository-local TMPDIR."""
import os
from pathlib import Path
import tempfile

from specroad_control.errors import ControlError
from specroad_control.local import outside


# Sandbox setup can transiently create /tmp/.git after a home was admitted.
# Keep the entire lifetime on the independent persistent temporary root.
# Unavailable/unsafe /var/tmp fails closed; never fall back to the shared /tmp.
TEMP_PARENTS = (Path('/var/tmp'),)
DAEMON_SOCKET = 'codex-home/app-server-control/app-server-control.sock'


def temporary_directory(*, prefix='src-test-', socket_suffix=DAEMON_SOCKET):
    """Own one short 0700 directory; callers must register its cleanup.

    Keep the real repository/symlink guards. Do not change environment or
    tempfile's process-wide cache, which other SpecRoad tests also use.
    """
    last_error = None
    for parent in TEMP_PARENTS:
        temporary = None
        try:
            outside(parent)
            temporary = tempfile.TemporaryDirectory(prefix=prefix, dir=parent)
            root = outside(Path(temporary.name))
            if len(os.fsencode(root / socket_suffix)) >= 108:
                raise ValueError('Control test socket path exceeds the Linux limit')
            return temporary
        except (ControlError, OSError, ValueError) as error:
            if temporary is not None:
                temporary.cleanup()
            last_error = error
    raise RuntimeError('No short private test directory outside Git is available') from last_error
