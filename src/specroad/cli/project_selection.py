"""Current root selection and profile-specific metadata checks, without a model."""

from pathlib import Path
import errno
import stat

from ..security import ProjectBoundary, SafetyViolation, check_project_declarations
from ..storage.json_syntax import parse_json_object
from .contracts import PreflightProfile
from .option_values import OptionResolutionError, _text


def _read_configuration(path: Path, *, project_read=False) -> dict:
    """Read one regular configuration file; never follow a config-file link."""
    try:
        # Preserve the established usage classification for a missing/invalid
        # config file; the subsequent descriptor-bound read still revalidates it.
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode):
            raise SafetyViolation("Linked project configuration is not accepted")
        if not stat.S_ISREG(before.st_mode):
            raise OptionResolutionError("Project configuration must be a regular file")
        boundary = ProjectBoundary(path.parent)
        raw = boundary.read_bytes(path.name)
        data = parse_json_object(raw, path="specroad.json")
    except SafetyViolation as error:
        raise OptionResolutionError("Project safety boundary rejected the configuration", 7) from error
    except OptionResolutionError:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        if project_read:
            from .results import FailureKind, OperationFailure
            raise OperationFailure(FailureKind.MODEL, "Invalid project configuration.",
                details={'preflight': {'profile': 'project_read',
                    'reason': 'invalid_project_configuration',
                    'normal_operation_started': False, 'model_loaded': False,
                    'write_authorized': False, 'recovery_performed': False}}) from error
        raise OptionResolutionError("Invalid project configuration") from error
    except OSError as error:
        code = 7 if error.errno == errno.ELOOP else 5
        raise OptionResolutionError("Cannot read project configuration", code) from error
    if not isinstance(data, dict):
        raise OptionResolutionError("Project configuration must be an object")
    try:
        check_project_declarations(data)
    except SafetyViolation as error:
        raise OptionResolutionError("Project execution or root declaration is not allowed", 7) from error
    if project_read:
        from ..runtime.preflight import require_project_read_preflight
        require_project_read_preflight(boundary, raw)
    return data


def select_project(command, options, cwd):
    explicit = options.get("--project")
    project_read = (command.preflight_profile is PreflightProfile.PROJECT_READ
                    or (command.preflight_profile is PreflightProfile.PROJECT_WRITE
                        and options.get("--dry-run") is True))
    if command.preflight_profile is PreflightProfile.BOOTSTRAP:
        if explicit is not None:
            raise OptionResolutionError("Bootstrap does not select a project")
        return None, None, {}
    if explicit is None and not command.requires_project:
        return None, None, {}
    try:
        if explicit is not None:
            requested = Path(_text(explicit, "project path"))
            if not requested.is_absolute():
                requested = (Path.cwd() if cwd is None else Path(cwd)) / requested
            root = requested.resolve(strict=True)
            if not root.is_dir():
                raise OptionResolutionError("Explicit project path is not a directory")
            config = root / "specroad.json"
            config.lstat()
            return root, "cli", _read_configuration(config, project_read=project_read)
        start = (Path.cwd() if cwd is None else Path(cwd)).resolve(strict=True)
        if not start.is_dir():
            raise OptionResolutionError("Search origin is not a directory")
        for root in (start, *start.parents):
            config = root / "specroad.json"
            try:
                config.lstat()
            except FileNotFoundError:
                continue
            return root, "discovery", _read_configuration(config, project_read=project_read)
    except OptionResolutionError:
        raise
    except FileNotFoundError as error:
        raise OptionResolutionError("Selected project does not exist") from error
    except (TypeError, ValueError) as error:
        raise OptionResolutionError("Invalid project search input") from error
    except (OSError, RuntimeError) as error:
        raise OptionResolutionError("Cannot resolve project", 5) from error
    raise OptionResolutionError("No project found; initialization must be explicit")
