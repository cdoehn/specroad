"""Only specroad-control.service is managed. Never start/enable PatchHarbor."""
from pathlib import Path
import subprocess
from .config import initialize, load
from .errors import ControlError
from .local import Paths, lock, read_private, user_dir, write_private, private_dir
from .systemd_unit import OWNER, UNIT, quoted, unit_text

SYSTEMCTL = "/usr/bin/systemctl"


def command(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([SYSTEMCTL, "--user", *args], stdin=subprocess.DEVNULL,
                              text=True, capture_output=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ControlError("systemd_unavailable", "The user systemd manager is unavailable or did not respond.") from None


def checked(args: list[str]):
    result = command(args)
    if result.returncode:
        raise ControlError("systemd_failed", "systemctl failed; inspect the user manager locally.")
    return result


def inspect() -> dict:
    result = command(["show", UNIT, "--property=LoadState,ActiveState,SubState,UnitFileState,FragmentPath,DropInPaths"])
    if result.returncode not in (0, 4):
        raise ControlError("systemd_unavailable", "No usable systemd user manager. Run from your Ubuntu login session.")
    props = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if "LoadState" not in props:
        raise ControlError("systemd_unavailable", "The user manager returned no unit information.")
    return props


def verify_properties(paths: Paths, properties: dict):
    fragment = properties.get("FragmentPath")
    if fragment and Path(fragment).resolve() != paths.unit.resolve():
        raise ControlError("foreign_unit", "systemd loaded this service from a different location.")
    if properties.get("UnitFileState", "").startswith("enabled"):
        raise ControlError("autostart_enabled", "This controller requires a manually started, non-enabled unit.")
    if properties.get("DropInPaths"):
        raise ControlError("unit_override", "Unreviewed systemd drop-ins are not permitted.")


def verify_owned(paths: Paths):
    try:
        data = read_private(paths.unit)
    except FileNotFoundError:
        raise ControlError("not_installed", "Run control install before starting the service.") from None
    if not data.startswith(OWNER.encode()):
        raise ControlError("foreign_unit", "An unrelated service file will not be overwritten or controlled.")
    properties = inspect()
    verify_properties(paths, properties)
    return properties


def install(paths: Paths) -> dict:
    with lock(paths.state / "operation.lock"):
        properties = inspect()  # Do not create configuration when the manager is absent.
        verify_properties(paths, properties)
        if properties.get("ActiveState") not in (None, "inactive", "failed"):
            raise ControlError("service_active", "Stop the controller before installation or update.")
        expected = unit_text(paths).encode()
        private_dir(paths.logs)
        if paths.unit.exists() or paths.unit.is_symlink():
            verify_owned(paths)
        user_dir(paths.unit.parent)  # New directories are 0700, independent of the caller's umask.
        initialize(paths)
        if not paths.unit.exists():
            write_private(paths.unit, expected, exclusive=True)
        elif read_private(paths.unit) != expected:
            write_private(paths.unit, expected)  # Explicit install, owned inactive unit only.
        checked(["daemon-reload"])
        return {"installed": True, "started": False, "autostart": False, "config": str(paths.config)}


def start(paths: Paths) -> dict:
    with lock(paths.state / "operation.lock"):
        from .handover_queue import startup
        startup(paths)
        properties = verify_owned(paths)
        if properties.get("ActiveState") == "deactivating":
            raise ControlError("stopping", "Wait until the pending graceful stop has completed.")
        if read_private(paths.unit) != unit_text(paths).encode():
            raise ControlError("unit_conflict", "Installed service and current paths do not match.")
        checked(["start", UNIT])
        return {"start_requested": True}  # Not a claim of a ready worker or active development.


def stop(paths: Paths) -> dict:
    with lock(paths.state / "operation.lock"):
        verify_owned(paths)  # Deliberately do not load config: stop works with broken config.
        checked(["--no-block", "stop", UNIT])
        return {"stop_requested": True, "graceful": True}
