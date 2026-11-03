"""Read-only bootstrap selection and history checks, separate from config writes."""
import os
from pathlib import Path
from .config import Config
from .core import Core
from .errors import ControlError
from .exchange import Exchange
from .job_contract import scope
from .ledger import Ledger
from .local import REPO


def inspect_history(config: Config, path: Path, legacy: dict | None) -> tuple[bool, bool]:
    exists, empty = os.path.lexists(path), False
    if exists and config.repo_id:
        history = Ledger(path, scope(config), allow_empty=True)
        try:
            from .apply_reconcile_history import require_no_pending
            require_no_pending(history)
            if legacy and history.seed_sha != legacy["sha256"]:
                raise ControlError("bootstrap_conflict", "Legacy seed disagrees with existing runtime history.")
            empty = history.current() is None
        finally:
            history.close()
    return exists, empty


def select_source(config: Config, result: str | None, legacy: dict | None, *, needs_initial: bool) -> dict | None:
    if legacy and result is None and needs_initial:
        # Only the previously approved bytes; never a newest-file guess.
        original = Path(legacy["path"])
        if original.exists():
            result = str(original)
        else:
            exchange = Exchange(config, Core(config))
            matches = [item for item in exchange.candidates("result", lambda _m: True)
                       if item["sha256"] == legacy["sha256"] and not item["dry_run"]]
            if not matches:
                raise ControlError("source_result_missing", "Approved legacy source is absent; runtime state was not reset.")
            result = matches[0]["path"]
    if result is None:
        return None
    path = Path(result).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ControlError("invalid_seed", "Supply an existing absolute product Result path in Exchange.")
    allowed = {config.exchange.resolve()}
    if config.archive_directory:
        allowed.add((config.exchange / config.archive_directory).resolve())
    if path.resolve().parent not in allowed:
        raise ControlError("invalid_seed", "The initial Result must be directly in Exchange or its configured archive.")
    source = Core(config).result(path)
    if (Path(source["repository_path"]).resolve() == REPO or source["dry_run"]
            or Path(source["repository_path"]).resolve() != config.repository.parent.resolve() / "specroad-apply"):
        raise ControlError("wrong_seed_repository", "Select a SpecRoad Apply Result, not a Control or Dev Result.")
    if legacy and legacy["sha256"] != source["sha256"]:
        raise ControlError("bootstrap_conflict", "Explicit source differs from the old approved seed; nothing is reset.")
    return source


def require_initial(config: Config, path: Path, source: dict | None, *, exists: bool) -> bool:
    """Inspect without mutation; only the later validated publication may seed."""
    if not exists:
        if source is None:
            raise ControlError("state_not_initialized", "Supply --result once to initialize the runtime state.")
        return False
    history = Ledger(path, scope(config), allow_empty=True)
    try:
        if source is not None and history.seed_sha != source["sha256"]:
            raise ControlError("bootstrap_conflict", "Existing runtime state has a different initial Result.")
        empty = history.current() is None
        if source is None and empty:
            raise ControlError("state_not_initialized", "Supply the matching initial Result for the empty runtime history.")
        return empty
    finally:
        history.close()
