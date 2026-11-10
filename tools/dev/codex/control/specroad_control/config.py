"""External opt-in configuration. Old foundation-only configurations remain inert."""
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from specroad_control.toml_compat import tomllib
from uuid import UUID
from .errors import ControlError
from .execution_scope import execution_directory, writable_roots
from .local import Paths, REPO, outside, read_private, write_private


@dataclass(frozen=True)
class Config:
    repository: Path
    exchange: Path
    session_id: str
    enabled: bool = False
    repo_id: str = ""
    core_python: Path | None = None
    codex_executable: Path | None = None
    codex_home: Path | None = None
    transport: str = "exec"
    settle_seconds: float = 0.5
    archive_directory: str = "PatchHarbor-Archive"
    command_path: str = ""
    retry_delays_seconds: tuple = (60, 180, 600, 1800)
    thread_cwd: Path | None = None
    start_delay_seconds: float = 60.0
    access_mode: str = "workspace-write"
    apply_repository: Path | None = None

    @property
    def apply_directory(self):
        if self.apply_repository is not None:
            return self.apply_repository
        name = "specroad-apply2" if self.repository.name == "specroad-dev2" else "specroad-apply"
        return self.repository.parent / name


def template() -> str:
    # The integrated source is a development tool, excluded from the product package.
    project = REPO.parents[3] if REPO.parts[-4:] == ("tools", "dev", "codex", "control") else None
    workspace = project.parent if project else Path.home() / "Codex/specroad"
    return render(Config(workspace / "specroad-codex", workspace / "exchange", ""))


def render(config: Config) -> str:
    q = lambda value: json.dumps(str(value) if value is not None else "", ensure_ascii=False)
    return ("format_version = 1\n\n[develop]\nrepository = " + q(config.repository)
            + "\nsession_id = " + q(config.session_id)
            + "\ncodex_executable = " + q(config.codex_executable)
            + "\ncodex_home = " + q(config.codex_home)
            + "\ntransport = " + q(config.transport)
            + "\naccess_mode = " + q(config.access_mode)
            + "\ncommand_path = " + q(config.command_path)
            + ("\nthread_cwd = " + q(config.thread_cwd) if config.thread_cwd is not None else "")
            + "\n\n[patchharbor]\nexchange = " + q(config.exchange)
            + ("\nrepository = " + q(config.apply_repository) if config.apply_repository is not None else "")
            + "\nrepo_id = " + q(config.repo_id)
            + "\npython_executable = " + q(config.core_python)
            + "\narchive_directory = " + q(config.archive_directory)
            + "\n\n[automation]\nenabled = " + str(config.enabled).lower()
            + "\nsettle_seconds = " + str(config.settle_seconds)
            + "\nstart_delay_seconds = " + str(config.start_delay_seconds)
            + "\nretry_delays_seconds = " + json.dumps(list(config.retry_delays_seconds)) + "\n")


def text(value) -> str:
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError
    return value


def absolute(value, *, optional=False) -> Path | None:
    value = text(value)
    if optional and not value:
        return None
    if not value:
        raise ValueError
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError
    return path


def identity(value, *, optional=False) -> str:
    value = text(value)
    if value or not optional:
        if str(UUID(value)) != value:
            raise ValueError
    return value


def digest(value, *, optional=False) -> str:
    value = text(value)
    if value or not optional:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError
    return value


