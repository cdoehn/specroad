"""Private local files and locations, strictly outside Git and Exchange."""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
from .errors import ControlError

REPO = Path(__file__).resolve().parent.parent

def outside(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        raise ControlError("invalid_path", "Local paths must be absolute.")
    resolved = path.resolve()
    forbidden = (REPO, REPO.parent / "specroad-codex", REPO.parent / "specroad-apply", REPO.parent / "exchange")
    if any(resolved == p.resolve() or p.resolve() in resolved.parents for p in forbidden):
        raise ControlError("local_path_in_repository", "Local data must remain outside repositories and Exchange.")
    if any(os.path.lexists(p / ".git") for p in (resolved, *resolved.parents)):
        raise ControlError("local_path_in_repository", "Local data must not be stored in a Git working tree.")
    for p in (path, *path.parents):
        if p.is_symlink():
            raise ControlError("unsafe_path", "Symbolic links are not supported for local data paths.")
    return resolved

@dataclass(frozen=True)
class Paths:
    config: Path
    state: Path
    runtime: Path
    unit: Path

    @property
    def home(self):
        return self.state.parent

    @property
    def logs(self):
        return self.home / "logs"

    @property
    def target_locks(self):
        return self.state / "target-locks"

    @classmethod
    def legacy(cls):
        home = Path.home()
        cfg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
        state = outside(Path(os.environ.get("XDG_STATE_HOME") or home / ".local/state") / "specroad-control")
        run = os.environ.get("XDG_RUNTIME_DIR")
        return cls(outside(cfg / "specroad-control/config.toml"), state,
                   outside(Path(run) / "specroad-control") if run else state / "run",
                   outside(cfg / "systemd/user/specroad-control.service"))

    @classmethod
    def discover(cls, config: str | None = None):
        home = Path.home()
        config_home = outside(Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config"))
        data_home = outside(Path(os.environ.get("SPECROAD_CONTROL_HOME") or
                                 home / ".local/share/specroad/dev/codex/control"))
        config_path = outside(Path(config)) if config else data_home / "config/config.toml"
        if config_path.parent != data_home / "config":
            raise ControlError("config_outside_data_home", "Configuration must be under Control's data home/config.")
        paths = cls(config_path, data_home / "state", data_home / "run",
                    outside(config_home / "systemd/user/specroad-control.service"))
        if len(os.fsencode(paths.socket)) >= 108:
            raise ControlError("socket_path_too_long", "The local control socket path is too long.")
        return paths

    @property
    def socket(self):
        return self.runtime / "control.sock"

    @property
    def state_file(self):
        return self.state / "state.json"


def user_dir(path: Path):
    """Create missing levels privately; preserve safe existing user directories.

    Each mkdir has its own explicit mode: parents=True would otherwise create
    intermediate directories using the caller's umask. Never chmod existing
    directories, and do not change the process-wide umask during installation.
    """
    path = outside(path)
    if not os.path.lexists(path):
        user_dir(path.parent)
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass  # A concurrent creator must pass the same checks below.
    outside(path)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o022:
        raise ControlError("unsafe_permissions", "Local directories must be user-owned and not writable by another user.")


def private_dir(path: Path):
    user_dir(path)
    st = path.lstat()
    if st.st_mode & 0o077:
        raise ControlError("unsafe_permissions", "Local directories must be owned by the user and mode 0700.")


def read_private(path: Path) -> bytes:
    outside(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_nlink != 1:
            raise ControlError("unsafe_permissions", "Local files must be private regular files owned by the user.")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise ControlError("file_too_large", "Local control file exceeds 64 KiB.")
        return data
    finally:
        os.close(fd)


def write_private(path: Path, data: bytes, *, exclusive: bool = False):
    outside(path)
    if not path.parent.exists():
        private_dir(path.parent)
    parent_state = path.parent.stat()
    if parent_state.st_uid != os.getuid() or parent_state.st_mode & 0o022:
        raise ControlError("unsafe_permissions", "Local file parents must not be writable by another user.")
    if path.exists() or path.is_symlink():
        if exclusive:
            raise FileExistsError(path)
        read_private(path)
    fd, tmp = tempfile.mkstemp(prefix=".control-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(tmp, path, follow_symlinks=False)
            os.unlink(tmp)
        else:
            outside(path)  # Recheck physical parents before publication.
            if path.exists() or path.is_symlink():
                read_private(path)
            os.replace(tmp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def decode_object(data: bytes | str) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def invalid_constant(_value):
        raise ValueError("Non-finite JSON number")
    value = json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def json_read(path: Path) -> dict | None:
    try:
        data = decode_object(read_private(path))
    except FileNotFoundError:
        return None
    except (ValueError, UnicodeError):
        raise ControlError("invalid_state", "Local state is not valid JSON.") from None
    if not isinstance(data, dict):
        raise ControlError("invalid_state", "Local state must be an object.")
    return data


def json_write(path: Path, value: dict):
    write_private(path, (json.dumps(value, sort_keys=True) + "\n").encode())


@contextmanager
def lock(path: Path):
    private_dir(path.parent)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_nlink != 1:
            raise ControlError("unsafe_lock", "The instance lock is not a private regular file.")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ControlError("already_running", "Another controller already owns this lock.") from None
        yield fd
    finally:
        os.close(fd)  # Never unlink a lock: another process could still hold its inode.
