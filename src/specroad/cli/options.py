"""Resolve CLI input and its provenance, without composing profiles or variants.

Project discovery reads only specroad.json along the ancestor chain. The
resolved selectors describe requested input, not installed capabilities or
completed profile validation. Full schema/preflight services arrive separately.
"""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
import json
import errno
import os
import stat

from .contracts import CommandUsageError, Invocation, OptionSpec, PreflightProfile


CORE_PROFILE = "core@0.2.0"
_GLOBAL_OPTIONS = {
    "--project": OptionSpec("--project", takes_value=True),
    "--profile": OptionSpec("--profile", takes_value=True, repeatable=True),
    "--configuration": OptionSpec("--configuration", takes_value=True),
    "--fail-on": OptionSpec("--fail-on", takes_value=True, choices=("error", "warning")),
    "--strict": OptionSpec("--strict"),
}


def global_options(*flags: str) -> tuple[OptionSpec, ...]:
    """Opt in per command; there is no universally accepted option catch-all."""
    try:
        return tuple(_GLOBAL_OPTIONS[flag] for flag in flags)
    except KeyError as error:
        raise CommandUsageError("Global option is not implemented") from error


def check_global_contract(command) -> None:
    """A recognized global flag must keep its shared parsing semantics."""
    for option in command.options:
        expected = _GLOBAL_OPTIONS.get(option.flag)
        if expected is None:
            continue
        if (option.takes_value, option.repeatable, option.choices) != (expected.takes_value, expected.repeatable, expected.choices):
            raise CommandUsageError("Command redefines a global option")
    if command.preflight_profile is PreflightProfile.BOOTSTRAP and any(option.flag == "--project" for option in command.options):
        raise CommandUsageError("Bootstrap contract must not select a project")


class OptionResolutionError(CommandUsageError):
    def __init__(self, message: str, exit_code: int = 2):
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class OptionOrigin:
    source: str
    value: object