def parse(doc: dict, paths: Paths) -> Config:
    if type(doc.get("format_version")) is not int or doc["format_version"] != 1:
        raise ValueError
    if not {"format_version", "develop", "patchharbor"} <= set(doc) or set(doc) - {"format_version", "develop", "patchharbor", "automation"}:
        raise ValueError
    dev, ph, auto = doc["develop"], doc["patchharbor"], doc.get("automation", {})
    if not all(isinstance(x, dict) for x in (dev, ph, auto)):
        raise ValueError
    if set(dev) - {"repository", "session_id", "codex_executable", "codex_home", "transport", "command_path", "thread_cwd", "access_mode"}:
        raise ValueError
    if set(ph) - {"exchange", "repo_id", "python_executable", "archive_directory", "repository"}:
        raise ValueError
    if set(auto) - {"enabled", "seed_result", "seed_sha256", "settle_seconds", "retry_delays_seconds", "start_delay_seconds"}:
        raise ValueError
    # Blank legacy template keys remain readable until explicit setup rewrites
    # them. Nonempty old bootstrap data must be migrated, never silently dropped.
    legacy_path = text(auto.get("seed_result", ""))
    legacy_sha = text(auto.get("seed_sha256", ""))
    if legacy_path or legacy_sha:
        raise ControlError("seed_migration_required", "Run explicit configure to migrate the old bootstrap into runtime state.")
    repo, exchange = absolute(dev["repository"]), absolute(ph["exchange"])
    session = identity(dev["session_id"], optional=True)
    enabled = auto.get("enabled", False)
    if type(enabled) is not bool:
        raise ValueError
    settle = auto.get("settle_seconds", 0.5)
    if type(settle) not in (int, float) or not math.isfinite(settle) or not 0.05 <= settle <= 30:
        raise ValueError
    delay = auto.get("start_delay_seconds", 60.0)
    if type(delay) not in (int, float) or not 0 <= delay <= 86400:
        raise ValueError
    retry_delays = auto.get("retry_delays_seconds", [60, 180, 600, 1800])
    if (not isinstance(retry_delays, list) or len(retry_delays) > 8
            or any(type(v) is not int or not 1 <= v <= 86400 for v in retry_delays)
            or retry_delays != sorted(retry_delays)):
        raise ValueError
    transport = text(dev.get("transport", "exec"))
    if transport not in ("exec", "app-server-proxy"):
        raise ValueError
    access_mode = text(dev.get("access_mode", "workspace-write"))
    if access_mode not in ("workspace-write", "full-access"):
        raise ValueError
    archive = text(ph.get("archive_directory", "PatchHarbor-Archive"))
    if archive and (archive in (".", "..") or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in archive)):
        raise ValueError
    config = Config(repository=repo, exchange=exchange, session_id=session, enabled=enabled,
                    repo_id=identity(ph.get("repo_id", ""), optional=True),
                    core_python=absolute(ph.get("python_executable", ""), optional=True),
                    codex_executable=absolute(dev.get("codex_executable", ""), optional=True),
                    codex_home=absolute(dev.get("codex_home", ""), optional=True),
                    transport=transport, settle_seconds=float(settle), archive_directory=archive,
                    command_path=text(dev.get("command_path", "")), retry_delays_seconds=tuple(retry_delays),
                    thread_cwd=absolute(dev.get("thread_cwd", ""), optional=True),
                    start_delay_seconds=float(delay), access_mode=access_mode,
                    apply_repository=absolute(ph.get("repository", ""), optional=True))
    repo_real, exchange_real = repo.resolve(), exchange.resolve()
    apply_real = config.apply_directory.resolve()
    if (apply_real == repo_real or apply_real in repo_real.parents or repo_real in apply_real.parents
            or apply_real == exchange_real or apply_real in exchange_real.parents or exchange_real in apply_real.parents):
        raise ValueError
    if any(p == apply_real or apply_real in p.parents for p in
           (paths.config.resolve(), paths.state.resolve(), paths.runtime.resolve(), paths.unit.resolve())):
        raise ControlError("local_path_in_repository", "Local data cannot be in Apply.")
    if config.thread_cwd is not None:
        target = config.thread_cwd
        if (not Path(dev['thread_cwd']).is_absolute() or target != target.resolve()
                or target not in (repo_real, repo_real.parent)
                or any(p.is_symlink() or not p.is_dir() for p in (target, *target.parents))):
            raise ValueError
    if (repo_real == exchange_real or repo_real in exchange_real.parents or exchange_real in repo_real.parents
            or repo_real == REPO or REPO in repo_real.parents
            or exchange_real == REPO or REPO in exchange_real.parents or exchange_real in REPO.parents):
        raise ValueError
    if any(p == repo_real or repo_real in p.parents or p == exchange_real or exchange_real in p.parents
           for p in (paths.config.resolve(), paths.state.resolve(), paths.runtime.resolve(), paths.unit.resolve())):
        raise ControlError("local_path_in_repository", "Local data cannot be in Dev or Exchange.")
    if config.codex_home:
        outside(config.codex_home)
        if config.codex_home.resolve() == repo_real or repo_real in config.codex_home.resolve().parents or config.codex_home.resolve() == exchange_real or exchange_real in config.codex_home.resolve().parents:
            raise ValueError
    if enabled and not all((session, config.repo_id, config.core_python, config.codex_executable, config.codex_home)):
        raise ControlError("automation_not_configured", "Explicit thread, target repository and tools are required.")
    if enabled:
        for executable in (config.core_python, config.codex_executable):
            if not executable.is_file() or not os.access(executable, os.X_OK):
                raise ControlError("configured_tool_unavailable", "An explicitly configured local executable is unavailable.")
        if not config.codex_home.is_dir():
            raise ControlError("codex_home_unavailable", "The existing Codex home must be available; no login is created.")
    return config


