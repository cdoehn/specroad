"""Pure systemd unit rendering, separate from manager commands and installation."""
import os
from pathlib import Path
import sys
from .errors import ControlError
from .local import Paths, REPO

UNIT = "specroad-control.service"
OWNER = "# Managed by specroad-control; format=1\n"


def quoted(value: str, *, command_line=False) -> str:
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ControlError("invalid_path", "Control characters in service paths are forbidden.")
    value = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    if command_line:
        value = value.replace("$", "$$")
    return '"' + value + '"'


def unit_text(paths: Paths, *, entrypoint=None) -> str:
    from .releases import active_entrypoint
    executable = str(Path(sys.executable).resolve())
    argv = [executable, "-B", str(entrypoint or active_entrypoint(paths)), "--config", str(paths.config), "run"]
    # Persist the same external state locations for the systemd user manager.
    env = {"SPECROAD_CONTROL_HOME": str(paths.data_root), "SPECROAD_CONTROL_INSTANCE": paths.instance, "XDG_CONFIG_HOME": str(paths.unit.parent.parent.parent)}
    log_path = str(paths.logs / "control.log")
    quoted(log_path)  # Reject control characters; file: directives take a literal path.
    log_path = log_path.replace("%", "%%")
    return (OWNER + "[Unit]\nDescription=SpecRoad Control (manual lifecycle)\n\n[Service]\nType=exec\n"
            + "ExecStart=" + " ".join(quoted(s, command_line=True) for s in argv) + "\n"
            + "WorkingDirectory=%h\n"
            + "".join("Environment=" + quoted(k + "=" + v) + "\n" for k, v in env.items())
            + "Environment=PYTHONDONTWRITEBYTECODE=1\nUMask=0077\nRestart=no\n"
            + "KillMode=mixed\nKillSignal=SIGTERM\nSendSIGKILL=no\nTimeoutStopSec=infinity\n"
            + "StandardOutput=append:" + log_path + "\n"
            + "StandardError=append:" + log_path + "\n")
    # Intentionally no [Install], WantedBy, enable, linger, timer or socket activation.