@dataclass(frozen=True)
class ResolvedOptions:
    project_root: Path | None
    project_source: str | None
    values: Mapping[str, object]
    history: Mapping[str, tuple[OptionOrigin, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "history", MappingProxyType({key: tuple(value) for key, value in self.history.items()}))

    @property
    def origins(self) -> Mapping[str, str]:
        return MappingProxyType({key: changes[-1].source for key, changes in self.history.items()})


@dataclass(frozen=True)
class OptionLayer:
    """Already resolved policy values, supplied by a future profile/variant engine.

This adapter does not load, activate or validate the selected profile resources.
Unknown values are rejected rather than pretending their policy was applied.
"""
    label: str
    values: Mapping[str, object]

    def __post_init__(self) -> None:
        _text(self.label, "layer label")
        if not isinstance(self.values, Mapping):
            raise OptionResolutionError("Layer values must be a mapping")
        checked = {}
        for name, value in self.values.items():
            if name != "fail_on":
                raise OptionResolutionError("Unsupported policy-layer value")
            checked[name] = _threshold(value)
        object.__setattr__(self, "values", MappingProxyType(checked))


def _text(value, name):
    if not isinstance(value, str) or not value or "\0" in value:
        raise OptionResolutionError("Invalid " + name)
    return value


def _profiles(value) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise OptionResolutionError("Profiles must be an ordered list")
    result = [CORE_PROFILE]
    for item in value:
        _text(item, "profile selector")
        if item in {"core", CORE_PROFILE}:
            continue
        if item.startswith("core@"):
            raise OptionResolutionError("The Core profile version is fixed by this distribution")
        result.append(item)
    return tuple(result)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OptionResolutionError("Duplicate configuration key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise OptionResolutionError("Non-finite configuration number")


def _read_configuration(path: Path) -> dict:
    """Read one regular configuration file; never follow a config-file link."""
    try:
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode):
            raise OptionResolutionError("Linked project configuration is not accepted", 7)
        if not stat.S_ISREG(before.st_mode):
            raise OptionResolutionError("Project configuration must be a regular file")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                raise OptionResolutionError("Configuration identity changed while opening", 7)
            raw = stream.read()
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except OptionResolutionError:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        raise OptionResolutionError("Invalid project configuration") from error
    except OSError as error:
        code = 7 if error.errno == errno.ELOOP else 5
        raise OptionResolutionError("Cannot read project configuration", code) from error
    if not isinstance(data, dict):
        raise OptionResolutionError("Project configuration must be an object")
    return data


def _project(command, options, cwd):
    explicit = options.get("--project")
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
            return root, "cli", _read_configuration(config)
        start = (Path.cwd() if cwd is None else Path(cwd)).resolve(strict=True)
        if not start.is_dir():
            raise OptionResolutionError("Search origin is not a directory")
        for root in (start, *start.parents):
            config = root / "specroad.json"
            try:
                config.lstat()
            except FileNotFoundError:
                continue
            return root, "discovery", _read_configuration(config)
    except OptionResolutionError:
        raise
    except FileNotFoundError as error:
        raise OptionResolutionError("Selected project does not exist") from error
    except (TypeError, ValueError) as error:
        raise OptionResolutionError("Invalid project search input") from error
    except (OSError, RuntimeError) as error:
        raise OptionResolutionError("Cannot resolve project", 5) from error
    raise OptionResolutionError("No project found; initialization must be explicit")


def _threshold(value):
    if not isinstance(value, str) or value not in {"error", "warning"}:
        raise OptionResolutionError("Invalid failure threshold")
    return value


def resolve_options(invocation: Invocation, *, cwd: Path | None = None,
                    profile_layers: tuple[OptionLayer, ...] = (),
                    configuration_layer: OptionLayer | None = None) -> ResolvedOptions:
    check_global_contract(invocation.command)
    if not isinstance(profile_layers, (tuple, list)) or not all(isinstance(layer, OptionLayer) for layer in profile_layers):
        raise OptionResolutionError("Invalid profile-policy layers")
    if configuration_layer is not None and not isinstance(configuration_layer, OptionLayer):
        raise OptionResolutionError("Invalid configuration-policy layer")
    root, source, project = _project(invocation.command, invocation.options, cwd)
    values = {"profiles": (CORE_PROFILE,), "configuration": None, "fail_on": "error",
              "strict": False, "core_lint_optional": False}
    history = {name: [OptionOrigin("default", value)] for name, value in values.items()}

    def assign(name, value, origin):
        values[name] = value
        history[name].append(OptionOrigin(origin, value))

    if "profiles" in project:
        assign("profiles", _profiles(project["profiles"]), "project")
    policy = project.get("validation_policy", {})
    if not isinstance(policy, dict):
        raise OptionResolutionError("validation_policy must be an object")
    if "fail_on" in policy:
        assign("fail_on", _threshold(policy["fail_on"]), "project")
    for layer in profile_layers:
        for name, value in layer.values.items():
            assign(name, value, "profile:" + layer.label)
    if configuration_layer is not None:
        for name, value in configuration_layer.values.items():
            assign(name, value, "configuration:" + configuration_layer.label)
    if "--profile" in invocation.options:
        assign("profiles", _profiles(invocation.options["--profile"]), "cli")
    if "--configuration" in invocation.options:
        assign("configuration", _text(invocation.options["--configuration"], "configuration selector"), "cli")
    if "--fail-on" in invocation.options:
        assign("fail_on", _threshold(invocation.options["--fail-on"]), "cli")
    if "--strict" in invocation.options:
        if invocation.options["--strict"] is not True:
            raise OptionResolutionError("strict must be a boolean flag")
        assign("strict", True, "cli")
        assign("fail_on", "warning", "cli:strict")
        assign("core_lint_optional", True, "cli:strict")
    return ResolvedOptions(root, source, values, history)


def policy_exit_code(severities, resolved: ResolvedOptions) -> int:
    """Assess only known diagnostics; strict never starts analysis or hides work."""
    threshold = _threshold(resolved.values["fail_on"])
    failed = False
    for severity in severities:
        if not isinstance(severity, str) or severity not in {"error", "warning", "info"}:
            raise OptionResolutionError("Unknown diagnostic severity")
        failed = failed or severity == "error" or (threshold == "warning" and severity == "warning")
    return 1 if failed else 0