def load(paths: Paths, *, allow_deferred=False) -> Config:
    from .migration import require_complete
    require_complete(paths)
    require_no_handover(paths, allow_deferred=allow_deferred)
    try:
        return parse(tomllib.loads(read_private(paths.config).decode("utf-8")), paths)
    except FileNotFoundError:
        raise ControlError("config_missing", "Run control install to create the external configuration.") from None
    except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
        raise ControlError("invalid_config", "Invalid external configuration; existing bytes were preserved.") from None


def initialize(paths: Paths):
    require_no_handover(paths)
    if not paths.config.exists():
        write_private(paths.config, template().encode(), exclusive=True)
    return load(paths)


def child_environment(config: Config) -> dict:
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "CODEX_THREAD_ID", "CODEX_SESSION_ID"):
        env.pop(name, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if config.codex_home:
        env["CODEX_HOME"] = str(config.codex_home)
    if config.command_path:
        env["PATH"] = config.command_path
    return env


def setup_config(paths: Paths) -> tuple[Config, dict | None]:
    """Read old bootstrap keys ONLY for an explicitly requested setup migration.

    Ordinary load/check/start remain read-only and refuse nonempty legacy seeds.
    No writer ever renders them back into the persistent configuration.
    """
    require_no_handover(paths)
    if not paths.config.exists():
        return initialize(paths), None
    try:
        doc = tomllib.loads(read_private(paths.config).decode("utf-8"))
        auto = doc.get("automation", {})
        if not isinstance(auto, dict):
            raise ValueError
        path = absolute(auto.pop("seed_result", ""), optional=True)
        sha = digest(auto.pop("seed_sha256", ""), optional=True)
        if bool(path) != bool(sha):
            raise ValueError
        config = parse(doc, paths)
        legacy = {"path": str(path), "sha256": sha} if path else None
        if legacy and (config.exchange.resolve() not in path.resolve().parents or path.is_symlink()):
            raise ValueError
        return config, legacy
    except (KeyError, ValueError, TypeError, UnicodeError, RecursionError):
        raise ControlError("invalid_config", "Invalid legacy configuration; existing bytes were preserved.") from None


def require_no_handover(paths: Paths, *, allow_deferred=False):
    if not allow_deferred and any(os.path.lexists(paths.state / name) for name in
                                 ("thread-handover-request.json", "thread-handover-state.json")):
        raise ControlError("handover_deferred", "A deferred thread handover owns this configuration until completion.")
    if os.path.lexists(paths.state / "thread-handover-pending.json"):
        raise ControlError("handover_pending", "Finish the explicit thread handover before ordinary operations.")


def thread_directories(config: Config) -> set[Path]:
    """Accept the declared workspace and a previous Dev-root turn during transition."""
    roots = {config.repository.resolve()}
    if config.thread_cwd is not None:
        roots.add(config.thread_cwd.resolve())
    return roots
